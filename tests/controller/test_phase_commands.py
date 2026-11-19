from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from helpers import workspace

import build


class PhaseCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = self.enterContext(workspace())
        self.work = self.root / ".work"
        self.target = build._target("aarch64-unknown-linux-musl")
        self.lock = object()
        self.enterContext(patch.multiple(build, ROOT=self.root, WORK=self.work, BUILD_ROOT=self.work / "build", _NATIVE=self.target))
        self.enterContext(patch.object(build.platform, "machine", return_value=self.target.machine))
        self.enterContext(patch.object(build, "load_bootstrap", return_value=self.lock))
        self.enterContext(patch.object(build.sandbox, "image_tag", return_value="fixture-image"))
        for owner, function in (
            (build, "Cache"), (build, "_prepare_inside"), (build, "_configure_inside"), (build, "_build_inside"),
            (build.sandbox, "build_image"), (build.sandbox, "network_boundary_selftest"),
            (build.rust, "install_wrapper"), (build.patches, "verify_inventory"),
        ):
            self.enterContext(patch.object(owner, function, side_effect=AssertionError(f"unexpected {function}")))
        self.enterContext(patch.object(build.sandbox, "in_container", return_value=False))
        self.sealed = self.enterContext(patch.object(build.sandbox, "run_sealed", return_value=SimpleNamespace(
            returncode=0, stdout="fixture output\n", stderr="", network_mode="none", networks=[],
        )))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def options(self, *, inside: bool = False, qualification: bool = False) -> argparse.Namespace:
        return argparse.Namespace(target=self.target.triple, in_container=inside, qualification_build=qualification)

    def assert_invocation(self, phase: str, timeout: int, *extra: str) -> None:
        self.sealed.assert_called_once_with(
            "fixture-image",
            ["python3", "build.py", phase, "--target", self.target.triple, "--in-container", *extra],
            target=self.target,
            mounts=[(self.root, "/src")],
            env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"},
            timeout=timeout,
        )

    def test_host_prepare_uses_locked_inputs_and_writes_isolation_evidence(self) -> None:
        source = SimpleNamespace(name="fixture-source", target=self.target.triple)
        package = SimpleNamespace(name="fixture-package", target="all")
        other = SimpleNamespace(name="fixture-other", target="x86_64-unknown-linux-musl")
        common = SimpleNamespace(name="fixture-common", target="all")
        probe = {"ok": True, "interfaces": ["lo"]}
        with (
            patch.object(build.patches, "verify_inventory") as inventory,
            patch.object(build, "load_sources", return_value=[source, other, common]),
            patch.object(build, "bootstrap_inputs", return_value=[package]) as extra,
            patch.object(build, "Cache") as cache_factory,
            patch.object(build.sandbox, "build_image", return_value="fixture-image") as image,
            patch.object(build.sandbox, "network_boundary_selftest", return_value=probe) as boundary,
            patch.object(build.sandbox, "image_fingerprint", return_value="fixture-fingerprint") as fingerprint,
        ):
            self.assertEqual(build.prepare(self.options()), 0)
        inventory.assert_called_once_with(self.root / "patches")
        extra.assert_called_once_with(self.lock, self.target.triple)
        cache_factory.assert_called_once_with(build.CACHE)
        self.assertEqual(cache_factory.return_value.require.call_args_list, [call(source), call(common), call(package)])
        image.assert_called_once_with(self.lock, self.target, build.DOCKERFILE, cache_factory.return_value, self.work / "tmp/image")
        boundary.assert_called_once_with("fixture-image", self.target, self.work / "tmp/probe")
        fingerprint.assert_called_once_with(self.lock, self.target, build.DOCKERFILE)
        self.assert_invocation("prepare", 3600)
        path = self.work / "build" / self.target.triple / "isolation.json"
        self.assertEqual(json.loads(path.read_text()), {
            "image": "fixture-image", "image_fingerprint": "fixture-fingerprint",
            "network_mode": "none", "networks": [], "probe": probe,
        })

    def test_missing_inputs_and_failed_probe_prevent_launch(self) -> None:
        item = SimpleNamespace(name="fixture-source", target=self.target.triple)
        with (
            patch.object(build.patches, "verify_inventory"),
            patch.object(build, "load_sources", return_value=[item]),
            patch.object(build, "bootstrap_inputs", return_value=[]),
            patch.object(build, "Cache") as cache_factory,
            patch.object(build.sandbox, "build_image", return_value="fixture-image") as image,
            patch.object(build.sandbox, "network_boundary_selftest", return_value={"ok": False}),
        ):
            cache_factory.return_value.require.side_effect = build.InputError("fixture asset absent")
            with self.assertRaises(SystemExit) as missing:
                build.prepare(self.options())
            self.assertEqual(missing.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), "error: missing locked inputs: fixture-source; run `build.py fetch`\n")
            image.assert_not_called()
            cache_factory.return_value.require.side_effect = None
            with self.assertRaises(SystemExit) as failed_probe:
                build.prepare(self.options())
            self.assertEqual(failed_probe.exception.code, 2)
            self.assertTrue(self.stderr.getvalue().endswith('error: network boundary probe failed: {\n  "ok": false\n}\n'))
        self.sealed.assert_not_called()

    def test_prepare_configure_and_build_require_loopback_inside(self) -> None:
        commands = (
            ("prepare", build.prepare, "_prepare_inside", (self.target,)),
            ("configure", build.configure, "_configure_inside", (self.target,)),
            ("build", build.build_command, "_build_inside", (self.target, build.cmake.BuildMode.QUALIFICATION)),
        )
        with patch.object(build.patches, "verify_inventory"), patch.object(build.sandbox, "in_container") as container:
            for name, action, helper, arguments in commands:
                with self.subTest(phase=name), patch.object(build, helper, return_value=13) as inner:
                    container.return_value = False
                    with self.assertRaises(SystemExit):
                        action(self.options(inside=True, qualification=True))
                    container.return_value = True
                    with patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), self.assertRaises(SystemExit):
                        action(self.options(inside=True, qualification=True))
                    inner.assert_not_called()
                    with patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo")]):
                        self.assertEqual(action(self.options(inside=True, qualification=True)), 13)
                    inner.assert_called_once_with(*arguments)
                    self.assertIn(f"error: {name} requires a sealed container with only loopback networking\n", self.stderr.getvalue())
        self.sealed.assert_not_called()

    def test_configure_and_build_use_the_sealed_host_entry_point(self) -> None:
        with patch.object(build, "prepare", return_value=0) as prepare:
            self.assertEqual(build.configure(self.options()), 0)
        self.assertEqual(prepare.call_args.args[0], argparse.Namespace(target=self.target.triple, in_container=False))
        self.assert_invocation("configure", 3600)

        wrapper = self.root / "fixture-kache"
        self.sealed.reset_mock()
        with (
            patch.object(build, "configure", return_value=0) as configure,
            patch.object(build.shutil, "which", return_value=str(wrapper)),
            patch.object(build.rust, "install_wrapper") as install,
        ):
            self.assertEqual(build.build_command(self.options(qualification=True)), 0)
        self.assertEqual(configure.call_args.args[0], argparse.Namespace(target=self.target.triple, in_container=False))
        install.assert_called_once_with(Path(wrapper), self.work / "tmp")
        self.assert_invocation("build", 7200, "--qualification-build")


    def test_prepare_reports_wrong_machine_and_invalid_locked_inputs(self) -> None:
        with patch.object(build.patches, "verify_inventory"), patch.object(build, "load_sources") as sources:
            with patch.object(build.platform, "machine", return_value="x86_64"), self.assertRaises(SystemExit) as wrong:
                build.prepare(self.options())
            self.assertEqual(wrong.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), f"error: --target {self.target.triple} does not match the running machine (x86_64); no emulation is used\n")
            sources.assert_not_called()
            self.stderr.seek(0)
            self.stderr.truncate()
            sources.side_effect = build.InputError("fixture lock is invalid")
            with self.assertRaises(SystemExit) as invalid:
                build.prepare(self.options())
            self.assertEqual(invalid.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), "error: fixture lock is invalid\n")
        self.sealed.assert_not_called()

    def test_host_command_invocations_preserve_failures_and_require_kache(self) -> None:
        failure = SimpleNamespace(returncode=17, stdout="fixture output\n", stderr="fixture failure")
        self.sealed.return_value = failure
        with patch.object(build, "prepare", return_value=0), self.assertRaises(SystemExit) as configure:
            build.configure(self.options())
        self.assertEqual(configure.exception.code, 2)
        self.assert_invocation("configure", 3600)
        self.assertEqual(self.stderr.getvalue(), "fixture failure\nerror: configure failed inside the sealed container (17)\n")
        self.sealed.reset_mock()
        with patch.object(build, "configure", return_value=0), patch.object(build.shutil, "which", return_value=None), self.assertRaises(SystemExit) as missing:
            build.build_command(self.options())
        self.assertEqual(missing.exception.code, 2)
        self.assertTrue(self.stderr.getvalue().endswith("error: kache is required for Rust builds\n"))
        self.sealed.assert_not_called()
        with (
            patch.object(build, "configure", return_value=0),
            patch.object(build.shutil, "which", return_value=str(self.root / "kache")),
            patch.object(build.rust, "install_wrapper"),
            self.assertRaises(SystemExit) as build_exit,
        ):
            build.build_command(self.options())
        self.assertEqual(build_exit.exception.code, 2)
        self.assert_invocation("build", 7200)
        self.assertTrue(self.stderr.getvalue().endswith("fixture failure\nerror: build failed inside the sealed container (17)\n"))

    def test_inner_build_rejects_emulation_and_selects_development_by_default(self) -> None:
        with (
            patch.object(build.sandbox, "in_container", return_value=True),
            patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo")]),
            patch.object(build, "_build_inside", return_value=0) as inner,
        ):
            with patch.object(build, "_NATIVE", build._target("x86_64-unknown-linux-musl")), self.assertRaises(SystemExit) as caught:
                build.build_command(self.options(inside=True))
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(self.stderr.getvalue(), f"error: {self.target.triple} does not match the running machine; no emulation is used\n")
            inner.assert_not_called()
            self.assertEqual(build.build_command(self.options(inside=True)), 0)
        inner.assert_called_once_with(self.target, build.cmake.BuildMode.DEVELOPMENT)
