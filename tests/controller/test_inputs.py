from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from helpers import archive, workspace, write_lock

from buildsys.inputs import (
    Cache,
    Input,
    InputError,
    bootstrap_inputs,
    load_bootstrap,
    load_sources,
    safe_extract,
)

SHA_A = "a" * 64
GOOD_SHA = hashlib.sha256(b"good").hexdigest()
BOOTSTRAP_LOCK = Path(__file__).resolve().parents[2] / "bootstrap.lock.json"
X86 = "x86_64-unknown-linux-musl"
ARM = "aarch64-unknown-linux-musl"


def entry(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
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
        urls=("https://example.invalid/source.tar.gz",),
        sha256=sha,
        role="source",
        target="x86_64-unknown-linux-musl",
        size=size,
    )


class LockTests(unittest.TestCase):
    def test_bootstrap_exposes_the_pinned_image_and_ordered_inputs(self) -> None:
        document = json.loads(BOOTSTRAP_LOCK.read_text())
        lock = load_bootstrap(BOOTSTRAP_LOCK)
        alpine = document["alpine"]
        self.assertEqual(lock.image_index_digest, alpine["image_index_digest"])
        for triple in (X86, ARM):
            with self.subTest(triple=triple):
                section = document["targets"][triple]
                entries = [*section["packages"], *section["rust"]["components"]]
                self.assertEqual(
                    [(item.name, item.url, item.sha256) for item in bootstrap_inputs(lock, triple)],
                    [(entry["name"], entry["url"], entry["sha256"]) for entry in entries],
                )

    def test_bootstrap_accepts_omitted_packages_and_unlabeled_rust_inputs(self) -> None:
        document = json.loads(BOOTSTRAP_LOCK.read_text())
        section = document["targets"][X86]
        del section["packages"]
        rust = section["rust"]["components"][0]
        del rust["role"], rust["target"]
        explicit = section["rust"]["components"][1]
        explicit["role"], explicit["target"] = "source", X86
        with workspace() as directory:
            path = directory / "bootstrap.json"
            path.write_text(json.dumps(document))
            inputs = bootstrap_inputs(load_bootstrap(path), X86)
        self.assertEqual([item.name for item in inputs], [item["name"] for item in section["rust"]["components"]])
        self.assertEqual((inputs[0].role, inputs[0].target), ("build-source", "all"))
        self.assertEqual((inputs[1].role, inputs[1].target), ("source", X86))

    def test_bootstrap_reports_the_location_of_malformed_records(self) -> None:
        cases = (
            (("alpine",), None, "expected 'alpine' object"),
            (("alpine", "release"), "", "alpine.release must be a nonempty string"),
            (("alpine", "image_manifest_reference"), 9, "image_manifest_reference must be a nonempty string"),
            (("alpine", "image_index_digest"), SHA_A, "image_index_digest must be a sha256 index digest"),
            (("alpine", "image_index_digest"), "sha256:bad", "image_index_digest must be a sha256 index digest"),
            (("alpine", "repositories"), [], "alpine.repositories must be an object"),
            (("targets",), [], "expected 'targets' object"),
            (("targets", "riscv64-unknown-linux-musl"), {}, "unknown target section riscv64"),
            (("targets", X86), [], f"target section {X86} is not an object"),
            (("targets", X86, "packages"), None, rf"{X86}\.packages must be a list"),
            (("targets", X86, "packages", 1), None, rf"{X86}\.packages: entry #1 is not an object"),
            (("targets", X86, "packages", 1), {"name": "incomplete"}, rf"{X86}\.packages: entry #1 missing version"),
            (("targets", X86, "packages", 0, "target"), ARM, f"target {ARM} is not {X86}"),
            (("targets", X86, "rust"), [], rf"{X86}\.rust\.components must be a list"),
            (("targets", X86, "rust", "components"), None, rf"{X86}\.rust\.components must be a list"),
            (("targets", X86, "rust", "components", 1), 9, rf"{X86}\.rust\.components: entry #1 is not an object"),
            (("targets", X86, "rust", "components", 1), {"name": "incomplete"},
             rf"{X86}\.rust\.components: entry #1 missing version"),
        )
        current = BOOTSTRAP_LOCK.read_text()
        with workspace() as directory:
            path = directory / "bootstrap.json"
            for location, value, message in cases:
                with self.subTest(location=location, value=value):
                    document = json.loads(current)
                    record = document
                    for key in location[:-1]:
                        record = record[key]
                    record[location[-1]] = value
                    path.write_text(json.dumps(document))
                    with self.assertRaisesRegex(InputError, message):
                        load_bootstrap(path)

    def test_bootstrap_requires_stable_alpine_release_and_matching_package_urls(self) -> None:
        root = Path(__file__).resolve().parents[2]
        current = (root / "bootstrap.lock.json").read_text()
        triple = "aarch64-unknown-linux-musl"
        edge = "https://dl-cdn.alpinelinux.org/alpine/edge/main"
        with workspace() as directory:
            path = directory / "bootstrap.json"
            for field in ("release", "repository", "package"):
                with self.subTest(field=field):
                    lock = json.loads(current)
                    expected = "stable"
                    if field == "release":
                        lock["alpine"]["release"] = "3.25.0_alpha20260805"
                    elif field == "repository":
                        lock["alpine"]["repositories"][triple] = [edge]
                        expected = "alpine.repositories"
                    else:
                        lock["targets"][triple]["packages"][0]["url"] = f"{edge}/aarch64/acl-libs-2.3.2-r1.apk"
                    path.write_text(json.dumps(lock))
                    with self.assertRaisesRegex(InputError, expected):
                        load_bootstrap(path)

    def test_bootstrap_requires_a_pinned_reference_image_index(self) -> None:
        with workspace() as directory:
            root = Path(__file__).resolve().parents[2]
            lock = json.loads((root / "bootstrap.lock.json").read_text())
            self.assertRegex(load_bootstrap(root / "bootstrap.lock.json").reference_image,
                             r"^debian@sha256:[0-9a-f]{64}$")
            path = directory / "bootstrap.json"
            for value in (None, "debian:trixie-slim", "debian@sha256:invalid"):
                with self.subTest(value=value):
                    lock["reference_image"] = value
                    path.write_text(json.dumps(lock))
                    with self.assertRaisesRegex(InputError, "reference_image"):
                        load_bootstrap(path)
            lock["schema_version"] = 2
            path.write_text(json.dumps(lock))
            with self.assertRaisesRegex(InputError, "schema_version must be 1"):
                load_bootstrap(path)

    def test_bootstrap_rust_component_requires_size(self) -> None:
        with workspace() as directory:
            root = Path(__file__).resolve().parents[2]
            lock = json.loads((root / "bootstrap.lock.json").read_text())
            component = lock["targets"][X86]["rust"]["components"][0]
            del component["size"]
            path = directory / "bootstrap.json"
            path.write_text(json.dumps(lock))
            with self.assertRaises(InputError) as error:
                load_bootstrap(path)
            self.assertEqual(str(error.exception), f"{path}:{X86}.rust.components: {component['name']} must pin a size")

    def test_bootstrap_preserves_zero_size_and_optional_metadata(self) -> None:
        document = json.loads(BOOTSTRAP_LOCK.read_text())
        package = document["targets"][X86]["packages"][0]
        package.update(size=0, license="MIT", purpose="bootstrap tool")
        with workspace() as directory:
            path = directory / "bootstrap.json"
            path.write_text(json.dumps(document))
            item = bootstrap_inputs(load_bootstrap(path), X86)[0]
        self.assertEqual((item.size, item.license, item.purpose), (0, "MIT", "bootstrap tool"))

    def test_bootstrap_reports_the_named_package_for_invalid_values(self) -> None:
        cases = (
            ("version", "", "version must be a nonempty string"),
            ("version", 3, "version must be a nonempty string"),
            ("sha256", "F" * 64, "sha256 must be lowercase hex"),
            ("size", -1, "size must be a nonnegative integer"),
            ("size", False, "size must be a nonnegative integer"),
        )
        current = BOOTSTRAP_LOCK.read_text()
        with workspace() as directory:
            path = directory / "bootstrap.json"
            for field, value, message in cases:
                with self.subTest(field=field, value=value):
                    document = json.loads(current)
                    package = document["targets"][X86]["packages"][0]
                    package[field] = value
                    path.write_text(json.dumps(document))
                    with self.assertRaises(InputError) as error:
                        load_bootstrap(path)
                    self.assertEqual(str(error.exception), f"{package['name']}: {message}")

    def test_bootstrap_rejects_invalid_optional_input_metadata(self) -> None:
        root = Path(__file__).resolve().parents[2]
        current = (root / "bootstrap.lock.json").read_text()
        with workspace() as directory:
            path = directory / "bootstrap.json"
            for field in ("license", "purpose"):
                with self.subTest(field=field):
                    lock = json.loads(current)
                    lock["targets"]["x86_64-unknown-linux-musl"]["packages"][0][field] = 123
                    path.write_text(json.dumps(lock))
                    with self.assertRaisesRegex(InputError, f"{field} must be a string"):
                        load_bootstrap(path)

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
            with self.assertRaisesRegex(InputError, "sha256 must be 64 lowercase hex"):
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

    def test_concurrent_stores_publish_the_same_verified_object(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            item = source()
            replace = os.replace
            ready = Barrier(2)

            def publish(temporary: Path, target: Path) -> None:
                self.assertTrue(temporary.is_relative_to(target.parent))
                ready.wait(timeout=5)
                replace(temporary, target)

            with (
                patch("buildsys.inputs.os.replace", side_effect=publish),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                first = executor.submit(cache.store, payload, item)
                second = executor.submit(cache.store, payload, item)
                stored = first.result()
                self.assertEqual(second.result(), stored)

            self.assertEqual(cache.require(item).read_bytes(), b"good")
            self.assertEqual(list(stored.parent.iterdir()), [stored])

    def test_store_cleans_up_when_input_changes_during_copy(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            item = source()
            copy = shutil.copyfile

            def copy_changed(path: Path, temporary: Path) -> None:
                path.write_bytes(b"evil")
                copy(path, temporary)

            with (
                patch("buildsys.inputs.shutil.copyfile", side_effect=copy_changed),
                self.assertRaisesRegex(InputError, "bytes changed during publication"),
            ):
                cache.store(payload, item)

            self.assertEqual(list((cache.root / "objects").iterdir()), [])
            payload.write_bytes(b"good")
            self.assertEqual(cache.store(payload, item).read_bytes(), b"good")

    def test_corrupted_cached_input(self) -> None:
        with workspace() as directory:
            payload = directory / "payload"
            payload.write_bytes(b"good")
            cache = Cache(directory / "cache")
            stored = cache.store(payload, source())
            stored.write_bytes(b"evil")
            with self.assertRaisesRegex(InputError, "cache object .*sha256 .* != pinned"):
                cache.require(source())

    def test_fetches_verified_fresh_input(self) -> None:
        with workspace() as directory:
            served = directory / "served"
            served.write_bytes(b"good")
            item = Input(
                name="source",
                version="1.0",
                urls=(served.as_uri(),),
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
                urls=(served.as_uri(),),
                sha256=SHA_A,
                role="source",
                target="x86_64-unknown-linux-musl",
                size=4,
            )
            cache = Cache(directory / "cache")
            with self.assertRaisesRegex(InputError, "served sha256 .*pinned"):
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
            source = root / "a"
            source.write_bytes(b"one")
            source.chmod(0o644)
            first = tree_digest(root)
            source.write_bytes(b"two")
            changed_contents = tree_digest(root)
            self.assertNotEqual(first, changed_contents)

            source.chmod(0o755)
            executable = tree_digest(root)
            self.assertNotEqual(changed_contents, executable)

            link = root / "link"
            link.symlink_to("a")
            linked = tree_digest(root)
            self.assertNotEqual(executable, linked)
            link.unlink()
            link.symlink_to("other")
            self.assertNotEqual(linked, tree_digest(root))

    def test_phase_records_are_excluded_only_at_the_root(self) -> None:
        from buildsys.inputs import tree_digest

        with workspace() as root:
            nested = root / "install" / "share"
            nested.mkdir(parents=True)
            root_record = root / "phase.json"
            nested_record = nested / "phase.json"
            root_record.write_text("controller metadata")
            nested_record.write_text("package metadata")
            excluded = {"phase.json"}
            initial = tree_digest(root, exclude=excluded)

            root_record.write_text("updated controller metadata")
            self.assertEqual(tree_digest(root, exclude=excluded), initial)

            nested_record.write_text("updated package metadata")
            updated = tree_digest(root, exclude=excluded)
            self.assertNotEqual(updated, initial)
            nested.rename(nested.with_name("doc"))
            self.assertNotEqual(tree_digest(root, exclude=excluded), updated)


if __name__ == "__main__":
    unittest.main()
