from __future__ import annotations

import unittest

from helpers import workspace

from buildsys import rust


class KacheWrapperTests(unittest.TestCase):
    def test_split_engine_is_copied_and_changes_the_identity(self) -> None:
        with workspace() as root:
            installed = root / 'installed'
            installed.mkdir()
            (installed / 'kache').write_bytes(b'client')
            engine = installed / 'kache-engine'
            engine.write_bytes(b'engine-one')
            copied = rust.install_wrapper(installed / 'kache', root / 'copied')
            first = rust.wrapper_identity(copied)
            self.assertEqual((copied.parent / 'kache-engine').read_bytes(), b'engine-one')
            engine.write_bytes(b'engine-two')
            rust.install_wrapper(installed / 'kache', root / 'copied')
            self.assertNotEqual(first, rust.wrapper_identity(copied))
            engine.unlink()
            rust.install_wrapper(installed / 'kache', root / 'copied')
            self.assertFalse((copied.parent / 'kache-engine').exists())


if __name__ == '__main__':
    unittest.main()
