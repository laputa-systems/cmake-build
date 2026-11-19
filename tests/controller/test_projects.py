from __future__ import annotations

import io
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
            outcomes = {'cmake': (2, 'run', 0), 'reference': (1, 'fail', 1)}

            def run_child(image, command, *, target, mounts: list[tuple[Path, str]], **options):
                self.assertEqual((image, command, target), ('fixture', ['python3', '/suite/upstream.py'], machine))
                mounted = {destination: path for path, destination in mounts}
                name = options['env']['UPSTREAM_PHASE']
                if name == 'cmake':
                    copied = mounted[f'/src/.work/build/{machine.triple}/phases/cmake'] / 'build/bin/cmake'
                    self.assertEqual(copied.read_bytes(), b'candidate')
                else:
                    selection = mounted['/selection/upstream-subset.txt']
                    self.assertEqual(selection.read_text(), '^Build$\n')
                count, status, code = outcomes[name]
                (mounted['/qualification'] / 'upstream.xml').write_text(
                    f'<testsuite><testcase name="Build" status="{status}"/></testsuite>'
                )
                return sandbox.SealedResult(code, f'upstream subset: {count} tests executed\n', '', 'none', {})

            with patch.object(sandbox, 'run_sealed', side_effect=run_child), redirect_stdout(io.StringIO()):
                for outcomes_to_reject, diagnostic in (
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
                self.assertIn('- `Build`', content)


if __name__ == '__main__':
    unittest.main()
