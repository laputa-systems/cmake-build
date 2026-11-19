from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import workspace

import build


class FetchCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root: Path = self.enterContext(workspace())
        self.work = self.root / ".work"
        self.cache_root = self.work / "cache"
        self.phases = self.work / "phases"
        self.native = build._target("aarch64-unknown-linux-musl")
        self.target = build._target("x86_64-unknown-linux-musl")
        self.source = self.input("rustls-ffi-source", "all", 11)
        self.selected = self.input("target-source", self.target.triple, 17)
        self.other = self.input("native-source", self.native.triple, 23)
        self.native_package = self.input("native-package", self.native.triple, 31)
        self.target_package = self.input("target-package", self.target.triple, None)
        self.lock = build.BootstrapLock("fixture-index", "fixture-reference", {
            self.native.triple: (self.native_package,), self.target.triple: (self.target_package,),
        })
        self.sources = [self.source, self.selected, self.other]
        self.enterContext(patch.multiple(
            build, ROOT=self.root, WORK=self.work, CACHE=self.cache_root, PHASES=self.phases,
            BUILD_ROOT=self.work / "build", SOURCES_LOCK=self.root / "sources.lock.json",
            BOOTSTRAP_LOCK=self.root / "bootstrap.lock.json", DOCKERFILE=self.root / "docker/builder.Dockerfile",
            _NATIVE=self.native,
        ))
        self.load_sources = self.enterContext(patch.object(build, "load_sources", return_value=self.sources))
        self.load_bootstrap = self.enterContext(patch.object(build, "load_bootstrap", return_value=self.lock))
        self.cache_factory = self.enterContext(patch.object(build, "Cache"))
        self.cache = self.cache_factory.return_value
        self.package_path = self.root / "fixture-package"
        self.package_path.write_bytes(b"uncounted")
        self.cache.require.side_effect = self.require
        self.enterContext(patch.object(build.sandbox, "in_container", return_value=False))
        self.pull = self.enterContext(patch.object(build.sandbox, "pull_image"))
        self.pull_reference = self.enterContext(patch.object(build.sandbox, "pull_reference"))
        self.image_reference = self.enterContext(patch.object(build.sandbox, "image_reference", return_value="fixture-base"))
        self.build_image = self.enterContext(patch.object(build.sandbox, "build_image", return_value="fixture-builder"))
        self.run_fetch = self.enterContext(patch.object(build.sandbox, "run_fetch"))
        self.install_tools = self.enterContext(patch.object(build.rust, "install_tools"))
        self.vendor = self.enterContext(patch.object(build.rust, "vendor", return_value=self.root / "vendor"))
        self.check_vendored = self.enterContext(patch.object(build.tls, "check_vendored"))
        self.verify_toolchain = self.enterContext(patch.object(build.toolchain, "verify", return_value={"clang": "fixture"}))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    @staticmethod
    def input(name: str, target: str, size: int | None) -> build.Input:
        return build.Input(name=name, version="1.0", target=target, size=size, sha256="0" * 64,
                           role="source", urls=("https://example.invalid/source.tar.xz",))

    def require(self, item: build.Input) -> Path:
        if item in (self.selected, self.native_package):
            raise build.InputError(f"missing {item.name}")
        return self.package_path

    def options(self, *, inside: bool = False) -> argparse.Namespace:
        return argparse.Namespace(target=self.target.triple, vendor_in_container=inside)

    def test_fetch_uses_target_inputs_and_the_native_builder(self) -> None:
        self.assertEqual(build.fetch(self.options()), 0)
        self.load_sources.assert_called_once_with(self.root / "sources.lock.json")
        self.load_bootstrap.assert_called_once_with(self.root / "bootstrap.lock.json")
        self.cache_factory.assert_called_once_with(self.cache_root)
        self.image_reference.assert_called_once_with(self.lock)
        self.assertEqual(self.cache.require.call_args_list, [
            call(self.source), call(self.selected), call(self.target_package), call(self.target_package), call(self.native_package),
        ])
        self.assertEqual(self.cache.fetch.call_args_list, [call(self.selected), call(self.native_package)])
        self.assertEqual(self.pull.call_args_list, [call(self.lock, self.target.docker_platform), call(self.lock, self.native.docker_platform)])
        self.pull_reference.assert_called_once_with(self.lock, self.target.docker_platform)
        self.install_tools.assert_called_once_with(self.cache, [self.native_package], self.work / "rust" / self.native.triple, self.work / "tmp")
        self.build_image.assert_called_once_with(self.lock, self.native, self.root / "docker/builder.Dockerfile", self.cache, self.work / "tmp/image")
        self.run_fetch.assert_called_once_with("fixture-builder", self.native, self.root, self.target.triple)
        self.vendor.assert_not_called()
        self.assertEqual(self.stdout.getvalue().splitlines(), [
            "rustls-ffi-source 1.0 cached 11 B", "target-source 1.0 downloaded 17 B", "target-package 1.0 cached 9 B",
            f"3 inputs, 37 B, cache {self.cache_root}", f"builder base fixture-base for {self.target.docker_platform}",
            f"reference base fixture-reference for {self.target.docker_platform}",
        ])

    def test_vendoring_uses_the_native_offline_cache_and_checks_the_requested_target(self) -> None:
        with patch.object(build.sandbox, "in_container", return_value=True):
            self.assertEqual(build.fetch(self.options(inside=True)), 0)
        self.cache_factory.assert_called_once_with(self.cache_root, offline=True)
        self.load_sources.assert_called_once_with(self.root / "sources.lock.json")
        self.load_bootstrap.assert_called_once_with(self.root / "bootstrap.lock.json")
        rust_root = self.work / "rust" / self.native.triple
        self.vendor.assert_called_once_with(self.cache, [self.native_package], self.source,
                                            self.root / "patches/rustls-ffi/0001-graviola-provider.patch", rust_root, self.work / "tmp")
        self.check_vendored.assert_called_once_with(self.root / "vendor", rust_root / "phases/tools/bin", self.target.triple, self.work / "tmp")
        self.pull.assert_not_called()
        self.run_fetch.assert_not_called()
        self.assertEqual(self.stdout.getvalue(), f"TLS dependency gate passed for {self.target.triple}\n")

    def test_fetch_stops_at_the_container_or_image_error(self) -> None:
        with self.assertRaises(SystemExit) as outside:
            build.fetch(self.options(inside=True))
        self.assertEqual(outside.exception.code, 2)
        self.assertEqual(self.stderr.getvalue(), "error: Rust vendoring requires a native builder container\n")
        self.load_sources.assert_not_called()
        self.pull.side_effect = build.SandboxError("fixture image unavailable")
        with self.assertRaises(SystemExit) as failed_pull:
            build.fetch(self.options())
        self.assertEqual(failed_pull.exception.code, 2)
        self.assertTrue(self.stderr.getvalue().endswith("error: fixture image unavailable\n"))
        self.pull_reference.assert_not_called()
        self.install_tools.assert_not_called()
        self.run_fetch.assert_not_called()

    def assert_fetch_error(self, message: str, *, inside: bool = False) -> None:
        self.stderr.seek(0)
        self.stderr.truncate()
        with self.assertRaises(SystemExit) as caught:
            build.fetch(self.options(inside=inside))
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.stderr.getvalue(), f"error: {message}\n")

    def test_fetch_requires_the_rustls_source_on_host_and_inside(self) -> None:
        self.load_sources.return_value = [self.selected, self.other]
        self.assert_fetch_error("source lock lacks rustls-ffi-source")
        with patch.object(build.sandbox, "in_container", return_value=True):
            self.assert_fetch_error("source lock lacks rustls-ffi-source", inside=True)
        self.install_tools.assert_not_called()
        self.vendor.assert_not_called()
        self.run_fetch.assert_not_called()

    def test_fetch_reports_lock_vendoring_and_native_admission_errors(self) -> None:
        self.load_sources.side_effect = build.InputError("fixture lock is invalid")
        self.assert_fetch_error("fixture lock is invalid")
        self.pull.assert_not_called()
        self.load_sources.side_effect = None
        self.install_tools.side_effect = build.rust.RustError("fixture cannot install Rust tools")
        self.assert_fetch_error("fixture cannot install Rust tools")
        self.run_fetch.assert_not_called()
        self.check_vendored.side_effect = build.tls.TlsError("fixture vendoring lock differs")
        with patch.object(build.sandbox, "in_container", return_value=True):
            self.assert_fetch_error("fixture vendoring lock differs", inside=True)
        with patch.object(build, "_NATIVE", None):
            self.assert_fetch_error("Rust vendoring requires a supported native machine")

    def test_doctor_reports_an_unsupported_native_host_without_toolchain(self) -> None:
        with patch.object(build, "_NATIVE", None), patch.object(build.shutil, "which", return_value=None):
            self.assertEqual(build.doctor(self.options()), 0)
        report = json.loads(self.stdout.getvalue())
        self.assertIsNone(report["native_target"])
        self.assertIsNone(report["toolchain"])
        self.assertIsNone(report["docker"])

    def test_doctor_reports_target_locks_missing_inputs_and_verified_toolchain(self) -> None:
        toolchain = self.work / "build" / self.target.triple / "phases/prepare/toolchain"
        toolchain.mkdir(parents=True)
        with (
            patch.object(build.platform, "machine", return_value="fixture-host"),
            patch.object(build.platform, "system", return_value="fixture-platform"),
            patch.object(build.shutil, "which", return_value="/fixture/bin/docker") as which,
        ):
            self.assertEqual(build.doctor(self.options()), 0)
        which.assert_called_once_with("docker")
        self.verify_toolchain.assert_called_once_with(toolchain, self.target)
        self.assertEqual(json.loads(self.stdout.getvalue()), {
            "host": "fixture-host", "platform": "fixture-platform", "python": sys.version.split()[0],
            "native_target": self.native.triple, "target": self.target.triple, "docker": "/fixture/bin/docker",
            "cache": str(self.cache_root), "phases": str(self.phases),
            "sources": {"total": 3, "selected": ["rustls-ffi-source", "target-source"], "bootstrap": ["target-package"]},
            "cache_missing": ["target-source"], "toolchain": {"clang": "fixture"},
        })
        self.cache.fetch.assert_not_called()

    def test_doctor_distinguishes_missing_toolchain_from_invalid_locks_or_tools(self) -> None:
        with patch.object(build.shutil, "which", return_value=None):
            self.assertEqual(build.doctor(self.options()), 0)
            self.assertIsNone(json.loads(self.stdout.getvalue())["toolchain"])
            self.verify_toolchain.assert_not_called()
            self.stdout.seek(0)
            self.stdout.truncate()
            self.load_bootstrap.side_effect = build.InputError("fixture lock is invalid")
            self.cache.require.reset_mock()
            self.assertEqual(build.doctor(self.options()), 1)
            report = json.loads(self.stdout.getvalue())
            self.assertEqual(report["locks"], "fixture lock is invalid")
            self.assertNotIn("sources", report)
            self.cache.require.assert_not_called()
            self.load_bootstrap.side_effect = None
            self.stdout.seek(0)
            self.stdout.truncate()
            (self.work / "build" / self.target.triple / "phases/prepare/toolchain").mkdir(parents=True)
            self.verify_toolchain.side_effect = build.toolchain.ToolchainError("fixture clang is missing")
            self.assertEqual(build.doctor(self.options()), 1)
            report = json.loads(self.stdout.getvalue())
            self.assertEqual(report["toolchain_error"], "fixture clang is missing")
            self.assertNotIn("toolchain", report)
