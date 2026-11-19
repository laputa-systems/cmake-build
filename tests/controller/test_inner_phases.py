from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import workspace

import build


class InnerPhaseWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.root: Path = self.enterContext(workspace())
        self.work = self.root / ".work"
        self.target = build._target("aarch64-unknown-linux-musl")
        self.phases = self.work / "build" / self.target.triple / "phases"
        self.prepared = self.phases / "prepare"
        self.bootstrap = self.phases / "bootstrap"
        self.archive = self.work / "rust" / self.target.triple / "phases/static/target/release/lib/librustls.a"
        for directory, digest in (
            (self.prepared, "prepare-digest"),
            (self.bootstrap, "bootstrap-digest"),
            (self.archive.parents[3], "rustls-digest"),
        ):
            self.write_record(directory, digest)
        self.cache_path = self.work / "cache"
        self.cmake = self.input("cmake-source", "4.3.3", "c")
        self.samurai = self.input("samurai-source", "1.3", "s")
        self.ninja = self.input("ninja-source", "1.13.2", "n")
        self.rustls = self.input("rustls-ffi-source", "0.15.0", "r")
        self.sources = [self.cmake, self.samurai, self.ninja, self.rustls]
        self.package = self.input("cmake", "4.2.1-r3", "p")
        self.lock = build.BootstrapLock("fixture-index", "fixture-reference", {self.target.triple: (self.package,)})
        self.inventory = (build.patches.Patch("fix.patch", "p" * 64, b"patch"),)
        self.kache = self.work / "tmp/build-kache"
        self.enterContext(patch.multiple(
            build, ROOT=self.root, WORK=self.work, CACHE=self.cache_path, BUILD_ROOT=self.work / "build",
            SOURCES_LOCK=self.root / "sources.lock.json", BOOTSTRAP_LOCK=self.root / "bootstrap.lock.json",
            DOCKERFILE=self.root / "docker/builder.Dockerfile",
        ))
        self.load_sources = self.enterContext(patch.object(build, "load_sources", return_value=self.sources))
        self.load_bootstrap = self.enterContext(patch.object(build, "load_bootstrap", return_value=self.lock))
        self.controller = self.enterContext(patch.object(build, "_controller_digest", return_value="controller-digest"))
        self.image = self.enterContext(patch.object(build.sandbox, "image_fingerprint", return_value="image-digest"))
        self.cache_factory = self.enterContext(patch.object(build, "Cache"))
        self.cache_factory.return_value.require.side_effect = lambda item: self.cache_path / item.name
        self.phase_factory = self.enterContext(patch.object(build, "PhaseCache"))
        self.phase = self.phase_factory.return_value
        self.phase.directory.side_effect = lambda name: self.phases / name
        self.phase.run.side_effect = self.run_phase
        self.reused_phases = {"configure"}
        self.verify_tools = self.enterContext(patch.object(build.toolchain, "verify"))
        self.bootstrap_build = self.enterContext(patch.object(build.bootstrap, "build"))
        self.bootstrap_configure = self.enterContext(patch.object(build.bootstrap, "configure"))
        self.verify_inventory = self.enterContext(patch.object(build.patches, "verify_inventory", return_value=self.inventory))
        self.rust_build = self.enterContext(patch.object(build.rust, "build_static", return_value=self.archive))
        self.wrapper = self.enterContext(patch.object(build.rust, "wrapper_identity", return_value="compiler-digest"))
        self.cmake_build = self.enterContext(patch.object(build.cmake, "build"))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    @staticmethod
    def input(name: str, version: str, sha: str) -> build.Input:
        return build.Input(name=name, version=version, target="all", size=1, sha256=sha * 64,
                           role="source", urls=("https://example.invalid/source.tar.xz",))

    @staticmethod
    def write_record(directory: Path, digest: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "phase.json").write_text(json.dumps({"output_digest": digest}))

    def run_phase(self, name: str, _inputs: dict[str, str], action: Callable[[Path], None]) -> SimpleNamespace:
        directory = self.phases / name
        action(directory)
        return SimpleNamespace(directory=directory, fingerprint="fingerprint-0123456789", reused=name in self.reused_phases)

    def assert_locks_and_image(self) -> None:
        self.load_sources.assert_called_once_with(self.root / "sources.lock.json")
        self.load_bootstrap.assert_called_once_with(self.root / "bootstrap.lock.json")
        self.image.assert_called_once_with(self.lock, self.target, self.root / "docker/builder.Dockerfile")
        self.phase_factory.assert_called_once_with(self.phases)


class InnerPhaseTests(InnerPhaseWorkspace):
    def test_configure_reuses_prepared_fingerprints_and_builds_locked_bootstrap(self) -> None:
        prepare = self.enterContext(patch.object(build, "_prepare_inside", return_value=0))
        self.assertEqual(build._configure_inside(self.target), 0)
        self.assert_locks_and_image()
        prepare.assert_called_once_with(self.target)
        self.cache_factory.assert_called_once_with(self.cache_path, offline=True)
        self.phase.directory.assert_called_once_with("prepare")
        tc = self.prepared / "toolchain"
        self.verify_tools.assert_called_once_with(tc, self.target)
        self.assertEqual([request.args[:2] for request in self.phase.run.call_args_list], [
            ("bootstrap", {
                "prepare": "prepare-digest", "cmake": self.cmake.sha256, "samurai": self.samurai.sha256,
                "ninja": self.ninja.sha256, "image": "image-digest", "controller": "controller-digest",
            }),
            ("configure", {"bootstrap": "bootstrap-digest", "image": "image-digest", "controller": "controller-digest"}),
        ])
        self.bootstrap_build.assert_called_once_with(
            cmake_archive=self.cache_path / self.cmake.name, samurai_archive=self.cache_path / self.samurai.name,
            ninja_archive=self.cache_path / self.ninja.name, directory=self.bootstrap, tc=tc,
            sysroot=self.prepared / "sysroot", target=self.target, bootstrap_version="4.2.1",
        )
        self.bootstrap_configure.assert_called_once_with(self.bootstrap, self.phases / "configure", tc, self.target)
        self.assertEqual(self.stdout.getvalue(), f"configure reused at {self.phases / 'configure'} (fingerprint-0123)\n")
        self.reused_phases.clear()
        self.stdout.seek(0)
        self.stdout.truncate()
        self.assertEqual(build._configure_inside(self.target), 0)
        self.assertEqual(self.stdout.getvalue(), f"configure built at {self.phases / 'configure'} (fingerprint-0123)\n")

    def test_configure_rejects_missing_duplicate_or_invalid_bootstrap_package(self) -> None:
        self.enterContext(patch.object(build, "_prepare_inside", return_value=0))
        for packages, diagnostic in (
            ((), "lock must contain exactly one bootstrap CMake package"),
            ((self.package, self.package), "lock must contain exactly one bootstrap CMake package"),
            ((self.input("cmake", "4.2.1", "p"),), "invalid bootstrap CMake package version '4.2.1'"),
        ):
            with self.subTest(packages=packages), self.assertRaises(SystemExit) as caught:
                self.stderr.seek(0)
                self.stderr.truncate()
                self.load_bootstrap.return_value = build.BootstrapLock("fixture-index", "fixture-reference", {self.target.triple: packages})
                build._configure_inside(self.target)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), f"error: {self.target.triple}: {diagnostic}\n")
        self.verify_tools.assert_not_called()
        self.bootstrap_build.assert_not_called()
        self.phase.run.assert_not_called()

    def test_build_binds_exact_phase_outputs_and_mode(self) -> None:
        configure = self.enterContext(patch.object(build, "_configure_inside", return_value=0))
        cmake_phase = self.phases / "cmake"
        for mode in build.cmake.BuildMode:
            with self.subTest(mode=mode):
                for mock in (configure, self.load_sources, self.load_bootstrap, self.image, self.phase_factory,
                             self.phase.run, self.verify_inventory, self.rust_build, self.wrapper, self.cmake_build):
                    mock.reset_mock()
                self.stdout.seek(0)
                self.stdout.truncate()
                reused = mode is build.cmake.BuildMode.DEVELOPMENT
                self.reused_phases = {"cmake"} if reused else set()
                self.assertEqual(build._build_inside(self.target, mode), 0)
                self.assert_locks_and_image()
                configure.assert_called_once_with(self.target)
                self.verify_inventory.assert_called_once_with(self.root / "patches")
                self.rust_build.assert_called_once_with(self.work / "rust" / self.target.triple, self.prepared,
                                                        self.target, self.kache, self.work / "tmp")
                patch_bytes = json.dumps([["fix.patch", "p" * 64]], separators=(",", ":")).encode()
                expected = {
                    "prepare": "prepare-digest", "bootstrap": "bootstrap-digest", "rustls": "rustls-digest",
                    "patches": hashlib.sha256(patch_bytes).hexdigest(), "image": "image-digest",
                    "controller": "controller-digest", "mode": hashlib.sha256(mode.value.encode()).hexdigest(),
                }
                if mode is build.cmake.BuildMode.DEVELOPMENT:
                    self.wrapper.assert_called_once_with(self.kache)
                    expected["compiler_cache"] = "compiler-digest"
                else:
                    self.wrapper.assert_not_called()
                self.phase.run.assert_called_once()
                self.assertEqual(self.phase.run.call_args.args[:2], ("cmake", expected))
                self.cmake_build.assert_called_once_with(
                    bootstrap=self.bootstrap, prepared=self.prepared, archive=self.archive, inventory=self.inventory,
                    directory=cmake_phase, target=self.target, cmake_version=self.cmake.version,
                    rustls_version=self.rustls.version, mode=mode, kache=self.kache,
                    compiler_cache=self.work / "compiler-cache" / self.target.triple,
                )
                outcome = "reused" if reused else "built"
                self.assertEqual(self.stdout.getvalue(), f"cmake {outcome} at {cmake_phase} (fingerprint-0123)\n")

    def test_build_rejects_either_missing_source_before_compiling(self) -> None:
        with patch.object(build, "_configure_inside", return_value=0):
            for source in (self.cmake, self.rustls):
                with self.subTest(source=source.name):
                    self.load_sources.return_value = [item for item in self.sources if item != source]
                    self.stderr.seek(0)
                    self.stderr.truncate()
                    with self.assertRaises(SystemExit) as caught:
                        build._build_inside(self.target, build.cmake.BuildMode.QUALIFICATION)
                    self.assertEqual(caught.exception.code, 2)
                    self.assertEqual(self.stderr.getvalue(), "error: source lock lacks CMake or Rustls\n")
        self.verify_inventory.assert_not_called()
        self.rust_build.assert_not_called()
        self.phase.run.assert_not_called()


class PreparePhaseTests(InnerPhaseWorkspace):
    def setUp(self) -> None:
        super().setUp()
        self.toolchain = self.input("llvm-toolchain-aarch64", "23.0", "l")
        self.musl = self.input("musl-source", "1.2.6", "m")
        self.headers = self.input("linux-headers", "6.19-r0", "h")
        self.load_sources.return_value = [self.toolchain, self.musl]
        self.lock = build.BootstrapLock("fixture-index", "fixture-reference", {self.target.triple: (self.headers,)})
        self.load_bootstrap.return_value = self.lock
        self.toolchain_dir = self.prepared / "toolchain"
        self.sysroot = self.prepared / "sysroot"
        self.provenance = self.root / "tests/fixtures/provenance/run.py"
        self.enterContext(patch.object(build, "PROVENANCE", self.provenance))
        self.install_toolchain = self.enterContext(patch.object(build.toolchain, "install", return_value=self.toolchain_dir))
        self.build_sysroot = self.enterContext(patch.object(build.sysroot, "build"))
        self.verify_sysroot = self.enterContext(patch.object(build.sysroot, "verify", return_value={"arch": "aarch64"}))
        self.verify_tools.return_value = {"clang": "fixture-clang"}
        self.run_fixture = self.enterContext(patch.object(build.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout="  fixture success\n", stderr="",
        )))

    def test_prepare_binds_locked_inputs_and_writes_verified_reports(self) -> None:
        with patch.dict(build.os.environ, {"PATH": "/fixture/bin"}, clear=True):
            self.assertEqual(build._prepare_inside(self.target), 0)
        self.assert_locks_and_image()
        self.cache_factory.assert_called_once_with(self.cache_path, offline=True)
        self.verify_inventory.assert_called_once_with(self.root / "patches")
        self.phase.run.assert_called_once()
        self.assertEqual(self.phase.run.call_args.args[:2], ("prepare", {
            "toolchain": self.toolchain.sha256, "musl": self.musl.sha256, "linux-headers": self.headers.sha256,
            "controller": "controller-digest", "image": "image-digest",
        }))
        self.install_toolchain.assert_called_once_with(self.cache_path / self.toolchain.name, self.toolchain_dir)
        self.verify_tools.assert_called_once_with(self.toolchain_dir, self.target)
        self.build_sysroot.assert_called_once_with(
            self.cache_path / self.musl.name, self.cache_path / self.headers.name,
            self.toolchain_dir, self.target, self.sysroot, self.work / "tmp" / f"sysroot-{os.getpid()}",
        )
        self.verify_sysroot.assert_called_once_with(self.sysroot, self.target, self.toolchain_dir)
        self.run_fixture.assert_called_once_with(
            [sys.executable, str(self.provenance), "--toolchain", str(self.toolchain_dir), "--sysroot", str(self.sysroot),
             "--target", self.target.triple, "--work", str(self.prepared / "fixture"),
             "--output", str(self.prepared / "provenance.json")],
            cwd=self.root, capture_output=True, text=True, check=False,
            env={"PATH": "/fixture/bin", "PYTHONPATH": str(self.root)},
        )
        self.assertEqual((self.prepared / "toolchain.json").read_bytes(), b'{\n  "clang": "fixture-clang"\n}\n')
        self.assertEqual((self.prepared / "sysroot.json").read_bytes(), b'{\n  "arch": "aarch64"\n}\n')
        self.assertEqual(self.stdout.getvalue(), f"fixture success\nprepare built at {self.prepared} (fingerprint-0123)\n")
        self.reused_phases.add("prepare")
        self.stdout.seek(0)
        self.stdout.truncate()
        with patch.dict(build.os.environ, {"PATH": "/fixture/bin"}, clear=True):
            self.assertEqual(build._prepare_inside(self.target), 0)
        self.assertEqual(self.stdout.getvalue(), f"fixture success\nprepare reused at {self.prepared} (fingerprint-0123)\n")

    def test_prepare_rejects_missing_locked_inputs_before_install(self) -> None:
        cases = (([self.musl], (self.headers,)), ([self.toolchain], (self.headers,)), ([self.toolchain, self.musl], ()))
        for sources, packages in cases:
            with self.subTest(sources=sources, packages=packages), self.assertRaises(SystemExit) as caught:
                self.load_sources.return_value = sources
                self.load_bootstrap.return_value = build.BootstrapLock("fixture-index", "fixture-reference", {self.target.triple: packages})
                self.stderr.seek(0)
                self.stderr.truncate()
                build._prepare_inside(self.target)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), f"error: {self.target.triple}: lock lacks toolchain, musl, or linux-headers\n")
        self.phase.run.assert_not_called()
        self.install_toolchain.assert_not_called()
        self.build_sysroot.assert_not_called()

    def test_prepare_reports_lock_error_before_cache_or_install(self) -> None:
        self.load_sources.side_effect = build.InputError("fixture source lock is invalid")
        with self.assertRaises(SystemExit) as caught:
            build._prepare_inside(self.target)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.stderr.getvalue(), "error: fixture source lock is invalid\n")
        self.cache_factory.assert_not_called()
        self.install_toolchain.assert_not_called()
        self.phase.run.assert_not_called()

    def test_prepare_reports_failed_provenance_with_both_streams(self) -> None:
        self.run_fixture.return_value = SimpleNamespace(returncode=7, stdout="fixture out", stderr="fixture error")
        with patch.dict(build.os.environ, {"PATH": "/fixture/bin"}, clear=True), self.assertRaises(SystemExit) as caught:
            build._prepare_inside(self.target)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.stderr.getvalue(), "error: provenance fixture failed (7):\nfixture out\nfixture error\n")
        self.assertEqual(self.stdout.getvalue(), "")
