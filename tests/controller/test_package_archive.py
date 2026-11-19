import io
import json
import os
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
        package.create(self.stage, first, {'target': 'example', 'features': {'b': False, 'a': True}}, 1234567890)
        (self.stage / 'bin/cmake').chmod(0o777)
        package.create(self.stage, second, {'features': {'a': True, 'b': False}, 'target': 'example'}, 1234567890)
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

    def test_preserves_a_nested_relative_link_in_the_package(self):
        shared = self.stage / 'share'
        (shared / 'component/deep').mkdir(parents=True)
        (shared / 'configuration').write_bytes(b'fixture config')
        target = 'component/deep/../../configuration'
        (shared / 'default').symlink_to(target)
        destination = self.root / 'cmake.tar.xz'
        package.create(self.stage, destination, {}, 0)
        package.inspect(destination)
        with tarfile.open(destination, 'r:xz') as archive:
            member = archive.getmember('usr/share/default')
            self.assertTrue(member.issym())
            self.assertEqual(member.linkname, target)
        self.assertEqual((shared / 'default').read_bytes(), b'fixture config')

    def test_inspection_requires_xz_and_unique_members_under_usr(self):
        original = self.root / 'original.tar.xz'
        changed = self.root / 'candidate.tar.xz'
        package.create(self.stage, original, {}, 0)
        cases = (
            ('w', None, 'invalid package:'),
            ('w:xz', 'usr/bin/cmake', '^invalid or duplicate archive member: usr/bin/cmake$'),
            ('w:xz', 'README', '^invalid or duplicate archive member: README$'),
            ('w:xz', 'usr/share/../README', r'^invalid or duplicate archive member: usr/share/\.\./README$'),
            ('w:xz', '.', r'^invalid or duplicate archive member: \.$'),
        )
        for mode, extra, error in cases:
            with self.subTest(mode=mode, member=extra):
                with tarfile.open(original, 'r:xz') as source, tarfile.open(changed, mode) as output:
                    for member in source:
                        output.addfile(member, source.extractfile(member) if member.isfile() else None)
                    if extra == 'usr/bin/cmake':
                        member = source.getmember(extra)
                        output.addfile(member, source.extractfile(member))
                    elif extra is not None:
                        member = tarfile.TarInfo(extra)
                        member.type = tarfile.DIRTYPE
                        output.addfile(member)
                with self.assertRaisesRegex(package.PackageError, error):
                    package.inspect(changed)

    def test_inspection_rejects_an_unpopulated_link_target(self):
        original = self.root / 'original.tar.xz'
        changed = self.root / 'candidate.tar.xz'
        package.create(self.stage, original, {}, 0)
        with tarfile.open(original, 'r:xz') as source, tarfile.open(changed, 'w:xz') as output:
            for member in source:
                if member.name == 'usr/share/link':
                    member.linkname = ''
                output.addfile(member, source.extractfile(member) if member.isfile() else None)
        with self.assertRaisesRegex(package.PackageError, '^unsafe symlink usr/share/link: $'):
            package.inspect(changed)

    def test_rejects_a_symlink_outside_the_package(self):
        (self.stage / 'share/escape').symlink_to('../../../outside')
        with self.assertRaisesRegex(package.PackageError, 'escaping symlink usr/share/escape'):
            package.create(self.stage, self.root / 'invalid.tar.xz', {}, 0)

    def test_rejects_special_files_without_creating_an_archive(self):
        os.mkfifo(self.stage / 'share/pipe')
        destination = self.root / 'invalid.tar.xz'
        with self.assertRaisesRegex(package.PackageError, 'unsupported file type: usr/share/pipe'):
            package.create(self.stage, destination, {}, 0)
        self.assertFalse(destination.exists())

    def test_requires_a_real_staging_directory_and_generates_its_own_inventory(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.stage, target_is_directory=True)
        destination = self.root / 'invalid.tar.xz'
        for stage in (alias, self.root / 'missing'):
            with self.subTest(stage=stage), self.assertRaisesRegex(package.PackageError, 'staging directory'):
                package.create(stage, destination, {}, 0)
        with self.assertRaisesRegex(package.PackageError, 'metadata must not supply its own file inventory'):
            package.create(self.stage, destination, {'files': {}}, 0)
        self.assertFalse(destination.exists())

    def test_replaces_stale_artifact_metadata_and_omits_only_root_phase_records(self):
        for filename in ('phase.json', 'state.json', 'share/phase.json', 'share/state.json'):
            path = self.stage / filename
            path.write_text('record')
            path.chmod(0o600)
        stale_manifest = self.stage / package.ARTIFACT.removeprefix('usr/')
        stale_manifest.parent.mkdir(parents=True)
        stale_manifest.write_text('stale')
        executable = self.stage / 'share/plugin'
        executable.write_text('program')
        executable.chmod(0o601)

        destination = self.root / 'nested' / 'target' / 'cmake.tar.xz'
        package.create(self.stage, destination, {'target': 'candidate'}, 0)
        artifact = package.inspect(destination)
        self.assertEqual(artifact['target'], 'candidate')
        with tarfile.open(destination, 'r:xz') as archive:
            self.assertNotIn('usr/phase.json', archive.getnames())
            self.assertNotIn('usr/state.json', archive.getnames())
            for filename in ('usr/share/phase.json', 'usr/share/state.json'):
                self.assertEqual(archive.getmember(filename).mode, 0o644)
            self.assertEqual(archive.getmember('usr/share/plugin').mode, 0o755)

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

    def test_detects_payload_changes_and_incomplete_manifests(self):
        original = self.root / 'original.tar.xz'
        changed = self.root / 'changed.tar.xz'
        package.create(self.stage, original, {}, 0)
        for name, data, error in (
            ('usr/bin/cmake', b'cmakE', 'package inventory does not match its contents'),
            (package.ARTIFACT, b'{}', 'package inventory does not match its contents'),
            (package.ARTIFACT, b'{', 'invalid package:'),
        ):
            with self.subTest(member=name, data=data):
                with tarfile.open(original, 'r:xz') as source, tarfile.open(changed, 'w:xz') as destination:
                    for member in source:
                        contents = source.extractfile(member) if member.isfile() else None
                        if member.name == name:
                            member.size = len(data)
                            contents = io.BytesIO(data)
                        destination.addfile(member, contents)
                with self.assertRaisesRegex(package.PackageError, error):
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
