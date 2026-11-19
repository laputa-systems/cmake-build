from __future__ import annotations

import io
import json
import re
import subprocess
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import archive, file_sha256, workspace, write_lock

from buildsys import inputs, qualify, sandbox, targets
from buildsys.qualify import QualificationError, _check_baseline_failures, _junit


class BasicQualificationTests(unittest.TestCase):
    def test_relocates_candidate_and_checks_sealed_execution_result(self) -> None:
        target = targets.target('x86_64-unknown-linux-musl')
        for code in (0, 9):
            with self.subTest(code=code), workspace() as root:
                if code:
                    (root / '.work/tmp').mkdir(parents=True)
                phase = root / 'candidate'
                executable = phase / 'bin/cmake'
                executable.parent.mkdir(parents=True)
                executable.write_bytes(b'candidate')
                (phase / 'bin/cpack').symlink_to('cmake')
                for state in ('phase.json', 'state.json'):
                    (phase / state).write_text('controller state', encoding='utf-8')

                def run_child(image, command, *, mounts: list[tuple[Path, str]], exit_code=code, **options):
                    paths = {destination: path for path, destination in mounts}
                    prefix = paths['/qualification']
                    relocated = prefix / 'relocated cmake'
                    phases = root / '.work/build' / target.triple / 'phases'
                    prepare = f'/src/.work/build/{target.triple}/phases/prepare'
                    self.assertEqual(prefix.parent, root / '.work/tmp')
                    self.assertEqual({entry.name for entry in prefix.iterdir()}, {'relocated cmake'})
                    self.assertEqual(paths, {
                        '/qualification': prefix,
                        '/qualification/relocated cmake': relocated,
                        '/suite': root / 'tests/acceptance/basic',
                        prepare: phases / 'prepare',
                        '/tools/toolchain.cmake': phases / 'bootstrap/toolchain.cmake',
                        '/tools/ninja': phases / 'bootstrap/ninja-build/ninja',
                    })
                    self.assertEqual((relocated / 'bin/cmake').read_bytes(), b'candidate')
                    self.assertTrue((relocated / 'bin/cpack').is_symlink())
                    self.assertEqual((relocated / 'bin/cpack').readlink(), Path('cmake'))
                    self.assertEqual({entry.name for entry in relocated.iterdir()}, {'bin'})
                    self.assertEqual((image, command), ('fixture-image', ['python3', '/suite/run.py']))
                    self.assertEqual(options, {
                        'target': target, 'env': {'TMPDIR': '/qualification'},
                        'workdir': '/qualification', 'timeout': 1800,
                        'read_only': frozenset(paths) - {'/qualification'},
                    })
                    return sandbox.SealedResult(exit_code, 'fixture stdout\n', 'fixture stderr', 'none', {})

                error = nullcontext() if code == 0 else self.assertRaisesRegex(
                    QualificationError, r'^basic qualification failed \(9\):\nfixture stderr$',
                )
                with (
                    patch.object(sandbox, 'run_sealed', side_effect=run_child) as sealed,
                    redirect_stdout(io.StringIO()) as stdout,
                    error,
                ):
                    qualify.basic(root=root, phase=phase, image='fixture-image', target=target)
                self.assertEqual(stdout.getvalue(), 'fixture stdout\n')
                self.assertEqual(sealed.call_count, 1)
                self.assertEqual(list((root / '.work/tmp').iterdir()), [])
                self.assertTrue((phase / 'phase.json').is_file())
                self.assertTrue((phase / 'state.json').is_file())


class ProjectQualificationTests(unittest.TestCase):
    def test_checks_locked_sources_relocated_stage_and_every_project_result(self) -> None:
        target = targets.target('x86_64-unknown-linux-musl')
        projects = {
            'fmt-source': ('fmt: built and passed ', '1 case'),
            'zstd-source': ('zstd: built and passed ', '2 cases'),
            'libjpeg-turbo-source': ('libjpeg-turbo: built and passed ', '3 cases'),
            'llvm-project-source': ('LLVM with Clang: configured and generated', ''),
        }
        with workspace() as root:
            lock = root / 'sources.lock.json'
            entries: list[dict[str, object]] = []
            packages = {}
            for name in projects:
                package = archive(root / f'{name}.tar.gz', [('source.txt', name.encode(), None)])
                packages[name] = package
                entries.append({'name': name, 'version': '1', 'role': 'test', 'target': 'all',
                                'url': f'https://example.invalid/{name}.tar.gz', 'sha256': file_sha256(package),
                                'size': package.stat().st_size})
            write_lock(lock, entries)
            cache = inputs.Cache(root / '.work/cache', offline=True)
            locked_sources = inputs.load_sources(lock)
            for item in locked_sources:
                cache.store(packages[item.name], item)

            phase = root / 'candidate'
            (phase / 'bin').mkdir(parents=True)
            (phase / 'bin/cmake').write_bytes(b'candidate')
            (phase / 'bin/ctest').symlink_to('cmake')
            for state in ('phase.json', 'state.json'):
                (phase / state).write_text('controller state')
            phases = root / '.work/build' / target.triple / 'phases'
            prepare = f'/src/.work/build/{target.triple}/phases/prepare'

            for code, omitted in [(0, ''), (7, ''), *((0, name) for name in projects)]:
                log = ''.join(f'{marker}{detail}\n' for name, (marker, detail) in projects.items() if name != omitted)
                reply = sandbox.SealedResult(code, log, 'build failed', 'none', {})
                message = f'real project qualification failed ({code}):\nbuild failed' if code else ''
                if omitted:
                    message = f'real project qualification missing result: {projects[omitted][0]}'

                def run(image, command, *, mounts, response=reply, **options):
                    paths = {destination: source for source, destination in mounts}
                    work = paths['/qualification']
                    stage = work / 'relocated cmake'
                    self.assertEqual(work.parent, root / '.work/tmp')
                    self.assertEqual({entry.name for entry in work.iterdir()}, {'relocated cmake'})
                    self.assertEqual((stage / 'bin/cmake').read_bytes(), b'candidate')
                    self.assertEqual((stage / 'bin/ctest').readlink(), Path('cmake'))
                    self.assertEqual({entry.name for entry in stage.iterdir()}, {'bin'})
                    self.assertEqual(paths, {
                        '/qualification': work, '/qualification/relocated cmake': stage,
                        '/suite': root / 'tests/projects', prepare: phases / 'prepare',
                        '/tools/toolchain.cmake': phases / 'bootstrap/toolchain.cmake',
                        '/tools/ninja': phases / 'bootstrap/ninja-build/ninja',
                        **{f'/inputs/{name}': phases / f'project-{name}/source' for name in projects},
                    })
                    for name in projects:
                        self.assertEqual((paths[f'/inputs/{name}'] / 'source.txt').read_text(), name)
                    self.assertEqual((image, command), ('fixture-image', ['python3', '/suite/run.py']))
                    self.assertEqual(options, {
                        'target': target, 'env': {'TMPDIR': '/qualification'}, 'workdir': '/qualification',
                        'timeout': 7200, 'read_only': frozenset(paths) - {'/qualification'},
                    })
                    return response

                expected = self.assertRaisesRegex(QualificationError, f'^{re.escape(message)}$') if message else nullcontext()
                with (
                    self.subTest(code=code, omitted=omitted),
                    patch.object(sandbox, 'run_sealed', side_effect=run) as sealed,
                    redirect_stdout(io.StringIO()) as stdout,
                    expected,
                ):
                    qualify.projects(root=root, phase=phase, image='fixture-image', target=target)
                sealed.assert_called_once()
                self.assertEqual(stdout.getvalue(), log)
                self.assertEqual(list((root / '.work/tmp').iterdir()), [])
                for item in locked_sources:
                    record = json.loads((phases / f'project-{item.name}/phase.json').read_text())
                    self.assertEqual(record['inputs'], {
                        'source': item.sha256, 'implementation': file_sha256(Path(qualify.__file__)),
                    })

    def test_rejects_a_missing_project_source_before_starting_a_child(self) -> None:
        target = targets.target('x86_64-unknown-linux-musl')
        with workspace() as root, patch.object(sandbox, 'run_sealed') as sealed:
            write_lock(root / 'sources.lock.json', [])
            with self.assertRaisesRegex(QualificationError, '^project source fmt-source is missing from the lock$'):
                qualify.projects(root=root, phase=root / 'absent', image='fixture-image', target=target)
            sealed.assert_not_called()


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
            (source_tree / 'ctest').symlink_to('cmake')
            phases = source_tree.parents[2]
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
                results = mounted['/qualification']
                self.assertEqual(results.parent.parent, root / '.work/tmp')
                self.assertEqual({item.name for item in results.iterdir()}, {'tmp'})
                selection = mounted['/selection/upstream-subset.txt']
                expected_mounts = {
                    '/qualification': results, phase_mount: results.parent / f'{name}-phase',
                    f'{build_root}/prepare': phases / 'prepare', f'{build_root}/bootstrap': phases / 'bootstrap',
                    f'/src/.work/rust/{machine.triple}/phases/staticlib':
                        root / '.work/rust' / machine.triple / 'phases/staticlib',
                    '/suite': root / 'tests/projects', '/selection/upstream-subset.txt': selection,
                }
                if name == 'cmake':
                    candidate_mount = f'{phase_mount}/build/bin/cmake'
                    expected_mounts[candidate_mount] = candidate
                    self.assertEqual((mounted[phase_mount] / 'build/bin/cmake').read_bytes(), b'candidate')
                    self.assertEqual((mounted[phase_mount] / 'build/bin/ctest').readlink(), Path('cmake'))
                    self.assertEqual(selection, subset)
                else:
                    self.assertEqual(selection, results.parent / 'reference-selection.txt')
                    self.assertEqual(selection.read_text(), '^Build\\.Verify$\n^Other\\[Case\\]$\n')
                    self.assertTrue(mounted[phase_mount].is_dir())
                self.assertEqual(mounted, expected_mounts)
                self.assertEqual(options['read_only'], set(expected_mounts) - {'/qualification', phase_mount})
                self.assertEqual((options['workdir'], options['timeout']), ('/qualification', 1260))
                self.assertEqual(environment['TMPDIR'], '/qualification/tmp')
                self.assertEqual(environment['CMAKE_BUILD_PARALLEL_LEVEL'], '8')
                self.assertEqual(environment['PATH'], f'{prepare}/toolchain/bin:{build_root}/bootstrap/ninja-build:/usr/bin:/bin')
                self.assertEqual(environment['CC'], f'{prepare}/toolchain/bin/clang')
                self.assertIn(prepare + '/sysroot', environment['CFLAGS'])
                self.assertIn(prepare + '/sysroot', environment['CXXFLAGS'])

                count, status, code = outcomes[name]
                if status != 'no-report':
                    cases = (
                        '<testcase name="Other[Case]" status="fail"/><testcase name="Build.Verify" status="fail"/>'
                        if status == 'two-fail' else f'<testcase name="Build.Verify" status="{status}"/>'
                    )
                    (results / 'upstream.xml').write_text(f'<testsuite>{cases}</testsuite>')
                summary = 'fixture unexpected stdout' if count is None else (
                    f'child setup\nupstream subset: {count} tests executed\nchild done\n'
                )
                return sandbox.SealedResult(code, summary, 'fixture child stderr', 'none', {})

            copy = qualify.shutil.copy2

            def corrupt_after_copy(source, destination):
                installed = copy(source, destination)
                Path(installed).write_bytes(b'wrong candidate')
                return installed

            with (
                patch.object(qualify.shutil, 'copy2', side_effect=corrupt_after_copy),
                patch.object(sandbox, 'run_sealed') as sealed,
                self.assertRaisesRegex(QualificationError, '^upstream test executable differs from the candidate$'),
            ):
                qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
            sealed.assert_not_called()
            self.assertEqual(report.read_text(), original)

            with patch.object(sandbox, 'run_sealed', side_effect=run_child), redirect_stdout(io.StringIO()) as stdout:
                for outcomes_to_reject, diagnostic in (
                    ({'cmake': (1, 'no-report', 0)}, '^cmake upstream subset produced no report:\nfixture child stderr$'),
                    ({'cmake': (None, 'run', 0)}, '^cmake upstream subset produced no report:\nfixture child stderr$'),
                    ({'cmake': (2, 'run', 0)}, '^cmake upstream summary reports 2 tests but JUnit contains 1$'),
                    ({'cmake': (1, 'fail', 0)}, '^cmake upstream result disagrees with its report:'),
                    ({'cmake': (2, 'two-fail', 1), 'reference': (3, 'two-fail', 1)}, '^reference upstream summary reports 3 tests but JUnit contains 2$'),
                ):
                    with self.subTest(outcomes=outcomes_to_reject), self.assertRaisesRegex(QualificationError, diagnostic):
                        outcomes.update(outcomes_to_reject)
                        qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                    self.assertEqual(report.read_text(), original)
                    self.assertEqual(list((root / '.work/tmp').iterdir()), [])
                stdout.seek(0)
                stdout.truncate()
                outcomes.update(cmake=(1, 'run', 0), reference=(1, 'fail', 1))
                qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                section = f'{original.rstrip()}\n\n## Latest upstream subset: {machine.triple}\n\n'
                identity = f'Executable SHA-256: `{file_sha256(candidate)}`.\n\n'
                self.assertEqual(report.read_text(), section + identity + 'Executed 1 tests. 1 passed.\n\nNo failures were observed.\n')
                self.assertEqual(stdout.getvalue(), (
                    'child setup\nupstream subset: 1 tests executed\nchild done\n'
                    'upstream: 1 tests, 0 shared baseline failures\n\n'
                ))
                outcomes.update(cmake=(2, 'two-fail', 1), reference=(2, 'two-fail', 1))
                qualify.upstream(root=root, phase=phase, image='fixture', target=machine)
                self.assertEqual(report.read_text(), section + identity + (
                    'Executed 2 tests. 0 passed.\n\n'
                    'The following failures also occurred in the unmodified static-PIE baseline:\n\n'
                    '- `Build.Verify`\n\n- `Other[Case]`\n'
                ))
                self.assertEqual((source_tree / 'cmake').read_bytes(), b'previous binary')
                self.assertEqual(list((root / '.work/tmp').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
