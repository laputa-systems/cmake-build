"""Rustls dependency gates over the native target's prepared, vendored Cargo graph.

These read `.work/rust/<native triple>` and the `rustls-ffi-source` cache object that
`build.py fetch` and the native build prepare; they are not portable checks.
"""

from __future__ import annotations

import unittest

from helpers import ROOT, workspace

from buildsys.inputs import Cache, bootstrap_inputs, load_bootstrap, load_sources
from buildsys.targets import native_target
from buildsys.tls import TlsError, check_host_vendored


class PreparedDependencyGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        native = native_target()
        if native.executable_format != "elf":
            self.skipTest(f"host-vendored musl runtime checks do not apply to {native.triple}")

    def test_locked_graph_rejects_changed_provider_patch(self) -> None:
        native = native_target()
        lock = load_bootstrap(ROOT / "bootstrap.lock.json")
        inputs = bootstrap_inputs(lock, native.triple)
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        with workspace() as directory:
            patch_file = directory / "provider.patch"
            patch_file.write_bytes((ROOT / "patches/rustls-ffi/0001-graviola-provider.patch").read_bytes() + b"\n")
            with self.assertRaisesRegex(TlsError, "inputs changed"):
                check_host_vendored(ROOT / ".work/rust" / native.triple, native, inputs, source, patch_file,
                                    Cache(ROOT / ".work/cache", offline=True), [native.triple], ROOT / ".work/tmp")

    def test_locked_dependency_graph_for_both_targets(self) -> None:
        native = native_target()
        lock = load_bootstrap(ROOT / "bootstrap.lock.json")
        inputs = bootstrap_inputs(lock, native.triple)
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        rust_root = ROOT / ".work/rust" / native.triple
        check_host_vendored(rust_root, native, inputs, source, ROOT / "patches/rustls-ffi/0001-graviola-provider.patch", Cache(ROOT / ".work/cache", offline=True),
                            ["x86_64-unknown-linux-musl", "aarch64-unknown-linux-musl"], ROOT / ".work/tmp")


if __name__ == "__main__":
    unittest.main()
