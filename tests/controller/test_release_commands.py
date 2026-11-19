from __future__ import annotations

import argparse
import contextlib
import io
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import workspace

import build


class ReleaseCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root: Path = self.enterContext(workspace())
        self.target = build._target("aarch64-unknown-linux-musl")
        self.other = build._target("x86_64-unknown-linux-musl")
        self.commit = "0123456789abcdef0123456789abcdef01234567"
        self.lock = object()
        self.enterContext(patch.multiple(build, ROOT=self.root, _NATIVE=self.target))
        self.identity = self.enterContext(patch.object(build, "_source_commit", return_value=self.commit))
        self.load_sources = self.enterContext(patch.object(build, "load_sources", return_value=[
            SimpleNamespace(name="not-cmake", version="0.1"),
            SimpleNamespace(name="cmake-source", version="4.4.5"),
        ]))
        self.load_lock = self.enterContext(patch.object(build, "load_bootstrap", return_value=self.lock))
        self.tag = self.enterContext(patch.object(build.sandbox, "image_tag", return_value="fixture-image"))
        self.suite = self.enterContext(patch.object(build, "test_command"))
        self.sealed = self.enterContext(patch.object(build.sandbox, "run_sealed", return_value=SimpleNamespace(
            returncode=0, stdout="fixture packaging\n", stderr="",
        )))
        self.inner = self.enterContext(patch.object(build, "_package_inside"))
        self.in_container = self.enterContext(patch.object(build.sandbox, "in_container", return_value=True))
        self.interfaces = self.enterContext(patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo")]))
        self.reproduce = self.enterContext(patch.object(build.reproduce, "run", return_value=[]))
        self.benchmark = self.enterContext(patch.object(build.benchmark, "run"))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def assert_rejected(self, action, args: argparse.Namespace, message: str) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as caught:
            action(args)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(error.getvalue(), f"error: {message}\n")

    def test_package_checks_inner_host_network_and_commit_identity(self) -> None:
        args = argparse.Namespace(target=self.target.triple, in_container=True)
        boundary_message = "packaging requires a sealed container with only loopback networking"
        self.in_container.return_value = False
        self.assert_rejected(build.package_command, args, boundary_message)
        self.in_container.return_value = True
        self.interfaces.return_value = [(1, "lo"), (2, "eth0")]
        self.assert_rejected(build.package_command, args, boundary_message)
        self.interfaces.return_value = [(1, "lo")]
        with patch.object(build, "_NATIVE", self.other):
            self.assert_rejected(build.package_command, args, f"{self.target.triple} does not match the running machine; no emulation is used")
        with patch.dict(os.environ, clear=True):
            self.assert_rejected(build.package_command, args, "packaging requires a repository commit identity")
        with patch.dict(os.environ, {"CMAKE_BUILD_COMMIT": self.commit[:8]}):
            self.assert_rejected(build.package_command, args, "packaging requires a repository commit identity")
        self.inner.assert_not_called()
        with patch.dict(os.environ, {"CMAKE_BUILD_COMMIT": self.commit}):
            self.assertEqual(build.package_command(args), 0)
        self.inner.assert_called_once_with(self.target, self.commit)
        self.sealed.assert_not_called()

    def test_package_uses_the_source_commit_and_exact_sealed_command(self) -> None:
        args = argparse.Namespace(target=self.target.triple, in_container=False)
        self.assertEqual(build.package_command(args), 0)
        self.identity.assert_called_once_with()
        self.suite.assert_called_once_with(argparse.Namespace(target=self.target.triple, suite="basic", in_container=False))
        self.load_lock.assert_called_once_with(build.BOOTSTRAP_LOCK)
        self.tag.assert_called_once_with(self.lock, self.target, build.DOCKERFILE)
        self.sealed.assert_called_once_with(
            "fixture-image",
            ["python3", "build.py", "package", "--target", self.target.triple, "--in-container"],
            target=self.target,
            mounts=[(self.root, "/src")],
            env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src", "CMAKE_BUILD_COMMIT": self.commit},
            timeout=1800,
        )
        self.assertEqual(self.stdout.getvalue(), "fixture packaging\n")
        self.sealed.return_value = SimpleNamespace(returncode=17, stdout="", stderr="fixture failure")
        self.assert_rejected(build.package_command, args, "packaging failed inside the sealed container (17):\nfixture failure")
        self.inner.assert_not_called()

    def test_reproduce_checks_native_target_and_reports_differences(self) -> None:
        args = argparse.Namespace(target=self.target.triple)
        with patch.object(build, "_NATIVE", self.other):
            self.assert_rejected(build.reproduce_command, args, f"{self.target.triple} does not match the running machine; no emulation is used")
        self.reproduce.assert_not_called()
        self.assertEqual(build.reproduce_command(args), 0)
        self.load_sources.assert_called_once_with(build.SOURCES_LOCK)
        self.reproduce.assert_called_once_with(self.root, self.target.triple, "4.4.5", self.commit)
        self.reproduce.return_value = ["manifest differs", "archive differs"]
        self.assertEqual(build.reproduce_command(args), 1)
        self.assertEqual(
            self.stdout.getvalue(),
            "reproducibility: file trees and archive bytes are identical\nmanifest differs\narchive differs\n",
        )

    def test_benchmark_requires_the_native_target_and_reports_the_output(self) -> None:
        args = argparse.Namespace(target=self.target.triple)
        with patch.object(build, "_NATIVE", self.other):
            self.assert_rejected(build.benchmark_command, args, f"{self.target.triple} does not match the running machine; no emulation is used")
        self.benchmark.assert_not_called()
        self.assertEqual(build.benchmark_command(args), 0)
        self.benchmark.assert_called_once_with(self.root, self.target)
        self.assertEqual(self.stdout.getvalue(), "benchmark report: docs/performance.md\n")
