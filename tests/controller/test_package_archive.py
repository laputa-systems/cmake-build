import json
import tarfile
import unittest

from helpers import file_sha256, workspace

from buildsys import package


class PackageTest(unittest.TestCase):
    def setUp(self):
        context = workspace()
        self.root = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.stage = self.root / 'stage'
        (self.stage / 'bin').mkdir(parents=True)
        (self.stage / 'bin/cmake').write_bytes(b'cmake')
        (self.stage / 'bin/cmake').chmod(0o755)
        (self.stage / 'share').mkdir()
        (self.stage / 'share/link').symlink_to('../bin/cmake')

    def test_deterministic_archive_and_inventory(self):
        first = self.root / 'first.tar.xz'
        second = self.root / 'second.tar.xz'
        package.create(self.stage, first, {'target': 'example'}, 1234567890)
        (self.stage / 'bin/cmake').chmod(0o777)
        package.create(self.stage, second, {'target': 'example'}, 1234567890)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(package.inspect(first)['target'], 'example')
        with tarfile.open(first, 'r:xz') as archive:
            members = archive.getmembers()
            self.assertEqual([m.name for m in members], sorted(m.name for m in members))
            self.assertTrue(all(m.uid == m.gid == 0 and m.mtime == 1234567890 for m in members))
            self.assertEqual(archive.getmember('usr/bin/cmake').mode, 0o755)
            member = archive.extractfile('usr/share/doc/cmake-build/artifact.json')
            assert member is not None
            artifact = json.load(member)
            self.assertEqual(artifact['target'], 'example')
            self.assertEqual(artifact['files']['usr/bin/cmake']['sha256'], file_sha256(self.stage / 'bin/cmake'))
            self.assertEqual(artifact['files']['usr/share/link']['target'], '../bin/cmake')
            self.assertNotIn('usr/share/doc/cmake-build/artifact.json', artifact['files'])

    def test_rejects_symlink_escape_and_special_files(self):
        (self.stage / 'share/escape').symlink_to('../../../outside')
        with self.assertRaises(package.PackageError):
            package.create(self.stage, self.root / 'invalid.tar.xz', {}, 0)


if __name__ == '__main__':
    unittest.main()
