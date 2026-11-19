from __future__ import annotations

import io
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import workspace

from buildsys import qualify, sandbox, targets
from buildsys.qualify import QualificationError, _check_baseline_failures, _junit


class UpstreamReportTests(unittest.TestCase):
    def test_only_failures_reproduced_by_the_baseline_are_shared(self) -> None:
        _check_baseline_failures({'a'}, {'a': 'fail'})
        for baseline in ({'a': 'run'}, {}, {'a': 'fail', 'b': 'fail'}):
            with self.subTest(baseline=baseline), self.assertRaises(QualificationError):
                _check_baseline_failures({'a'}, baseline)

    def test_rejects_missing_duplicate_and_skipped_results(self) -> None:
        with workspace() as directory:
            report = directory / 'report.xml'
            report.write_text('<testsuite><testcase name="a" status="run"/><testcase name="b" status="fail"/></testsuite>')
            self.assertEqual(_junit(report), {'a': 'run', 'b': 'fail'})
            for text in ('<testsuite', '<testsuite/>', '<testsuite><testcase name="a" status="run"/><testcase name="a" status="fail"/></testsuite>',
                         '<testsuite><testcase name="a" status="notrun"/></testsuite>'):
                with self.subTest(report=text), self.assertRaises(QualificationError):
                    report.write_text(text)
                    _junit(report)

    def test_rejects_a_result_without_a_case_name(self) -> None:
        with workspace() as directory:
            report = directory / 'report.xml'
            for attributes in ('status="run"', 'name="" status="run"'):
                with self.subTest(attributes=attributes):
                    report.write_text(f'<testsuite><testcase {attributes}/></testsuite>')
                    with self.assertRaisesRegex(QualificationError, 'upstream report has invalid test cases'):
                        _junit(report)


    def test_reports_jaq_process_and_output_failures(self) -> None:
        with workspace() as directory:
            report = directory / 'report.xml'
            for failure in (OSError('fixture tool missing'), subprocess.TimeoutExpired(['jaq'], 60)):
                with (
                    self.subTest(failure=failure),
                    patch.object(qualify.subprocess, 'run', side_effect=failure),
                    self.assertRaises(QualificationError) as error,
                ):
                    _junit(report)
                self.assertEqual(str(error.exception), f'cannot run jaq for upstream report: {failure}')
            with (
                patch.object(qualify.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 8, '[]', 'fixture invalid XML',
                )) as run,
                self.assertRaisesRegex(QualificationError, '^cannot parse upstream report: fixture invalid XML$'),
            ):
                _junit(report)
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ['jaq', '--from', 'xml', '--slurp'])
            self.assertEqual(len(command), 6)
            self.assertEqual(command[-1], str(report))
            self.assertEqual(run.call_args.kwargs['timeout'], 60)
            for output in ('...', '{}', '[42]', '[{"name":"a","status":null}]'):
                with (
                    self.subTest(output=output),
                    patch.object(qualify.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, '')),
                    self.assertRaisesRegex(QualificationError, '^upstream report '),
                ):
                    _junit(report)


class QualificationSectionTests(unittest.TestCase):
    def test_replaces_only_the_requested_section_and_cleans_scratch(self) -> None:
        with workspace() as root:
            scratch = root / '.work/tmp'
            scratch.mkdir(parents=True)
            report = root / 'docs/qualification.md'
            report.parent.mkdir()
            marker = '## Latest upstream subset: aarch64-unknown-linux-musl'
            initial = (
                '# Qualification\n\n## Intro\n\nFixture note.\n\n'
                f'{marker}\n\nOld receipt.\n\n## Retained checks\n\nUnrelated receipt.\n'
            )
            report.write_text(initial, encoding='utf-8')
            qualify._write_section(root, marker, 'Verified receipt.\n')
            expected = initial.replace('Old receipt.', 'Verified receipt.')
            self.assertEqual(report.read_text(encoding='utf-8'), expected)
            self.assertEqual(list(scratch.iterdir()), [])
            self.assertEqual(report.read_text(encoding='utf-8').count(marker), 1)
            qualify._write_section(root, '## New evidence', 'Independent receipt.')
            self.assertTrue(report.read_text(encoding='utf-8').endswith('\n\n## New evidence\n\nIndependent receipt.\n'))
            self.assertEqual(list(scratch.iterdir()), [])

    def test_failed_publication_preserves_previous_report_and_removes_scratch(self) -> None:
        with workspace() as root:
            scratch = root / '.work/tmp'
            scratch.mkdir(parents=True)
            report = root / 'docs/qualification.md'
            report.parent.mkdir()
            original = b'# Qualification\n\nPrior evidence.\n'
            report.write_bytes(original)

            def reject(staged: Path, destination: Path) -> None:
                self.assertEqual(staged.parent, scratch)
                self.assertEqual(destination, report)
                self.assertEqual(staged.read_bytes(), original + b'\n## Candidate\n\nNew evidence.\n')
                raise PermissionError('fixture cannot replace report')

            with (
                patch.object(Path, 'replace', autospec=True, side_effect=reject),
                self.assertRaisesRegex(PermissionError, '^fixture cannot replace report$'),
            ):
                qualify._write_section(root, '## Candidate', 'New evidence.')
            self.assertEqual(report.read_bytes(), original)
            self.assertEqual(list(scratch.iterdir()), [])


class UpstreamQualificationTests(unittest.TestCase):
    def test_requires_junit_case_count_to_match_the_child_summary(self) -> None:
        with workspace() as root:
            machine = targets.target('aarch64-unknown-linux-musl')
            phase = root / 'stage'
            candidate = phase / 'bin/cmake'
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b'candidate')
            source_tree = root / '.work/build' / machine.triple / 'phases/cmake/build/bin'
            source_tree.mkdir(parents=True)
            (source_tree / 'cmake').write_bytes(b'previous binary')
            reference = source_tree.parents[1].with_name('reference')
            reference.mkdir()
            report = root / 'docs/qualification.md'
            report.parent.mkdir()
            original = '# Qualification\n\nPrior verification.\n'
            report.write_text(original)
            subset = root / 'tests/upstream-subset.txt'
            subset.parent.mkdir()
            subset.write_text('^Build\\.Verify$\n', encoding='utf-8')
            build_root = f'/src/.work/build/{machine.triple}/phases'
            prepare = f'{build_root}/prepare'
            outcomes = {'cmake': (2, 'run', 0), 'reference': (1, 'fail', 1)}

            def run_child(image, command, *, target, mounts: list[tuple[Path, str]], **options):
                self.assertEqual((image, command, target), ('fixture', ['python3', '/suite/upstream.py'], machine))
                mounted = {destination: path for path, destination in mounts}
                environment = options['env']
                name = environment['UPSTREAM_PHASE']
                phase_mount = f'{build_root}/{name}'
                expected_destinations = {
                    '/qualification', phase_mount, f'{build_root}/prepare', f'{build_root}/bootstrap',
                    f'/src/.work/rust/{machine.triple}/phases/staticlib', '/suite', '/selection/upstream-subset.txt',
                }
                if name == 'cmake':
                    candidate_mount = f'{phase_mount}/build/bin/cmake'
                    expected_destinations.add(candidate_mount)
                    self.assertEqual(mounted[candidate_mount], candidate)
                    self.assertEqual((mounted[phase_mount] / 'build/bin/cmake').read_bytes(), b'candidate')
                    self.assertEqual(mounted['/selection/upstream-subset.txt'], subset)
                else:
                    selection = mounted['/selection/upstream-subset.txt']
                    self.assertEqual(selection.read_text(), '^Build\\.Verify$\n')
                    self.assertTrue(mounted[phase_mount].is_dir())
                self.assertEqual(set(mounted), expected_destinations)
                self.assertEqual(options['read_only'], expected_destinations - {'/qualification', phase_mount})
                self.assertEqual((options['workdir'], options['timeout']), ('/qualification', 1260))
                self.assertEqual(environment['TMPDIR'], '/qualification/tmp')
                self.assertEqual(environment['CMAKE_BUILD_PARALLEL_LEVEL'], '8')
                self.assertEqual(environment['PATH'], f'{prepare}/toolchain/bin:{build_root}/bootstrap/ninja-build:/usr/bin:/bin')
                self.assertIn(prepare + '/sysroot', environment['CFLAGS'])
                self.assertIn(prepare + '/sysroot', environment['CXXFLAGS'])
                self.assertTrue((mounted['/qualification'] / 'tmp').is_dir())

                count, status, code = outcomes[name]
                if status != 'no-report':
                    (mounted['/qualification'] / 'upstream.xml').write_text(
                        f'<testsuite><testcase name="Build.Verify" status="{status}"/></testsuite>'
                    )
                summary = 'fixture unexpected stdout' if count is None else f'upstream subset: {count} tests executed\n'
                return sandbox.SealedResult(code, summary, 'fixture child stderr', 'none', {})

            with patch.object(sandbox, 'run_sealed', side_effect=run_child), redirect_stdout(io.StringIO()):
                for outcomes_to_reject, diagnostic in (
                    ({'cmake': (1, 'no-report', 0)}, '^cmake upstream subset produced no report:\nfixture child stderr$'),
                    ({'cmake': (None, 'run', 0)}, '^cmake upstream subset produced no report:\nfixture child stderr$'),
                    ({'cmake': (2, 'run', 0)}, '^cmake upstream summary reports 2 tests but JUnit contains 1$'),
                    ({'cmake': (1, 'fail', 0)}, '^cmake upstream result disagrees with its report:'),
                    ({'cmake': (1, 'fail', 1), 'reference': (2, 'fail', 1)}, '^reference upstream summary reports 2 tests but JUnit contains 1$'),
                ):
                    with self.subTest(outcomes=outcomes_to_reject), self.assertRaisesRegex(QualificationError, diagnostic):
                        outcomes.update(outcomes_to_reject)
                        qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                    self.assertEqual(report.read_text(), original)
                outcomes.update(cmake=(1, 'run', 0), reference=(1, 'fail', 1))
                qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                self.assertIn('Executed 1 tests. 1 passed.', report.read_text())
                self.assertTrue(report.read_text().startswith(original))
                outcomes['cmake'] = (1, 'fail', 1)
                qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                content = report.read_text()
                self.assertTrue(content.startswith(original))
                self.assertEqual(content.count('## Latest upstream subset:'), 1)
                self.assertIn('Executed 1 tests. 0 passed.', content)
                self.assertIn('- `Build.Verify`', content)


if __name__ == '__main__':
    unittest.main()
