from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from buildsys import bootstrap
from buildsys.targets import target
from helpers import workspace


class BootstrapTests(unittest.TestCase):
    def test_rejects_bootstrap_cmake_version_mismatch(self) -> None:
        with workspace() as directory, patch.object(bootstrap, "_run", return_value="cmake version 1.0\n"), \
                patch.object(bootstrap, "_source") as source:
            with self.assertRaisesRegex(bootstrap.BootstrapError, "bootstrap CMake version"):
                bootstrap.build(
                    cmake_archive=Path("source"), samurai_archive=Path("samurai"), ninja_archive=Path("ninja"),
                    directory=directory, tc=directory, sysroot=directory, target=target("x86_64-unknown-linux-musl"),
                    bootstrap_version="4.3.4",
                )
            source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
