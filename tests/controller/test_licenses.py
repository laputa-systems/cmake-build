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

    def test_license_notices_are_packaged_with_the_distribution(self) -> None:
        with workspace() as root:
            phase = root / 'phase'
            (phase / 'build/bin').mkdir(parents=True)
            for name in ('cmake', 'ctest', 'cpack'):
                (phase / 'build/bin' / name).write_bytes(name.encode())
            source = phase / 'source'
            for name in ('Help', 'Modules', 'Templates'):
                (source / name).mkdir(parents=True)
            for name in ('LICENSE.rst', 'CONTRIBUTORS.rst'):
                (source / name).write_text(name)
            licenses = root / 'licenses'
            (licenses / 'library').mkdir(parents=True)
            (licenses / 'library/LICENSE').write_text('license terms')
            notice = root / 'NOTICE'
            notice.write_text('third-party notice')
            output = root / 'output'
            output.mkdir()
            stage.stage(phase, output, 'target', '4.4.5', licenses, notice)
            for name in ('cmake', 'ctest', 'cpack'):
                self.assertEqual((output / 'bin' / name).read_bytes(), name.encode())
            self.assertEqual((output / 'share/cmake').readlink(), Path('cmake-4.4'))
            docs = output / 'share/doc/cmake-build'
            self.assertEqual((docs / 'NOTICE').read_text(), 'third-party notice')
            self.assertEqual((docs / 'licenses/library/LICENSE').read_text(), 'license terms')


if __name__ == '__main__':
    unittest.main()
