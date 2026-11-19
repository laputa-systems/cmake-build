from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from helpers import workspace

from buildsys.patches import Patch, PatchError, verify_inventory


def inventory(directory: Path, rows: list[tuple[int, str, bytes]]) -> None:
    text = "# Patches\n\n| Order | File | SHA-256 | Purpose |\n| --- | --- | --- | --- |\n"
    for order, name, data in rows:
        text += f"| {order} | `{name}` | `{hashlib.sha256(data).hexdigest()}` | Test patch. |\n"
    (directory / "README.md").write_text(text)


class PatchInventoryTests(unittest.TestCase):
    def test_preserves_declared_order_exact_bytes_and_digests(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            (patches / "nested").mkdir(parents=True)
            files = (("nested/z.patch", b"first\r\n"), ("a.patch", b"second\n"))
            for name, data in files:
                (patches / name).write_bytes(data)
            inventory(patches, [(order, name, data) for order, (name, data) in enumerate(files, 1)])
            self.assertEqual(
                verify_inventory(patches),
                tuple(Patch(name, hashlib.sha256(data).hexdigest(), data) for name, data in files),
            )

    def test_rejects_invalid_manifest_rows_and_empty_or_duplicate_inventories(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            patches.mkdir()
            patch = patches / "example.patch"
            data = b"example"
            patch.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            inventory(patches, [])
            heading = (patches / "README.md").read_text()
            row = f"| 1 | `example.patch` | `{digest}` | Test patch. |\n"
            malformed = row.replace(digest, "not-a-digest")
            cases = (
                ("", "patch inventory does not match the patch files"),
                (malformed, f"malformed patch inventory row: {malformed.rstrip()!r}"),
                (row.replace(" 1 ", " 2 "), "invalid patch inventory order or entry: 'example.patch'"),
                (row.replace(".patch`", ".txt`"), "invalid patch inventory order or entry: 'example.txt'"),
                (row.replace("Test patch.", "   "), "invalid patch inventory order or entry: 'example.patch'"),
                (row + row.replace(" 1 ", " 2 "), "patch inventory does not match the patch files"),
            )
            for content, message in cases:
                with self.subTest(message=message):
                    (patches / "README.md").write_text(heading + content)
                    with self.assertRaises(PatchError) as caught:
                        verify_inventory(patches)
                    self.assertEqual(str(caught.exception), message)

    def test_rejects_unreadable_manifest_and_directory_patch(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            patches.mkdir()
            with self.assertRaises(PatchError) as caught:
                verify_inventory(patches)
            self.assertTrue(str(caught.exception).startswith("cannot read patch inventory path 'README.md': "))
            self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

            (patches / "README.md").write_bytes(b"\xff")
            with self.assertRaises(PatchError) as caught:
                verify_inventory(patches)
            self.assertEqual(str(caught.exception), "patch inventory is not UTF-8")
            self.assertIsInstance(caught.exception.__cause__, UnicodeDecodeError)

            (patches / "directory.patch").mkdir()
            inventory(patches, [(1, "directory.patch", b"fixture")])
            with self.assertRaises(PatchError) as caught:
                verify_inventory(patches)
            self.assertEqual(str(caught.exception), "patch inventory path is not a regular file: directory.patch")

    def test_rejects_changed_or_unlisted_patch(self) -> None:
        with workspace() as directory:
            patches = directory / "patches"
            patches.mkdir()
            patch = patches / "change.patch"
            patch.write_bytes(b"original")
            inventory(patches, [(1, "change.patch", b"original")])
            verify_inventory(patches)
            patch.write_bytes(b"changed")
            with self.assertRaises(PatchError) as caught:
                verify_inventory(patches)
            found = hashlib.sha256(b"changed").hexdigest()
            expected = hashlib.sha256(b"original").hexdigest()
            self.assertEqual(str(caught.exception), f"patch digest mismatch for change.patch: {found} != {expected}")
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
