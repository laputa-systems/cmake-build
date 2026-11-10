from __future__ import annotations

import unittest
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from buildsys import rust, sandbox, tls
from buildsys.inputs import Cache, Input
from buildsys.phases import PhaseCache
from buildsys.rust import RustError, _phase_digest, build_static, vendor
from buildsys.targets import target
from buildsys.tls import TlsError, build_client, check_tree, check_host_vendored
from buildsys.targets import native_target
from buildsys.inputs import bootstrap_inputs, load_bootstrap, load_sources
from helpers import ROOT, workspace


class DependencyTests(unittest.TestCase):
    def test_client_rebuilds_when_builder_image_changes(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        source = Input("cmake-source", "4.4.5", "https://example.invalid/cmake", "a" * 64, "source", "all", 1)
        with workspace() as directory:
            root = directory / "build"
            staticlib = directory / "rust/phases/staticlib"
            archive = staticlib / "target" / description.triple / "debug/librustls_ffi.a"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"archive")
            (staticlib / "source").mkdir()
            (staticlib / "source/Cargo.toml").write_text('[package]\nversion = "0.15.7"\n')
            client = directory / "client.c"
            client.write_text("int main(void) { return 0; }\n")
            bootstrap_runs = []
            client_runs = []

            def extract(archive_path, destination):
                (destination / "cmake-source").mkdir(parents=True)
                return destination

            def run(command, *, cwd, env):
                if Path(command[0]).name == "bootstrap":
                    bootstrap_runs.append(1)
                if Path(command[0]).name == "clang":
                    client_runs.append(1)
                    Path(command[-1]).write_bytes(b"client")
                return ""

            with patch.object(tls.toolchain, "verify"), patch.object(tls, "_phase_digest", return_value="b" * 64), \
                    patch.object(tls, "safe_extract", side_effect=extract), patch.object(tls, "_run", side_effect=run), \
                    patch.object(Cache, "require", return_value=directory / "source"), \
                    patch.object(sandbox, "image_fingerprint", return_value="c" * 64) as image:
                for _ in range(2):
                    build_client(Cache(directory), source, directory / "prepared", archive, description, root, directory, client)
                self.assertEqual((len(bootstrap_runs), len(client_runs)), (1, 1))
                image.return_value = "d" * 64
                build_client(Cache(directory), source, directory / "prepared", archive, description, root, directory, client)
                self.assertEqual((len(bootstrap_runs), len(client_runs)), (2, 2))

    def test_static_build_rebuilds_when_builder_image_changes(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            root = directory / "rust"
            (root / "phases/vendor/source/crate").mkdir(parents=True)
            kache = directory / "kache"
            kache.write_bytes(b"wrapper")
            original_is_file = Path.is_file
            cargo_runs = []

            def is_file(path):
                return True if path == Path("/usr/lib/libgcc_s.so.1") else original_is_file(path)

            def run(command, *, cwd, env):
                if Path(command[0]).name == "cargo":
                    cargo_runs.append(1)
                    archive = Path(env["CARGO_TARGET_DIR"]) / description.triple / "debug/librustls_ffi.a"
                    archive.parent.mkdir(parents=True)
                    archive.write_bytes(b"archive")
                return ""

            with patch.object(sandbox, "in_container", return_value=True), \
                    patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo")]), \
                    patch.object(rust.toolchain, "verify"), patch.object(rust, "_phase_digest", return_value="a" * 64), \
                    patch.object(Path, "is_file", is_file), patch.object(rust, "_run", side_effect=run), \
                    patch.object(sandbox, "image_fingerprint", return_value="b" * 64) as image:
                build_static(root, directory / "prepared", description, kache, directory)
                build_static(root, directory / "prepared", description, kache, directory)
                self.assertEqual(len(cargo_runs), 1)
                image.return_value = "c" * 64
                build_static(root, directory / "prepared", description, kache, directory)
                self.assertEqual(len(cargo_runs), 2)

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

    def test_static_build_rejects_networked_container(self) -> None:
        with workspace() as directory, patch.object(sandbox, "in_container", return_value=True), patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]):
            with self.assertRaisesRegex(RustError, "sealed container"):
                build_static(directory, directory, target("x86_64-unknown-linux-musl"), directory, directory)

    def test_rejects_tampered_vendor_phase(self) -> None:
        with workspace() as directory:
            phase = PhaseCache(directory).run("vendor", {"source": "a" * 64}, lambda path: (path / "crate").write_bytes(b"verified"))
            self.assertTrue(_phase_digest(phase.directory))
            (phase.directory / "crate").write_bytes(b"tampered")
            with self.assertRaisesRegex(RustError, "does not match"):
                _phase_digest(phase.directory)

    def test_vendor_process_tree_stops_on_termination(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(10)
            child = "import socket,sys; s=socket.socket(); s.connect(('127.0.0.1',int(sys.argv[1]))); s.sendall(b'ready'); s.recv(1)"
            owner = "import os,sys; from pathlib import Path; from buildsys.rust import _run; _run([sys.executable,'-c',sys.argv[1],sys.argv[2]],cwd=Path('.'),env=dict(os.environ))"
            process = subprocess.Popen([sys.executable, "-c", owner, child, str(listener.getsockname()[1])])
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(10)
                    self.assertEqual(connection.recv(5), b"ready")
                    process.send_signal(signal.SIGTERM)
                    self.assertEqual(connection.recv(1), b"")
                self.assertEqual(process.wait(timeout=10), -signal.SIGTERM)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_vendor_rejects_incomplete_toolchain_lock(self) -> None:
        with workspace() as directory, self.assertRaisesRegex(RustError, "component lock is incomplete"):
            source = Input("source", "1", "https://example.invalid", "a" * 64, "source", "all", 1)
            vendor(Cache(directory / "cache"), [], source, Path("patch"), directory, directory)

    def test_graviola_closure_accepts_certificate_path_probe(self) -> None:
        check_tree("rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\nopenssl-probe v0.2.1\n")

    def test_rejects_other_crypto_providers_and_missing_provider(self) -> None:
        for package in ("ring", "aws-lc-rs", "aws-lc-sys", "openssl", "openssl-sys", "native-tls"):
            with self.subTest(package=package), self.assertRaises(TlsError):
                check_tree(f"rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\n{package} v1.0.0\n")
        with self.assertRaises(TlsError):
            check_tree("rustls-ffi v0.15.7\n")


if __name__ == "__main__":
    unittest.main()
