from __future__ import annotations

import io
import tarfile
import unittest
from pathlib import Path

from helpers import workspace

from buildsys import macho, targets

ROOT = Path(__file__).resolve().parents[2]
DARWIN = targets.target("aarch64-apple-darwin")


def _archive(path: Path, members: list[tuple[str, bytes | None, str | None]]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data, link in members:
            if link is not None:
                info = tarfile.TarInfo(name)
                info.type = tarfile.SYMTYPE
                info.linkname = link
                tar.addfile(info)
            elif data is None:
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            else:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return path


class MachoLinkTests(unittest.TestCase):
    def test_safe_link_rejects_absolute_and_escaping_targets(self) -> None:
        for name, target in (
            ("usr/share/cmake", "/etc/passwd"),
            ("usr/a", "../../outside"),
            ("usr/a/b", "../../../x"),
            ("usr/a", ""),
        ):
            with self.subTest(name=name, target=target), self.assertRaises(macho.MachoError):
                macho._safe_link(name, target)

    def test_safe_link_accepts_internal_relative_targets(self) -> None:
        macho._safe_link("usr/share/cmake", "cmake-4.4")
        macho._safe_link("usr/share/doc/x", "../licenses")
        macho._safe_link("usr/a/b/c", "../../d")


class MachoExtractTests(unittest.TestCase):
    def test_extract_requires_a_single_top_level_directory(self) -> None:
        with workspace() as directory:
            flat = _archive(directory / "flat.tar.gz", [("usr/bin/cmake", b"x", None)])
            root = macho._extract(flat, directory / "out")
            self.assertEqual(root.name, "usr")
            mixed = _archive(directory / "mixed.tar.gz", [("a/f", b"x", None), ("b/g", b"y", None)])
            with self.assertRaises(macho.MachoError):
                macho._extract(mixed, directory / "out2")

    def test_extract_accepts_safe_symlinks_and_rejects_escapes(self) -> None:
        with workspace() as directory:
            good = _archive(
                directory / "good.tar.gz",
                [("top/", None, None), ("top/usr/", None, None),
                 ("top/usr/share/", None, None), ("top/usr/share/cmake-4.4/", None, None),
                 ("top/usr/share/cmake", None, "cmake-4.4")],
            )
            root = macho._extract(good, directory / "out")
            self.assertTrue((root / "usr/share/cmake").is_symlink())

            bad = _archive(
                directory / "bad.tar.gz",
                [("top/", None, None), ("top/usr/", None, None),
                 ("top/usr/evil", None, "../../../etc/passwd")],
            )
            with self.assertRaises(macho.MachoError):
                macho._extract(bad, directory / "out2")

    def test_extract_rejects_hardlinks_and_special_members(self) -> None:
        with workspace() as directory:
            path = directory / "links.tar.gz"
            with tarfile.open(path, "w:gz") as tar:
                info = tarfile.TarInfo("top")
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
                link = tarfile.TarInfo("top/hard")
                link.type = tarfile.LNKTYPE
                link.linkname = "top/file"
                tar.addfile(link)
            with self.assertRaises(macho.MachoError):
                macho._extract(path, directory / "out")


class DarwinLockTests(unittest.TestCase):
    def test_source_lock_carries_the_darwin_toolchain_inputs(self) -> None:
        from buildsys.inputs import load_sources

        names = {item.name for item in load_sources(ROOT / "sources.lock.json")}
        self.assertIn("llvm-toolchain-arm64", names)
        self.assertIn("cmake-bootstrap-darwin", names)

    def test_bootstrap_lock_carries_the_darwin_rust_components(self) -> None:
        from buildsys.inputs import bootstrap_inputs, load_bootstrap

        lock = load_bootstrap(ROOT / "bootstrap.lock.json")
        names = {item.name for item in bootstrap_inputs(lock, "aarch64-apple-darwin")}
        self.assertEqual(names, {"cargo", "rustc", "rust-std", "rust-src"})

    def test_darwin_target_is_not_an_elf_target(self) -> None:
        self.assertEqual(DARWIN.executable_format, "mach-o")
        self.assertEqual(DARWIN.elf_machine, 0)
        self.assertEqual(DARWIN.musl_loader, "")


if __name__ == "__main__":
    unittest.main()
