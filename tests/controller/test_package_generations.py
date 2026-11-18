import json
import unittest
from unittest.mock import patch

from helpers import file_sha256, workspace

from buildsys import budgets, generations, package


class GenerationTest(unittest.TestCase):
    def setUp(self):
        context = workspace()
        self.root = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.stage = self.root / 'stage'
        (self.stage / 'bin').mkdir(parents=True)
        (self.stage / 'bin/cmake').write_bytes(b'first')
        self.archive = self.root / 'artifact.tar.xz'
        package.create(self.stage, self.archive, {'target': 'example'}, 1)
        self.store = self.root / 'generations'

    def test_failed_and_interrupted_qualification_preserve_active_generation(self):
        first_digest = file_sha256(self.archive)
        generation = generations.qualify(self.store, self.archive, first_digest, lambda tree: {'basic': 'passed'})
        results = json.loads((generation / 'results.json').read_text())
        self.assertEqual(results['archive_size'], self.archive.stat().st_size)
        unpacked = sum(path.stat().st_size for path in (generation / 'tree').rglob('*') if path.is_file() and not path.is_symlink())
        self.assertEqual(results['unpacked_size'], unpacked)
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')
        (self.stage / 'bin/cmake').write_bytes(b'second')
        package.create(self.stage, self.archive, {'target': 'example'}, 1)
        second_digest = file_sha256(self.archive)
        def fail(tree):
            raise RuntimeError('qualification failed')
        with self.assertRaises(RuntimeError):
            generations.qualify(self.store, self.archive, second_digest, fail)
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')
        def interrupt(tree):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            generations.qualify(self.store, self.archive, second_digest, interrupt)
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')

    def test_same_archive_requalification_refreshes_active_results(self):
        digest = file_sha256(self.archive)
        generation = generations.qualify(self.store, self.archive, digest, lambda tree: {'basic': 'passed'})
        result = generation / 'results.json'
        first = json.loads(result.read_text())
        result.write_text(json.dumps(first | {'archive_size': 0}))
        refreshed = {'basic': 'passed', 'projects': 'passed'}
        self.assertEqual(generations.qualify(self.store, self.archive, digest, lambda tree: refreshed), generation)
        self.assertEqual(json.loads(result.read_text()), first | {'qualification': refreshed})
        self.assertEqual((self.store / 'active').resolve(), generation / 'tree')

    def test_failed_results_replacement_preserves_the_active_generation(self):
        digest = file_sha256(self.archive)
        generation = generations.qualify(self.store, self.archive, digest, lambda tree: {'basic': 'passed'})
        result = generation / 'results.json'
        previous = result.read_bytes()
        atomic_replace = generations.os.replace

        def fail_result_replace(source, destination):
            if destination == result:
                raise OSError('fixture replacement failure')
            atomic_replace(source, destination)

        with (
            patch.object(generations.os, 'replace', side_effect=fail_result_replace),
            self.assertRaisesRegex(OSError, 'fixture replacement failure'),
        ):
            generations.qualify(self.store, self.archive, digest, lambda tree: {'projects': 'passed'})
        self.assertEqual(result.read_bytes(), previous)
        self.assertEqual((self.store / 'active').resolve(), generation / 'tree')
        self.assertEqual(list(self.store.glob('.candidate-*')), [])

    def test_tampered_archive_does_not_activate(self):
        expected = file_sha256(self.archive)
        with self.archive.open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaises(generations.GenerationError):
            generations.qualify(self.store, self.archive, expected, lambda tree: {'basic': 'passed'})
        self.assertFalse((self.store / 'active').exists())

    def test_qualification_cannot_modify_packaged_bytes(self):
        expected = file_sha256(self.archive)
        def corrupt(tree):
            (tree / 'usr/bin/cmake').write_bytes(b'modified')
            return {'basic': 'passed'}
        with self.assertRaises(generations.GenerationError):
            generations.qualify(self.store, self.archive, expected, corrupt)
        self.assertFalse((self.store / 'active').exists())

    def test_over_budget_candidate_does_not_replace_active_generation(self):
        first_digest = file_sha256(self.archive)
        first = generations.qualify(self.store, self.archive, first_digest, lambda tree: {'basic': 'passed'})
        first_tree = first / 'tree'
        unpacked = sum(path.stat().st_size for path in first_tree.rglob('*') if path.is_file() and not path.is_symlink())
        limits = {'schema_version': 1, 'targets': {'example': {'metrics': {
            'executable_bytes': {'value': 5, 'allowed_regression': 0},
            'unpacked_bytes': {'value': unpacked, 'allowed_regression': 0},
            'archive_bytes': {'value': self.archive.stat().st_size, 'allowed_regression': 0},
        }}}}
        (self.stage / 'bin/cmake').write_bytes(b'too large')
        package.create(self.stage, self.archive, {'target': 'example'}, 1)
        with self.assertRaises(budgets.BudgetError):
            generations.qualify(self.store, self.archive, file_sha256(self.archive),
                                lambda tree: budgets.check_size(limits, 'example', tree, tree.parent / 'artifact.tar.xz'))
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')

    def test_size_check_uses_the_copied_candidate(self):
        digest = file_sha256(self.archive)
        size = self.archive.stat().st_size
        def qualify(tree):
            unpacked = sum(path.stat().st_size for path in tree.rglob('*') if path.is_file() and not path.is_symlink())
            limits = {'schema_version': 1, 'targets': {'example': {'metrics': {
                'executable_bytes': {'value': 5, 'allowed_regression': 0},
                'unpacked_bytes': {'value': unpacked, 'allowed_regression': 0},
                'archive_bytes': {'value': size, 'allowed_regression': 0},
            }}}}
            self.archive.write_bytes(b'x' * (size + 1))
            return budgets.check_size(limits, 'example', tree, tree.parent / 'artifact.tar.xz')
        generation = generations.qualify(self.store, self.archive, digest, qualify)
        self.assertEqual(file_sha256(generation / 'artifact.tar.xz'), digest)


if __name__ == '__main__':
    unittest.main()
