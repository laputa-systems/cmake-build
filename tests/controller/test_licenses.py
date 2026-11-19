from __future__ import annotations

import unittest
from pathlib import Path

from helpers import workspace

from buildsys import licenses, stage


class LicenseStagingTests(unittest.TestCase):
    def test_new_dependency_requires_a_license(self) -> None:
        with workspace() as root:
            for group, name in (('rustls', 'tls-1.0.0'), ('rust-std', 'std-0.0.0')):
                folder = root / group / name
                folder.mkdir(parents=True)
                (folder / 'LICENSE').write_text('terms')
            licenses.verify_closure('tls v1.0.0\n', 'std v0.0.0\n', root)
            with self.assertRaisesRegex(licenses.LicenseError, 'new-dependency-2.0.0'):
                licenses.verify_closure('tls v1.0.0\nnew-dependency v2.0.0\n', 'std v0.0.0\n', root)

    def test_license_links_cannot_escape_the_license_tree(self) -> None:
        with workspace() as root:
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'LICENSE').write_text('terms')
            base = root / 'licenses'
            (base / 'rustls').mkdir(parents=True)
            (base / 'rustls/tls-1.0.0').symlink_to(outside, target_is_directory=True)
            (base / 'rust-std/std-0.0.0').mkdir(parents=True)
            (base / 'rust-std/std-0.0.0/LICENSE').write_text('terms')
            with self.assertRaisesRegex(licenses.LicenseError, 'tls-1.0.0'):
                licenses.verify_closure('tls v1.0.0\n', 'std v0.0.0\n', base)

    def test_rejects_invalid_empty_and_unlicensed_dependency_closures(self) -> None:
        with workspace() as root:
            for group in ('rustls', 'rust-std'):
                folder = root / group / 'Sample-crate-1.2.3+BUILD'
                folder.mkdir(parents=True)
                (folder / 'LICENSE').write_text('terms')
            entry = 'Sample-crate v1.2.3+BUILD (registry)\n'
            licenses.verify_closure(entry + entry, entry, root)
            cases = (
                ('invalid dependency\n', entry, "invalid rustls dependency entry: 'invalid dependency'"),
                (entry, 'sample-crate 1.2.3\n', "invalid rust-std dependency entry: 'sample-crate 1.2.3'"),
                ('', entry, 'rustls dependency closure is empty'),
                (entry, '', 'rust-std dependency closure is empty'),
                (entry, 'empty v0.1.0\n', 'rust-std dependency lacks license texts: empty-0.1.0'),
            )
            (root / 'rust-std/empty-0.1.0').mkdir()
            for rustls, std, message in cases:
                with self.subTest(message=message), self.assertRaises(licenses.LicenseError) as caught:
                    licenses.verify_closure(rustls, std, root)
                self.assertEqual(str(caught.exception), message)

    def test_reports_each_missing_distribution_executable(self) -> None:
        for missing in ('cmake', 'ctest', 'cpack'):
            with self.subTest(missing=missing), workspace() as root:
                phase = root / 'phase'
                binaries = phase / 'build/bin'
                binaries.mkdir(parents=True)
                for name in ('cmake', 'ctest', 'cpack'):
                    if name != missing:
                        (binaries / name).write_bytes(name.encode())
                output = root / 'output'
                output.mkdir()
                with self.assertRaises(stage.StageError) as caught:
                    stage.stage(phase, output, 'target', '4.4.5', root / 'licenses', root / 'NOTICE')
                self.assertEqual(str(caught.exception), f'built {missing} executable is missing')

    def test_license_notices_are_packaged_with_the_distribution(self) -> None:
        with workspace() as root:
            phase = root / 'phase'
            (phase / 'build/bin').mkdir(parents=True)
            for name in ('cmake', 'ctest', 'cpack'):
                executable = phase / 'build/bin' / name
                executable.write_bytes(name.encode())
                executable.chmod(0o751)
            source = phase / 'source'
            for name in ('Help', 'Modules', 'Templates'):
                (source / name / 'nested').mkdir(parents=True)
                (source / name / 'nested/resource').write_text(name)
                (source / name / 'entry').symlink_to('nested/resource')
            for name in ('LICENSE.rst', 'CONTRIBUTORS.rst'):
                (source / name).write_text(name)
            licenses = root / 'licenses'
            (licenses / 'library').mkdir(parents=True)
            (licenses / 'library/LICENSE').write_text('license terms')
            (licenses / 'library/COPYING').symlink_to('LICENSE')
            notice = root / 'NOTICE'
            notice.write_text('third-party notice')
            output = root / 'output'
            output.mkdir()
            stage.stage(phase, output, 'target', '4.4.5', licenses, notice)
            for name in ('cmake', 'ctest', 'cpack'):
                executable = output / 'bin' / name
                self.assertEqual(executable.read_bytes(), name.encode())
                self.assertEqual(executable.stat().st_mode & 0o777, 0o751)
            self.assertEqual({entry.name for entry in output.iterdir()}, {'bin', 'share'})
            self.assertEqual({entry.name for entry in (output / 'share').iterdir()}, {'cmake', 'cmake-4.4', 'doc'})
            self.assertEqual({entry.name for entry in (output / 'share/doc').iterdir()}, {'cmake-build'})
            self.assertEqual({entry.name for entry in (output / 'share/cmake-4.4').iterdir()}, {'Help', 'Modules', 'Templates'})
            self.assertEqual((output / 'share/cmake').readlink(), Path('cmake-4.4'))
            for name in ('Help', 'Modules', 'Templates'):
                resource = output / 'share/cmake-4.4' / name
                self.assertEqual((resource / 'entry').readlink(), Path('nested/resource'))
                self.assertEqual((resource / 'entry').read_text(), name)
            docs = output / 'share/doc/cmake-build'
            self.assertEqual(
                {entry.name for entry in docs.iterdir()},
                {'LICENSE.rst', 'CONTRIBUTORS.rst', 'NOTICE', 'artifact.json', 'licenses'},
            )
            for name in ('LICENSE.rst', 'CONTRIBUTORS.rst'):
                self.assertEqual((docs / name).read_text(), name)
            self.assertEqual((docs / 'NOTICE').read_text(), 'third-party notice')
            self.assertEqual((docs / 'licenses/library/LICENSE').read_text(), 'license terms')
            self.assertEqual((docs / 'licenses/library/COPYING').readlink(), Path('LICENSE'))
            self.assertEqual(
                (docs / 'artifact.json').read_text(),
                '{\n  "cmake_version": "4.4.5",\n  "qualification": "pending",\n  "target": "target"\n}\n',
            )


if __name__ == '__main__':
    unittest.main()
