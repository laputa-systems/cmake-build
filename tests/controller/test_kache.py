from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from helpers import file_sha256, workspace

from buildsys import rust


class KacheWrapperTests(unittest.TestCase):
    def test_split_engine_is_copied_and_changes_the_identity(self) -> None:
        with workspace() as root:
            installed = root / 'installed'
            installed.mkdir()
            client = installed / 'kache'
            client.write_bytes(b'client')
            client.chmod(0o751)
            engine = installed / 'kache-engine'
            engine.write_bytes(b'engine-one')
            engine.chmod(0o755)
            alias = root / 'current-kache'
            alias.symlink_to(client)
            destination = root / 'scratch' / 'copied'
            copied = rust.install_wrapper(alias, destination)
            self.assertEqual(copied, destination / 'build-kache')
            self.assertEqual(copied.read_bytes(), b'client')
            self.assertEqual(copied.stat().st_mode & 0o777, 0o751)
            copied_engine = destination / 'kache-engine'
            self.assertEqual(copied_engine.stat().st_mode & 0o777, 0o755)
            first = rust.wrapper_identity(copied)
            identity_input = f'{{"client":"{file_sha256(client)}","engine":"{file_sha256(engine)}"}}'
            self.assertEqual(first, hashlib.sha256(identity_input.encode()).hexdigest())
            self.assertEqual(copied_engine.read_bytes(), b'engine-one')
            engine.write_bytes(b'engine-two')
            rust.install_wrapper(alias, destination)
            self.assertNotEqual(first, rust.wrapper_identity(copied))
            engine.unlink()
            rust.install_wrapper(alias, destination)
            self.assertFalse(copied_engine.exists())
            client_only = f'{{"client":"{file_sha256(client)}"}}'
            self.assertEqual(rust.wrapper_identity(copied), hashlib.sha256(client_only.encode()).hexdigest())

    def test_single_binary_install_and_copy_failure(self) -> None:
        with workspace() as root:
            client = root / 'kache'
            client.write_bytes(b'client only')
            destination = root / 'copied'
            copied = rust.install_wrapper(client, destination)
            self.assertEqual(copied.read_bytes(), b'client only')
            self.assertFalse((destination / 'kache-engine').exists())

            cause = PermissionError('fixture denied the wrapper copy')
            with patch.object(rust.shutil, 'copy2', side_effect=cause), self.assertRaises(rust.RustError) as failed:
                rust.install_wrapper(client, destination)
            self.assertEqual(str(failed.exception), f'cannot install kache wrapper: {cause}')
            self.assertIs(failed.exception.__cause__, cause)


if __name__ == '__main__':
    unittest.main()
