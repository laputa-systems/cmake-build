import io
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

    def test_inventory_requires_an_integer_size(self):
        (self.stage / 'share/tiny').write_bytes(b'x')
        original = self.root / 'original.tar.xz'
        changed = self.root / 'changed.tar.xz'
        package.create(self.stage, original, {}, 0)
        package.inspect(original)
        for invalid_size in (True, 1.0):
            with self.subTest(size=invalid_size):
                with tarfile.open(original, 'r:xz') as source, tarfile.open(changed, 'w:xz') as destination:
                    for member in source:
                        contents = source.extractfile(member) if member.isfile() else None
                        if member.name == package.ARTIFACT:
                            assert contents is not None
                            artifact = json.load(contents)
                            artifact['files']['usr/share/tiny']['size'] = invalid_size
                            body = json.dumps(artifact).encode()
                            member.size = len(body)
                            contents = io.BytesIO(body)
                        destination.addfile(member, contents)
                with self.assertRaisesRegex(package.PackageError, 'package inventory does not match its contents'):
                    package.inspect(changed)

    def test_an_initial_null_manifest_does_not_hide_a_duplicate(self):
        original = self.root / 'original.tar.xz'
        changed = self.root / 'changed.tar.xz'
        package.create(self.stage, original, {}, 0)
        with tarfile.open(original, 'r:xz') as source, tarfile.open(changed, 'w:xz') as destination:
            for member in source:
                if member.name == package.ARTIFACT:
                    null = tarfile.TarInfo(member.name)
                    null.size = 4
                    destination.addfile(null, io.BytesIO(b'null'))
                destination.addfile(member, source.extractfile(member) if member.isfile() else None)
        with self.assertRaisesRegex(package.PackageError, 'package inventory does not match its contents'):
            package.inspect(changed)


if __name__ == '__main__':
    unittest.main()
