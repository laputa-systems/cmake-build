import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from buildsys import bench


class BenchTests(unittest.TestCase):
    def test_selection_and_exclusions(self):
        selected, excluded = bench.select('edit', [], [], [])
        self.assertEqual(selected, ['controller'])
        self.assertEqual(excluded['release-matrix'], 'above tier ceiling')
        self.assertEqual(bench.select('full', [], ['cmake'], [])[0], ['release-matrix'])
        self.assertEqual(bench.select('full', ['controller'], [], [])[0], ['controller'])
        for args in [('full', ['cmake'], [], []), ('full', [], ['controller'], []),
                     ('edit', [], [], ['controller']), ('edit', ['release-matrix'], [], [])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                bench.select(*args)

    def test_preflight_failure_runs_nothing(self):
        with patch.object(bench.platform, 'system', return_value='Darwin'), \
             patch.object(bench.platform, 'platform', return_value='fixture host'), \
             patch.object(bench.subprocess, 'run') as run, \
             patch.object(sys, 'argv', ['bench', '--workload', 'release-matrix']):
            self.assertEqual(bench.main(), 1)
            run.assert_not_called()

    def test_preflight_calls_coordinator_admission(self):
        from buildsys import benchmark, targets

        with patch.object(bench.platform, 'system', return_value='Linux'), \
             patch.object(bench.platform, 'machine', return_value='x86_64'), \
             patch.object(bench.shutil, 'which', return_value='/tool'), \
             patch.object(benchmark, 'admit', side_effect=benchmark.BenchmarkError('invalid archive')) as admit:
            failures = bench.preflight(['release-matrix'], None)
            admit.assert_called_once_with(bench.ROOT, targets.target('x86_64-unknown-linux-musl'))
            self.assertTrue(any('invalid archive' in failure for failure in failures))

    def test_dry_run_writes_nothing(self):
        with patch.object(bench.Path, 'mkdir') as mkdir, \
             patch.object(bench.subprocess, 'run') as run, \
             patch.object(sys, 'argv', ['bench', '--dry-run']):
            self.assertEqual(bench.main(), 0)
            mkdir.assert_not_called()
            run.assert_not_called()

    def test_edit_run_records_result(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, '-m', 'buildsys.bench', '--tier', 'edit'],
                                cwd=root, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        summary = Path(result.stdout.split('results: ')[1].strip()) / 'summary.json'
        self.assertIn('"exit_status": 0', summary.read_text())
