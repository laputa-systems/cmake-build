from __future__ import annotations

import unittest
from types import SimpleNamespace

from buildsys import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_interleaving_rotates_each_baseline_through_each_position(self) -> None:
        orders = list(benchmark.interleaved_orders(('product', 'musl', 'kitware'), 12))
        self.assertEqual(len(orders), 12)
        for index in range(3):
            self.assertEqual({order[index] for order in orders}, {'product', 'musl', 'kitware'})
        self.assertTrue(all(set(order) == {'product', 'musl', 'kitware'} for order in orders))

    def test_report_rejects_missing_or_failed_measurements(self) -> None:
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.summarize([{'variant': 'product', 'scenario': 'initial', 'seconds': 1.0,
                                  'max_rss_kib': 1, 'exit_code': 1}], 1)
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.summarize([], 10)

    def test_report_requires_every_variant_and_scenario(self) -> None:
        scenarios = [(workload, scenario) for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
                     for scenario in ('initial', 'unchanged', 'cmakelists-edit', 'option-change')]
        scenarios += [('process', 'version'), ('process', 'script')]
        records = [{'workload': workload, 'scenario': scenario, 'variant': variant, 'iteration': 0,
                    'seconds': 1.0, 'cpu_seconds': 0.5, 'max_rss_kib': 42, 'exit_code': 0}
                   for workload, scenario in scenarios for variant in ('product', 'musl', 'kitware')]
        self.assertEqual(len(benchmark.summarize(records, 1)), 54)
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.summarize(records[:-1], 1)

        profiles = [{'workload': workload, 'variant': variant, 'summary': 'total'}
                    for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
                    for variant in ('product', 'musl', 'kitware')]
        metadata = {'target': 'test', 'host': 'test', 'container': 'test', 'cpus': [0],
                    'archive_sha256': 'a', 'official_sha256': 'b', 'baseline_digest': 'c',
                    'strace_version': 'test', 'runner_sha256': 'd', 'profiles': profiles,
                    'projects': [SimpleNamespace(name='fmt', version='1', sha256='e')],
                    'sizes': {variant: {'executable': 1, 'files': 2, 'archive': 3}
                              for variant in ('product', 'musl', 'kitware')}}
        for record in records:
            record.update(load_before=0.0, load_after=0.0)
        self.assertIn('## Raw samples', benchmark.render(records, 1, metadata))
        metadata['profiles'] = profiles[:-1]
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.render(records, 1, metadata)
