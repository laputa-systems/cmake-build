from __future__ import annotations

import hashlib
import tarfile
import unittest

from buildsys.inputs import (
    Cache,
    Input,
    InputError,
    load_sources,
    safe_extract,
)
from helpers import archive, workspace, write_lock

SHA_A = "a" * 64
GOOD_SHA = hashlib.sha256(b"good").hexdigest()


def entry(**overrides: object) -> dict:
    value = {
        "name": "source",
        "version": "1.0",
        "url": "https://example.invalid/source.tar.gz",
        "sha256": SHA_A,
        "size": 4,
        "role": "source",
        "target": "x86_64-unknown-linux-musl",
    }
    value.update(overrides)
    return value


def source(sha: str = GOOD_SHA, size: int | None = 4, name: str = "source") -> Input:
    return Input(
        name=name,
        version="1.0",
        url="https://example.invalid/source.tar.gz",
        sha256=sha,
        role="source",
        target="x86_64-unknown-linux-musl",
        size=size,
    )


class LockTests(unittest.TestCase):
    def test_accepts_complete_entry(self) -> None:
        with workspace() as directory:
            lock = write_lock(directory / "lock.json", [entry()])
            [item] = load_sources(lock)
            self.assertEqual(item.name, "source")
            self.assertEqual(item.size, 4)

    def test_missing_lock_entry_field(self) -> None:
        with workspace() as directory:
            broken = entry()
            del broken["sha256"]
            lock = write_lock(directory / "lock.json", [broken])
            with self.assertRaisesRegex(InputError, "missing sha256"):
                load_sources(lock)

    def test_missing_size_is_rejected(self) -> None:
        with workspace() as directory:
            broken = entry()
            del broken["size"]
            lock = write_lock(directory / "lock.json", [broken])
            with self.assertRaisesRegex(InputError, "must pin a size"):
                load_sources(lock)

    def test_modified_lock_entry_breaks_cached_object(self) -> None:
        with workspace() as directory:
            original = directory / "payload"
            original.write_bytes(b"good")
            cache = Cache(directory / "cache")
            cache.store(original, source())
            modified = source(sha="c" * 64)
            with self.assertRaisesRegex(InputError, "absent from cache"):
                cache.require(modified)

    def test_duplicate_names_and_bad_roles(self) -> None:
        with workspace() as directory:
            duplicate = write_lock(directory / "duplicate.json", [entry(), entry()])
            with self.assertRaisesRegex(InputError, "duplicate input"):
                load_sources(duplicate)
            bad_role = write_lock(directory / "role.json", [entry(role="vendor")])
            with self.assertRaisesRegex(InputError, "unknown role"):
                load_sources(bad_role)


class CacheTests(unittest.TestCase):
    def test_store_and_require_roundtrip(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            stored = cache.store(payload, source())
            self.assertEqual(stored.read_bytes(), b"good")
            self.assertEqual(cache.require(source()), stored)

    def test_corrupted_cached_input(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            stored = cache.store(payload, source())
            stored.write_bytes(b"evil")
            with self.assertRaisesRegex(InputError, "cache object digest"):
                cache.require(source())

    def test_fetches_verified_fresh_input(self) -> None:
        with workspace() as directory:
            served = directory / "served"
            served.write_bytes(b"good")
            item = Input(
                name="source",
                version="1.0",
                url=served.as_uri(),
                sha256=GOOD_SHA,
                role="source",
                target="x86_64-unknown-linux-musl",
                size=4,
            )
            cache = Cache(directory / "cache")
            fetched = cache.fetch(item)
            self.assertEqual(fetched.read_bytes(), b"good")

    def test_corrupted_fresh_input(self) -> None:
        with workspace() as directory:
            served = directory / "served"
            served.write_bytes(b"evil")
            item = Input(
                name="source",
                version="1.0",
                url=served.as_uri(),
                sha256=SHA_A,
                role="source",
                target="x86_64-unknown-linux-musl",
                size=4,
            )
            cache = Cache(directory / "cache")
            with self.assertRaisesRegex(InputError, "digest .* != pinned"):
                cache.fetch(item)
            self.assertFalse((cache.root / "objects" / f"{SHA_A}.blob").exists())

    def test_size_mismatch(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            with self.assertRaisesRegex(InputError, "size 4 != pinned 5"):
                cache.store(payload, source(size=5))


class ExtractTests(unittest.TestCase):
    def test_extracts_regular_tree(self) -> None:
        with workspace() as directory:
            bundle = archive(
                directory / "good.tar.gz",
                [("top/", None, None), ("top/file", b"data", None)],
            )
            destination = safe_extract(bundle, directory / "out")
            self.assertEqual((destination / "top" / "file").read_bytes(), b"data")

    def test_traversal_archive(self) -> None:
        with workspace() as directory:
            bundle = archive(directory / "bad.tar.gz", [("../evil", b"data", None)])
            with self.assertRaisesRegex(InputError, "traversal"):
                safe_extract(bundle, directory / "out")
            self.assertFalse((directory / "out").exists())
            self.assertFalse((directory / "evil").exists())

    def test_absolute_archive(self) -> None:
        with workspace() as directory:
            bundle = archive(directory / "bad.tar.gz", [("/evil", b"data", None)])
            with self.assertRaisesRegex(InputError, "absolute"):
                safe_extract(bundle, directory / "out")

    def test_unsafe_symlink_archive(self) -> None:
        with workspace() as directory:
            bundle = archive(directory / "bad.tar.gz", [("link", None, "../../outside")])
            with self.assertRaisesRegex(InputError, "link-escape"):
                safe_extract(bundle, directory / "out")
            self.assertFalse((directory / "out").exists())

    def test_escaping_hardlink_archive(self) -> None:
        with workspace() as directory:
            path = directory / "bad.tar.gz"
            with tarfile.open(path, "w:gz") as tar:
                info = tarfile.TarInfo("link")
                info.type = tarfile.LNKTYPE
                info.linkname = "../../outside"
                tar.addfile(info)
            with self.assertRaisesRegex(InputError, "link-escape"):
                safe_extract(path, directory / "out")

    def test_device_node_archive(self) -> None:
        with workspace() as directory:
            path = directory / "bad.tar.gz"
            with tarfile.open(path, "w:gz") as tar:
                info = tarfile.TarInfo("null")
                info.type = tarfile.CHRTYPE
                info.devmajor = 1
                info.devminor = 3
                tar.addfile(info)
            with self.assertRaisesRegex(InputError, "special"):
                safe_extract(path, directory / "out")


class DigestTests(unittest.TestCase):
    def test_digest_tracks_content_mode_and_links(self) -> None:
        from buildsys.inputs import tree_digest

        with workspace() as directory:
            root = directory / "tree"
            root.mkdir()
            (root / "a").write_bytes(b"one")
            first = tree_digest(root)
            (root / "a").write_bytes(b"two")
            self.assertNotEqual(first, tree_digest(root))
            (root / "a").chmod(0o755)
            self.assertNotEqual(first, tree_digest(root))
            (root / "link").symlink_to("a")
            self.assertNotEqual(first, tree_digest(root))


if __name__ == "__main__":
    unittest.main()
