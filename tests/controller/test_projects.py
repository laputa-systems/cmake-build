from __future__ import annotations

import unittest

from helpers import workspace

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


if __name__ == '__main__':
    unittest.main()
