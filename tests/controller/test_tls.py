from __future__ import annotations

import unittest
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

from buildsys.inputs import Cache, Input
from buildsys.phases import PhaseCache
from buildsys.rust import RustError, _phase_digest, vendor
from buildsys.tls import TlsError, check_tree
from helpers import workspace


class DependencyTests(unittest.TestCase):
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
