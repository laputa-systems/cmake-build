from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import build
from helpers import ROOT, workspace


class CliTests(unittest.TestCase):
    def test_test_command_dispatches_the_selected_suite(self) -> None:
        for name in ("basic", "parity", "network", "projects,upstream"):
            with self.subTest(suite=name), patch.object(build, "build_command") as compile_build, \
                    patch.object(build, "load_bootstrap"), patch.object(build.sandbox, "image_tag", return_value="image"), \
                    patch.object(build.sandbox, "run_sealed", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")), \
                    patch.object(build.qualify, "basic") as basic, patch.object(build.qualify, "parity") as parity, \
                    patch.object(build.qualify, "network") as network, patch.object(build.qualify, "projects") as projects, \
                    patch.object(build.qualify, "upstream") as upstream, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build.main(["test", "--target", "x86_64-unknown-linux-musl", "--suite", name]), 0)
                self.assertTrue(compile_build.call_args.args[0].qualification_build)
                for candidate, mock in (("basic", basic), ("parity", parity), ("network", network),
                                        ("projects", projects), ("upstream", upstream)):
                    self.assertEqual(mock.call_count, int(candidate in name.split(",")))

    def test_configure_rebuilds_when_builder_image_changes(self) -> None:
        target = build.describe_target("x86_64-unknown-linux-musl")
        sources = [SimpleNamespace(name=name, target="all", sha256=digest * 64) for name, digest in (
            ("cmake-source", "a"), ("samurai-source", "b"), ("ninja-source", "c"),
        )]
        with workspace() as directory:
            prepared = directory / target.triple / "phases/prepare"
            prepared.mkdir(parents=True)
            (prepared / "phase.json").write_text(json.dumps({"output_digest": "d" * 64}))

            def bootstrap_action(*, cmake_archive, samurai_archive, ninja_archive, directory, tc, sysroot, target, bootstrap_version):
                (directory / "bootstrap-output").write_text("built")

            def configure_action(bootstrap, output, tc, target):
                (output / "configured-output").write_text("built")

            with patch.object(build, "BUILD_ROOT", directory), patch.object(build, "_prepare_inside"), \
                    patch.object(build, "load_sources", return_value=sources), patch.object(build, "load_bootstrap"), \
                    patch.object(build, "bootstrap_inputs", return_value=[SimpleNamespace(name="cmake", version="4.3.4-r0")]), \
                    patch.object(build, "_controller_digest", return_value="e" * 64), \
                    patch.object(build.Cache, "require", lambda self, item: Path(item.name)), \
                    patch.object(build.toolchain, "verify"), \
                    patch.object(build.sandbox, "image_fingerprint", return_value="f" * 64) as image, \
                    patch.object(build.bootstrap, "build", side_effect=bootstrap_action) as bootstrap, \
                    patch.object(build.bootstrap, "configure", side_effect=configure_action) as configure, \
                    contextlib.redirect_stdout(io.StringIO()):
                build._configure_inside(target)
                build._configure_inside(target)
                self.assertEqual(bootstrap.call_count, 1)
                self.assertEqual(configure.call_count, 1)
                image.return_value = "0" * 64
                build._configure_inside(target)
                self.assertEqual(bootstrap.call_count, 2)
                self.assertEqual(configure.call_count, 2)

    def test_controller_digest_ignores_python_bytecode(self) -> None:
        with workspace() as directory:
            (directory / "buildsys/__pycache__").mkdir(parents=True)
            (directory / "tests/fixtures/native").mkdir(parents=True)
            provenance = directory / "provenance"
            (provenance / "__pycache__").mkdir(parents=True)
            (directory / "build.py").write_text("controller")
            dockerfile = directory / "Dockerfile"
            dockerfile.write_text("image")
            with patch.object(build, "ROOT", directory), patch.object(build, "DOCKERFILE", dockerfile), patch.object(build, "PROVENANCE", provenance / "run.py"):
                before = build._controller_digest()
                (directory / "buildsys/__pycache__/module.pyc").write_bytes(b"changed")
                (provenance / "__pycache__/run.pyc").write_bytes(b"changed")
                self.assertEqual(before, build._controller_digest())
    def test_internal_vendoring_rejects_host_execution(self) -> None:
        with patch.object(build.sandbox, "in_container", return_value=False), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                build.main(["fetch", "--target", "x86_64-unknown-linux-musl", "--vendor-in-container"])

    def test_every_command_is_registered(self) -> None:
        parser = build._parser()
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(["--help"])
        output = subprocess.run(
            [sys.executable, "build.py", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for command in (
            "doctor",
            "fetch",
            "prepare",
            "configure",
            "build",
            "test",
            "package",
            "qualify",
            "reproduce",
            "benchmark",
            "controller-test",
        ):
            self.assertIn(command, output)

    def test_doctor_reads_real_locks(self) -> None:
        with workspace() as directory, patch.object(build, "BUILD_ROOT", directory), contextlib.redirect_stdout(io.StringIO()) as output:
            status = build.main(["doctor", "--target", "x86_64-unknown-linux-musl"])
        self.assertEqual(status, 0)
        self.assertIn('"sources"', output.getvalue())

    def test_controller_test_rejects_empty_selection(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            status = build.main(["controller-test", "-k", "no-such-module"])
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
