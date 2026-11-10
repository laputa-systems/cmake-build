import unittest
import json

from buildsys import generations
from buildsys import budgets
from buildsys import package
from helpers import workspace


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
        first_digest = package.digest(self.archive)
        generation = generations.qualify(self.store, self.archive, first_digest, lambda tree: {'basic': 'passed'})
        results = json.loads((generation / 'results.json').read_text())
        self.assertEqual(results['archive_size'], self.archive.stat().st_size)
        unpacked = sum(path.stat().st_size for path in (generation / 'tree').rglob('*') if path.is_file() and not path.is_symlink())
        self.assertEqual(results['unpacked_size'], unpacked)
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')
        (self.stage / 'bin/cmake').write_bytes(b'second')
        package.create(self.stage, self.archive, {'target': 'example'}, 1)
        second_digest = package.digest(self.archive)
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

    def test_tampered_archive_does_not_activate(self):
        expected = package.digest(self.archive)
        with self.archive.open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaises(generations.GenerationError):
            generations.qualify(self.store, self.archive, expected, lambda tree: {'basic': 'passed'})
        self.assertFalse((self.store / 'active').exists())

    def test_qualification_cannot_modify_packaged_bytes(self):
        expected = package.digest(self.archive)
        def corrupt(tree):
            (tree / 'usr/bin/cmake').write_bytes(b'modified')
            return {'basic': 'passed'}
        with self.assertRaises(generations.GenerationError):
            generations.qualify(self.store, self.archive, expected, corrupt)
        self.assertFalse((self.store / 'active').exists())

    def test_over_budget_candidate_does_not_replace_active_generation(self):
        first_digest = package.digest(self.archive)
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
            generations.qualify(self.store, self.archive, package.digest(self.archive),
                                lambda tree: budgets.check_size(limits, 'example', tree, tree.parent / 'artifact.tar.xz'))
        self.assertEqual((self.store / 'active/usr/bin/cmake').read_bytes(), b'first')

    def test_size_check_uses_the_copied_candidate(self):
        digest = package.digest(self.archive)
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
        self.assertEqual(package.digest(generation / 'artifact.tar.xz'), digest)


if __name__ == '__main__':
    unittest.main()
