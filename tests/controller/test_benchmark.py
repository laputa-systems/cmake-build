from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from buildsys import benchmark
from buildsys.inputs import Input


class BenchmarkTests(unittest.TestCase):
    def test_fewer_than_five_repetitions_cannot_bypass_budgets(self) -> None:
        from pathlib import Path

        from buildsys.targets import native_target
        with patch.object(benchmark.platform, 'system', return_value='Linux'), self.assertRaisesRegex(benchmark.BenchmarkError, 'at least five'):
            benchmark.run(Path('/not-a-workspace'), native_target(), 4)

    def test_interleaving_rotates_each_baseline_through_each_position(self) -> None:
        single_order = list(benchmark.interleaved_orders(('product', 'musl', 'kitware'), 1))
        self.assertEqual(single_order, [('product', 'musl', 'kitware')])
        orders = list(benchmark.interleaved_orders(('product', 'musl', 'kitware'), 12))
        self.assertEqual(len(orders), 12)
        self.assertEqual(
            orders[:3],
            [('product', 'musl', 'kitware'), ('musl', 'kitware', 'product'), ('kitware', 'product', 'musl')],
        )
        for index in range(3):
            self.assertEqual({order[index] for order in orders}, {'product', 'musl', 'kitware'})
        self.assertTrue(all(set(order) == {'product', 'musl', 'kitware'} for order in orders))

    def test_interleaving_rejects_invalid_variants_and_repetition_counts(self) -> None:
        for variants, repetitions in (((), 1), (('product', 'product'), 2), (('product',), 0)):
            with self.subTest(variants=variants, repetitions=repetitions), self.assertRaises(benchmark.BenchmarkError) as caught:
                list(benchmark.interleaved_orders(variants, repetitions))
            self.assertEqual(str(caught.exception), 'invalid benchmark variants or repetitions')

    def test_report_independently_rejects_invalid_sample_values(self) -> None:
        sample: benchmark.Measurement = {
            'variant': 'product', 'workload': 'fmt', 'scenario': 'initial',
            'iteration': 0, 'seconds': 1.0, 'cpu_seconds': 0.5, 'max_rss_kib': 1,
            'exit_code': 0, 'load_before': 0.0, 'load_after': 0.0,
        }
        cases: tuple[benchmark.Measurement, ...] = (
            {**sample, 'seconds': float('inf')},
            {**sample, 'seconds': float('nan')},
            {**sample, 'seconds': -0.5},
            {**sample, 'max_rss_kib': -1},
            {**sample, 'exit_code': 1},
            {**sample, 'seconds': True},
            {**sample, 'seconds': 10 ** 400},
            {**sample, 'cpu_seconds': float('inf')},
            {**sample, 'cpu_seconds': -0.25},
            {**sample, 'load_before': float('nan')},
            {**sample, 'load_after': -0.25},
            {**sample, 'load_after': float('inf')},
            {**sample, 'iteration': True},
            {**sample, 'iteration': -1},
            {**sample, 'max_rss_kib': False},
            {**sample, 'exit_code': False},
        )
        for record in cases:
            with self.subTest(record=record), self.assertRaises(benchmark.BenchmarkError) as caught:
                benchmark.summarize([record], 1)
            self.assertEqual(str(caught.exception), 'benchmark contains a failed or invalid measurement')

    def test_report_rejects_missing_or_failed_measurements(self) -> None:
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.summarize([{'variant': 'product', 'workload': 'fmt', 'scenario': 'initial',
                                  'iteration': 0, 'seconds': 1.0, 'cpu_seconds': 0.5,
                                  'max_rss_kib': 1, 'exit_code': 1,
                                  'load_before': 0.0, 'load_after': 0.0}], 1)
        with self.assertRaisesRegex(benchmark.BenchmarkError, '^benchmark produced no measurements$'):
            benchmark.summarize([], 10)

    def test_report_requires_every_variant_and_scenario(self) -> None:
        scenarios = [(workload, scenario) for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
                     for scenario in ('initial', 'unchanged', 'cmakelists-edit', 'option-change')]
        scenarios += [('process', 'version'), ('process', 'script')]
        records: list[benchmark.Measurement] = [
            {'workload': workload, 'scenario': scenario, 'variant': variant, 'iteration': 0,
             'seconds': 1.0, 'cpu_seconds': 0.5, 'max_rss_kib': 42, 'exit_code': 0,
             'load_before': 0.12, 'load_after': 0.34}
            for workload, scenario in scenarios for variant in ('product', 'musl', 'kitware')
        ]
        self.assertEqual(len(benchmark.summarize(records, 1)), 54)
        bounded: list[benchmark.Measurement] = [
            {**records[0], 'seconds': 0.0, 'cpu_seconds': sys.float_info.max, 'max_rss_kib': 0}, *records[1:],
        ]
        self.assertEqual(
            benchmark.summarize(bounded, 1)[('fmt', 'initial', 'product')],
            {'median_seconds': 0.0, 'median_cpu_seconds': sys.float_info.max, 'min_seconds': 0.0,
             'max_seconds': 0.0, 'max_rss_kib': 0},
        )
        even: list[benchmark.Measurement] = [
            {**record, 'iteration': iteration, 'seconds': sys.float_info.max, 'cpu_seconds': sys.float_info.max}
            for record in records for iteration in range(6)
        ]
        report = benchmark.summarize(even, 6)[('fmt', 'initial', 'product')]
        self.assertEqual(report['median_seconds'], sys.float_info.max)
        self.assertEqual(report['median_cpu_seconds'], sys.float_info.max)
        ordinary: list[benchmark.Measurement] = [
            {**record, 'seconds': float(record['iteration']), 'cpu_seconds': record['iteration'] / 2}
            for record in even
        ]
        report = benchmark.summarize(ordinary, 6)[('fmt', 'initial', 'product')]
        self.assertEqual(report['median_seconds'], 2.5)
        self.assertEqual(report['median_cpu_seconds'], 1.25)
        with self.assertRaisesRegex(benchmark.BenchmarkError, '^benchmark contains a failed or invalid measurement$'):
            benchmark.summarize([{**records[0], 'cpu_seconds': float('nan')}, *records[1:]], 1)
        measured: list[benchmark.Measurement] = [
            {**record, 'iteration': iteration, 'seconds': seconds, 'cpu_seconds': cpu, 'max_rss_kib': rss}
            for record in records
            for iteration, seconds, cpu, rss in ((0, 3.0, 0.25, 60), (1, 2.0, 1.5, 44), (2, 9.0, 3.5, 57))
        ]
        self.assertEqual(
            benchmark.summarize(measured, 3)[('fmt', 'initial', 'product')],
            {'median_seconds': 3.0, 'median_cpu_seconds': 1.5, 'min_seconds': 2.0, 'max_seconds': 9.0, 'max_rss_kib': 60},
        )
        for samples, repetitions in ((measured, 0), (measured + measured[:1], 3), (measured[:-1] + measured[-2:-1], 3)):
            with self.subTest(length=len(samples), repetitions=repetitions), self.assertRaises(benchmark.BenchmarkError) as caught:
                benchmark.summarize(samples, repetitions)
            self.assertRegex(str(caught.exception), '^benchmark produced no measurements$|^incomplete benchmark samples: ')
        with self.assertRaises(benchmark.BenchmarkError) as missing:
            benchmark.summarize(records[:-1], 1)
        self.assertEqual(str(missing.exception), "benchmark scenario coverage differs: missing [('process', 'script', 'kitware')]")

        profiles: list[benchmark.Profile] = [
            {'workload': workload, 'variant': variant, 'summary': f'trace for {workload}/{variant}\n\n'}
            for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
            for variant in ('product', 'musl', 'kitware')
        ]
        metadata: benchmark.ReportMetadata = {
            'target': 'aarch64-unknown-linux-musl', 'host': 'Linux arm64',
            'cpu_model': 'fixture CPU', 'container': 'fixture image', 'cpus': [0, 2],
            'archive_sha256': 'product-hash', 'official_sha256': 'kitware-hash', 'baseline_digest': 'musl-hash',
            'cmake_sha256': 'source-hash', 'toolchain_sha256': 'tools-hash',
            'strace_version': 'fixture strace', 'runner_sha256': 'runner-hash', 'implementation_sha256': 'impl-hash',
            'rss_implementation_sha256': 'rss-hash', 'profiles': profiles,
            'projects': [Input(name='fmt', version='1', sha256='e', urls=('https://example.invalid/fmt',))],
            'sizes': {
                'product': {'executable': 10, 'files': 20, 'archive': 5},
                'musl': {'executable': 12, 'files': 22, 'archive': 'not packaged'},
                'kitware': {'executable': 15, 'files': 26, 'archive': 9},
            },
        }
        report = benchmark.render(measured, 3, metadata)
        self.assertTrue(report.startswith(
            '# CMake executable performance\n\n'
            'Target: `aarch64-unknown-linux-musl`. Runs per variant: 3.\n\n'
        ))
        for evidence in (
            (
                'All three binaries ran in the same native Debian container with the pinned musl toolchain.\n'
                'Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource\n'
                'differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with\n'
                'OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those\n'
                'product differences and does not isolate an individual compiler flag.\n'
                'A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not\n'
                'measured. Timings are not release gates.\n\n'
            ),
            'Host: `Linux arm64`. CPU: `fixture CPU`. Container: `fixture image`.',
            'CPU affinity: `[0, 2]`. Product archive SHA-256: `product-hash`.',
            'Official archive SHA-256: `kitware-hash`. Baseline output digest: `musl-hash`.',
            'CMake source SHA-256: `source-hash`. Toolchain SHA-256: `tools-hash`.',
            'Tracer: `fixture strace`. Runner SHA-256: `runner-hash`.',
            'Benchmark implementation SHA-256: `impl-hash`.',
            'RSS measurement implementation SHA-256: `rss-hash`.',
            (
                'See the [baseline analysis](performance-analysis.md) for the interpretation and limits of the initial run.\n\n'
                '| Project | Version | Source SHA-256 |\n| --- | --- | --- |\n| fmt | 1 | `e` |'
            ),
            (
                '\n\n## Size\n\n'
                'The official archive includes additional tools and resources, so total package sizes are not like-for-like.\n\n'
                '| Variant | CMake executable bytes | Regular-file bytes | Archive bytes |\n| --- | ---: | ---: | ---: |\n'
                '| product | 10 | 20 | 5 |\n| musl | 12 | 22 | not packaged |\n| kitware | 15 | 26 | 9 |'
            ),
            (
                '\n\n## Measurements\n\n'
                "RSS is CMake's image high-water mark, read before exit; it excludes child processes.\n"
                'Configure timings include process-tracing overhead. Startup timings are untraced; their RSS\n'
                'comes from a separate traced invocation. CPU time includes waited child processes.\n\n'
                '| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |\n'
                '| --- | --- | --- | ---: | ---: | ---: | ---: |\n'
            ),
            '| fmt | initial | product | 3.000000 | 2.000000–9.000000 | 1.500000 | 60 |',
            (
                '\n\n## Raw samples\n\n'
                'Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.\n\n'
                '| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |\n'
                '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
                '| fmt | initial | product | 1 | 3.000000 | 0.250000 | 60 | 0.12 | 0.34 |\n'
                '| fmt | initial | product | 2 | 2.000000 | 1.500000 | 44 | 0.12 | 0.34 |\n'
                '| fmt | initial | product | 3 | 9.000000 | 3.500000 | 57 | 0.12 | 0.34 |'
            ),
            (
                '\n\n## File and process syscall profiles\n\n'
                'These untimed `strace -f -c` profiles cover an unchanged reconfigure after the\n'
                'measured runs. They include child processes and use a host tracer, not the release binary.\n'
                'Tracing changes execution cost; its syscall times are not untraced wall-time shares.\n'
                'Kernel sampling with `perf` is not collected by this command.\n\n'
                '### fmt: product\n\n```text\ntrace for fmt/product\n```'
            ),
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, report)
        self.assertTrue(report.endswith('```\n'))
        metadata['profiles'] = profiles + profiles[:1]
        with self.assertRaisesRegex(benchmark.BenchmarkError, '^file and process profiles are incomplete$'):
            benchmark.render(records, 1, metadata)
        metadata['profiles'] = profiles[:-1]
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.render(records, 1, metadata)
