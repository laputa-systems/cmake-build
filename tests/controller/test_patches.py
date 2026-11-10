from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from buildsys.patches import PatchError, verify_inventory
from helpers import workspace


def inventory(directory: Path, rows: list[tuple[int, str, bytes]]) -> None:
    text = "# Patches\n\n| Order | File | SHA-256 | Purpose |\n| --- | --- | --- | --- |\n"
    for order, name, data in rows:
        text += f"| {order} | `{name}` | `{hashlib.sha256(data).hexdigest()}` | Test patch. |\n"
    (directory / "README.md").write_text(text)


class PatchInventoryTests(unittest.TestCase):
    def test_rejects_changed_or_unlisted_patch(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            patches.mkdir()
            patch = patches / "change.patch"
            patch.write_bytes(b"original")
            inventory(patches, [(1, "change.patch", b"original")])
            verify_inventory(patches)
            patch.write_bytes(b"changed")
            with self.assertRaises(PatchError):
                verify_inventory(patches)
            patch.write_bytes(b"original")
            (patches / "extra.patch").write_bytes(b"extra")
            with self.assertRaises(PatchError):
                verify_inventory(patches)

    def test_rejects_escaping_or_symlinked_patch(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            patches.mkdir()
            outside = directory / "outside.patch"
            outside.write_bytes(b"outside")
            inventory(patches, [(1, "../outside.patch", b"outside")])
            with self.assertRaises(PatchError):
                verify_inventory(patches)
            (patches / "link.patch").symlink_to(outside)
            inventory(patches, [(1, "link.patch", b"outside")])
            with self.assertRaises(PatchError):
                verify_inventory(patches)


if __name__ == "__main__":
    unittest.main()
