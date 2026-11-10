import unittest

from buildsys import budgets
from helpers import workspace


class SizeBudgetTests(unittest.TestCase):
    def test_size_budget_checks_exact_packaged_bytes(self) -> None:
        with workspace() as root:
            tree = root / 'tree'
            (tree / 'usr/bin').mkdir(parents=True)
            executable = tree / 'usr/bin/cmake'
            executable.write_bytes(b'x' * 10)
            (tree / 'usr/metadata').write_bytes(b'y' * 5)
            archive = root / 'package.tar.xz'
            archive.write_bytes(b'z' * 15)
            document = {'schema_version': 1, 'targets': {'test': {'metrics': {
                'executable_bytes': {'value': 10, 'allowed_regression': 0},
                'unpacked_bytes': {'value': 15, 'allowed_regression': 0},
                'archive_bytes': {'value': 15, 'allowed_regression': 0},
            }}}}
            budgets.check_size(document, 'test', tree, archive)
            executable.write_bytes(b'x' * 11)
            with self.assertRaises(budgets.BudgetError):
                budgets.check_size(document, 'test', tree, archive)
            executable.write_bytes(b'x' * 10)
            archive.write_bytes(b'z' * 16)
            with self.assertRaises(budgets.BudgetError):
                budgets.check_size(document, 'test', tree, archive)
            document['targets']['test']['metrics']['archive_bytes']['allowed_regression'] = 1
            budgets.check_size(document, 'test', tree, archive)
            (tree / 'usr/metadata').write_bytes(b'y' * 6)
            with self.assertRaises(budgets.BudgetError):
                budgets.check_size(document, 'test', tree, archive)

    def test_missing_or_invalid_budget_fails(self) -> None:
        with workspace() as root:
            with self.assertRaises(budgets.BudgetError):
                budgets.check_size({'schema_version': 1, 'targets': {}}, 'test', root, root / 'archive')
            with self.assertRaises(budgets.BudgetError):
                budgets.check_size({'schema_version': 9, 'targets': {}}, 'test', root, root / 'archive')

    def test_memory_regression_requires_five_samples_and_exceeds_observed_spread(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        document = {'schema_version': 1, 'targets': {'test': {'metrics': {
            f'{name}_initial_rss_kib': {'value': 100, 'allowed_regression': 3} for name in workloads
        }}}}
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': 100}
                   for name in workloads for _ in range(5)]
        self.assertEqual(budgets.check_memory(document, 'test', records)['fmt_initial_rss_kib'], 100)
        records[0]['max_rss_kib'] = 200
        budgets.check_memory(document, 'test', records)
        for record in records:
            if record['workload'] == 'fmt':
                record['max_rss_kib'] = 120
        with self.assertRaises(budgets.BudgetError):
            budgets.check_memory(document, 'test', records)
        records[0]['max_rss_kib'] = 300
        with self.assertRaises(budgets.BudgetError):
            budgets.check_memory(document, 'test', records)
        with self.assertRaises(budgets.BudgetError):
            budgets.check_memory(document, 'test', records[:4])

    def test_memory_baseline_is_initialized_only_for_the_recorded_archive(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': 100}
                   for name in workloads for _ in range(5)]
        document = {'schema_version': 1, 'targets': {'test': {
            'archive_sha256': 'a' * 64, 'memory_status': 'unmeasured', 'metrics': {}}}}
        with self.assertRaises(budgets.BudgetError):
            budgets.apply_memory(document, 'test', 'b' * 64, records)
        self.assertTrue(budgets.apply_memory(document, 'test', 'a' * 64, records))
        before = document['targets']['test']['metrics']['fmt_initial_rss_kib'].copy()
        for record in records:
            record['max_rss_kib'] = 90
        self.assertFalse(budgets.apply_memory(document, 'test', 'b' * 64, records))
        self.assertEqual(document['targets']['test']['metrics']['fmt_initial_rss_kib'], before)
        del document['targets']['test']['metrics']['fmt_initial_rss_kib']
        with self.assertRaises(budgets.BudgetError):
            budgets.validate_memory_source(document, 'test', 'b' * 64)

    def test_release_memory_evidence_requires_a_measured_budget_and_five_samples(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': 100}
                   for name in workloads for _ in range(5)]
        document = {'schema_version': 1, 'targets': {'test': {
            'archive_sha256': 'a' * 64, 'memory_status': 'unmeasured', 'metrics': {}}}}
        with self.assertRaises(budgets.BudgetError):
            budgets.release_evidence(document, 'test', 'a' * 64, 1000, 'b' * 64, 5, records)
        budgets.apply_memory(document, 'test', 'a' * 64, records)
        with self.assertRaises(budgets.BudgetError):
            budgets.release_evidence(document, 'test', 'a' * 64, 1000, 'b' * 64, 4, records)
        evidence = budgets.release_evidence(document, 'test', 'a' * 64, 1000, 'b' * 64, 5, records)
        self.assertEqual(evidence['archive_sha256'], 'a' * 64)
        self.assertEqual(evidence['budget_sha256'], 'b' * 64)
        self.assertEqual(evidence['measurements']['fmt_initial_rss_kib'], 100)
        self.assertEqual(evidence['result'], 'passed')
