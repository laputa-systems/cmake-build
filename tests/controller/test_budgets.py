import json
import unittest

from helpers import ROOT, workspace

from buildsys import budgets


class SizeBudgetTests(unittest.TestCase):
    def test_reads_the_persisted_budget_document_and_reports_invalid_inputs(self) -> None:
        original = (ROOT / 'release-budgets.json').read_text(encoding='utf-8')
        valid = json.loads(original)
        with workspace() as root:
            budget_file = root / 'release-budgets.json'
            with self.assertRaisesRegex(budgets.BudgetError, 'cannot read release budgets:'):
                budgets.read(budget_file)
            budget_file.write_text(original, encoding='utf-8')
            self.assertEqual(budgets.read(budget_file), valid)
            for malformed in ('{', '[]', json.dumps(valid | {'schema_version': 9})):
                with self.subTest(document=malformed), self.assertRaisesRegex(budgets.BudgetError, 'cannot read release budgets:'):
                    budget_file.write_text(malformed, encoding='utf-8')
                    budgets.read(budget_file)

    def test_legacy_process_tree_rss_baseline_cannot_qualify_a_candidate(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        document = {'schema_version': 1, 'targets': {'test': {'memory_status': 'measured', 'metrics': {
            f'{name}_initial_rss_kib': {'value': 100, 'allowed_regression': 3} for name in workloads
        }}}}
        with self.assertRaises(budgets.BudgetError):
            budgets.validate_memory_source(document, 'test', 'a' * 64, 1000)

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
            for targets in (None, [], 'unavailable'):
                with self.subTest(targets=targets), self.assertRaisesRegex(budgets.BudgetError, '^release budgets lack target test$'):
                    budgets.check_size({'schema_version': 1, 'targets': targets}, 'test', root, root / 'archive')

    def test_memory_regression_requires_five_samples_and_exceeds_observed_spread(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        document = {'schema_version': 1, 'targets': {'test': {'rss_scope': budgets.RSS_SCOPE, 'metrics': {
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

    def test_memory_sample_without_rss_is_a_budget_error(self) -> None:
        records = [{'variant': 'product', 'workload': 'fmt', 'scenario': 'initial'}]
        with self.assertRaisesRegex(budgets.BudgetError, '^insufficient memory samples: fmt$'):
            budgets.memory_baseline(records)

    def test_memory_baseline_is_initialized_only_for_the_recorded_archive(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': 100}
                   for name in workloads for _ in range(5)]
        document = {'schema_version': 1, 'targets': {'test': {
            'archive_sha256': 'a' * 64, 'memory_archive_bytes': 1000, 'memory_status': 'unmeasured', 'metrics': {}}}}
        with self.assertRaises(budgets.BudgetError):
            budgets.apply_memory(document, 'test', 'b' * 64, 1000, records)
        with self.assertRaises(budgets.BudgetError):
            budgets.apply_memory(document, 'test', 'a' * 64, 999, records)
        with self.assertRaises(budgets.BudgetError):
            budgets.apply_memory(document, 'test', 'a' * 64, 1000, records + [records[0]])
        self.assertEqual(document['targets']['test']['memory_status'], 'unmeasured')
        self.assertTrue(budgets.apply_memory(document, 'test', 'a' * 64, 1000, records))
        self.assertEqual(document['targets']['test']['memory_repetitions'], 5)
        before = document['targets']['test']['metrics']['fmt_initial_rss_kib'].copy()
        for record in records:
            record['max_rss_kib'] = 90
        self.assertFalse(budgets.apply_memory(document, 'test', 'b' * 64, 999, records))
        self.assertEqual(document['targets']['test']['metrics']['fmt_initial_rss_kib'], before)
        del document['targets']['test']['metrics']['fmt_initial_rss_kib']
        with self.assertRaises(budgets.BudgetError):
            budgets.validate_memory_source(document, 'test', 'b' * 64, 999)

    def test_release_memory_evidence_requires_a_measured_budget_and_five_samples(self) -> None:
        workloads = ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': 100}
                   for name in workloads for _ in range(5)]
        document = {'schema_version': 1, 'targets': {'test': {
            'archive_sha256': 'a' * 64, 'memory_archive_bytes': 1000, 'memory_status': 'unmeasured', 'metrics': {}}}}
        with self.assertRaises(budgets.BudgetError):
            budgets.release_evidence(document, 'test', 'a' * 64, 1000, 'b' * 64, 5, records)
        budgets.apply_memory(document, 'test', 'a' * 64, 1000, records)
        with self.assertRaises(budgets.BudgetError):
            budgets.release_evidence(document, 'test', 'a' * 64, 1000, 'b' * 64, 4, records)
        evidence = budgets.release_evidence(document, 'test', 'b' * 64, 999, 'c' * 64, 5, records)
        self.assertEqual(evidence['target'], 'test')
        self.assertEqual(evidence['repetitions'], 5)
        self.assertEqual(evidence['archive_sha256'], 'b' * 64)
        self.assertEqual(evidence['archive_size'], 999)
        self.assertEqual(document['targets']['test']['archive_sha256'], 'a' * 64)
        self.assertEqual(evidence['budget_sha256'], 'c' * 64)
        self.assertEqual(evidence['rss_scope'], budgets.RSS_SCOPE)
        self.assertEqual(evidence['measurements']['fmt_initial_rss_kib'], 100)
        self.assertEqual(evidence['result'], 'passed')

    def test_size_budget_rejects_a_symlink_or_missing_entrypoint_and_invalid_numeric_limit(self) -> None:
        with workspace() as root:
            tree = root / 'tree'
            executable = tree / 'usr/bin/cmake'
            executable.parent.mkdir(parents=True)
            archive = root / 'archive'
            archive.write_bytes(b'archive')
            metrics: dict[str, dict[str, object]] = {
                name: {'value': 10, 'allowed_regression': 0}
                for name in ('executable_bytes', 'unpacked_bytes', 'archive_bytes')
            }
            document = {'targets': {'test': {'metrics': metrics}}}
            error = '^packaged CMake executable is missing or not a regular file$'
            with self.assertRaisesRegex(budgets.BudgetError, error):
                budgets.check_size(document, 'test', tree, archive)
            executable.symlink_to(archive)
            with self.assertRaisesRegex(budgets.BudgetError, error):
                budgets.check_size(document, 'test', tree, archive)
            executable.unlink()
            executable.write_bytes(b'cmake')
            self.assertEqual(budgets.check_size(document, 'test', tree, archive), {
                'executable_bytes': 5, 'unpacked_bytes': 5, 'archive_bytes': 7,
            })
            executable.write_bytes(b'x' * 11)
            with self.assertRaisesRegex(budgets.BudgetError, r'^test size budget exceeded: executable_bytes: 11 > 10, unpacked_bytes: 11 > 10$'):
                budgets.check_size(document, 'test', tree, archive)
            original_limit = metrics.pop('executable_bytes')
            with self.assertRaisesRegex(budgets.BudgetError, '^release budgets lack test executable_bytes$'):
                budgets.check_size(document, 'test', tree, archive)
            metrics['executable_bytes'] = original_limit
            limits = metrics['executable_bytes']
            for key in ('value', 'allowed_regression'):
                original = limits[key]
                for value in (True, '10', float('inf'), float('nan'), -1):
                    with self.subTest(key=key, value=value):
                        limits[key] = value
                        with self.assertRaisesRegex(budgets.BudgetError, '^release budget is invalid: test executable_bytes$'):
                            budgets.check_size(document, 'test', tree, archive)
                limits[key] = original

    def test_memory_report_preserves_spread_and_uses_inclusive_limit(self) -> None:
        sample_sets = {
            'fmt': [120, 122, 124, 125, 127],
            'zstd': [100, 100, 100, 100, 100],
            'libjpeg-turbo': [1, 2, 3, 4, 5],
            'llvm-clang': [100, 100, 100, 100, 100],
        }
        records = [{'variant': 'product', 'workload': name, 'scenario': 'initial', 'max_rss_kib': value}
                   for name, samples in sample_sets.items() for value in samples]
        self.assertEqual(budgets.memory_baseline(records), {
            'fmt_initial_rss_kib': {'value': 124, 'spread': 7, 'central_spread': 3, 'allowed_regression': 14},
            'zstd_initial_rss_kib': {'value': 100, 'spread': 0, 'central_spread': 0, 'allowed_regression': 3},
            'libjpeg-turbo_initial_rss_kib': {'value': 3, 'spread': 4, 'central_spread': 2, 'allowed_regression': 8},
            'llvm-clang_initial_rss_kib': {'value': 100, 'spread': 0, 'central_spread': 0, 'allowed_regression': 3},
        })
        document = {'targets': {'test': {'rss_scope': budgets.RSS_SCOPE, 'metrics': {
            f'{name}_initial_rss_kib': {'value': 100, 'allowed_regression': 24}
            for name in sample_sets
        }}}}
        self.assertEqual(budgets.check_memory(document, 'test', records)['fmt_initial_rss_kib'], 124)
        invalid = {'targets': {'test': {'rss_scope': 'different-scope', 'metrics': {}}}}
        with self.assertRaisesRegex(budgets.BudgetError, '^test memory baseline has an incompatible RSS scope$'):
            budgets.check_memory(invalid, 'test', records)
        for record, value in zip(records[:5], (55, 123, 129, 135, 200), strict=True):
            record['max_rss_kib'] = value
        with self.assertRaisesRegex(budgets.BudgetError, r'^test memory budget exceeded: fmt_initial_rss_kib: 129 > 124$'):
            budgets.check_memory(document, 'test', records)
        for value in (False, 0):
            records[0]['max_rss_kib'] = value
            with self.assertRaisesRegex(budgets.BudgetError, '^insufficient memory samples: fmt$'):
                budgets.memory_baseline(records)
        with self.assertRaisesRegex(budgets.BudgetError, '^insufficient memory samples: fmt$'):
            budgets.memory_baseline(records[1:])
        records[0]['max_rss_kib'] = 100
        with self.assertRaisesRegex(budgets.BudgetError, '^memory workloads have different sample counts$'):
            budgets.memory_baseline([*records, records[0]])

    def test_memory_baseline_rejects_partial_fields_and_invalid_measured_identity(self) -> None:
        target = 'test'
        sha = 'a' * 64
        entry = {'archive_sha256': sha, 'memory_archive_bytes': 1, 'memory_status': 'unmeasured', 'metrics': {}}
        document = {'targets': {target: entry}}
        self.assertEqual(budgets.validate_memory_source(document, target, sha, 1), 'unmeasured')
        for key, value in (
            ('rss_scope', budgets.RSS_SCOPE), ('memory_repetitions', 5), ('metrics', {'fmt_initial_rss_kib': {}}),
        ):
            partial = {'targets': {target: entry | {key: value}}}
            with self.subTest(partial=key), self.assertRaisesRegex(budgets.BudgetError, '^partial memory baseline is invalid: test$'):
                budgets.validate_memory_source(partial, target, sha, 1)

        metrics = {f'{name}_initial_rss_kib': {'value': 100, 'allowed_regression': 3}
                   for name in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')}
        measured = entry | {'memory_status': 'measured', 'rss_scope': budgets.RSS_SCOPE,
                            'memory_repetitions': 5, 'metrics': metrics}
        self.assertEqual(budgets.validate_memory_source({'targets': {target: measured}}, target, 'b' * 64, 998), 'measured')
        for key, value, detail in (
            ('rss_scope', 'legacy', 'an incompatible RSS scope'),
            ('memory_repetitions', 4, 'insufficient repetitions'),
            ('memory_repetitions', 5.0, 'insufficient repetitions'),
            ('archive_sha256', 'bad', 'invalid archive identity'),
            ('memory_archive_bytes', 0, 'invalid archive identity'),
            ('memory_archive_bytes', True, 'invalid archive identity'),
        ):
            invalid = {'targets': {target: measured | {key: value}}}
            with self.subTest(field=key, value=value), self.assertRaisesRegex(budgets.BudgetError, f'^test memory baseline has {detail}$'):
                budgets.validate_memory_source(invalid, target, sha, 1)
