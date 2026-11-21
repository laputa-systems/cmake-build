from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from helpers import workspace

import build


class ControllerCliTests(unittest.TestCase):
    def test_routes_commands_and_preserves_their_selected_arguments(self) -> None:
        cases = (
            ("doctor", build.doctor, [], {}),
            ("fetch", build.fetch, ["--vendor-in-container"], {"vendor_in_container": True}),
            ("prepare", build.prepare, ["--in-container"], {"in_container": True}),
            ("configure", build.configure, ["--in-container"], {"in_container": True}),
            ("build", build.build_command, ["--in-container", "--qualification-build"], {"in_container": True, "qualification_build": True}),
            ("test", build.test_command, ["--in-container", "--suite", "projects,network"], {"in_container": True, "suite": "projects,network"}),
            ("package", build.package_command, ["--in-container"], {"in_container": True}),
            ("qualify", build.qualify_command, [], {}),
            ("reproduce", build.reproduce_command, [], {}),
            ("benchmark", build.benchmark_command, [], {}),
        )
        parser = build._parser()
        self.assertEqual(parser.prog, "build.py")
        selected = "aarch64-unknown-linux-musl"
        for command, handler, inputs, expected in cases:
            with self.subTest(command=command):
                parsed = parser.parse_args([command, "--target", selected, *inputs])
                self.assertEqual((parsed.command, parsed.target), (command, selected))
                self.assertIs(parsed.handler, handler)
                for name, value in expected.items():
                    self.assertEqual(getattr(parsed, name), value)
                self.assertEqual(parser.parse_args([command, *inputs]).target, build.DEFAULT_TARGET)
                with contextlib.redirect_stdout(io.StringIO()) as help_text, self.assertRaises(SystemExit) as help_exit:
                    parser.parse_args([command, "--help"])
                self.assertEqual(help_exit.exception.code, 0)
                for option in ("--vendor-in-container", "--in-container", "--qualification-build"):
                    self.assertNotIn(option, help_text.getvalue())
        parsed = parser.parse_args(["controller-test", "-k", "fixture"])
        self.assertEqual((parsed.command, parsed.filter), ("controller-test", "fixture"))
        self.assertIs(parsed.handler, build._controller_test)

    def test_parser_rejects_missing_commands_and_required_suite(self) -> None:
        for inputs in ([], ["unknown"], ["test"]):
            with self.subTest(inputs=inputs), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                build._parser().parse_args(inputs)

    def test_dispatches_arguments_and_preserves_a_real_exit_code(self) -> None:
        handler = Mock(return_value=17)
        parsed = argparse.Namespace(handler=handler)
        arguments = ["benchmark", "--target", "aarch64-unknown-linux-musl"]
        with patch.object(build, "_parser") as parser:
            parser.return_value.parse_args.return_value = parsed
            self.assertEqual(build.main(arguments), 17)
        parser.return_value.parse_args.assert_called_once_with(arguments)
        handler.assert_called_once_with(parsed)

    def test_controller_sums_results_and_rejects_an_empty_or_failing_module(self) -> None:
        with workspace() as root:
            directory = root / "tests/controller"
            directory.mkdir(parents=True)
            modules = {
                "test_fixture_ok.py": (0, "progress\nRan 2 tests in 0.02s\n"),
                "test_fixture_bad.py": (7, "Ran 1 test in 0.01s\n"),
                "test_fixture_empty.py": (0, "runner produced no count\n"),
                "test_other.py": (0, "Ran 1 test in 0.01s\n"),
            }
            for name in modules:
                (directory / name).write_text("")

            def execute(command: list[str], **options: object) -> subprocess.CompletedProcess[str]:
                module = command[-1]
                self.assertEqual(command, [sys.executable, "-m", "unittest", "discover", "-s", "tests/controller", "-p", module])
                self.assertEqual(options, {
                    "cwd": root, "capture_output": True, "text": True, "check": False,
                    "env": {**os.environ, "PYTHONPATH": str(root)},
                })
                status, receipt = modules[module]
                return subprocess.CompletedProcess(command, status, stdout=f"{module} output\n", stderr=receipt)

            with (
                patch.object(build, "ROOT", root),
                patch.object(build.subprocess, "run", side_effect=execute) as run,
                patch.object(build.time, "monotonic", side_effect=[10.0, 10.5, 20.0, 20.2]),
                patch.object(build.os, "cpu_count", return_value=2),
                patch.object(build, "ThreadPoolExecutor", wraps=build.ThreadPoolExecutor) as executor,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(build._controller_test(argparse.Namespace(scope="all", filter="fixture")), 1)
                self.assertEqual(build._controller_test(argparse.Namespace(scope="all", filter="other")), 0)
            self.assertEqual(run.call_count, 4)
            self.assertEqual([item.kwargs for item in executor.call_args_list], [{"max_workers": 2}, {"max_workers": 1}])
            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    "--- test_fixture_bad.py (exit 7, 1 tests)", "test_fixture_bad.py output", "Ran 1 test in 0.01s", "",
                    "--- test_fixture_empty.py (exit 0, 0 tests)", "test_fixture_empty.py output", "runner produced no count", "",
                    "Ran 3 tests in 3 modules in 0.5s; 2 failed: test_fixture_bad.py, test_fixture_empty.py",
                    "Ran 1 tests in 1 modules in 0.2s; 0 failed",
                ],
            )

    def test_controller_rejects_no_matching_modules_without_launching_processes(self) -> None:
        with (
            workspace() as root,
            patch.object(build, "ROOT", root),
            patch.object(build.subprocess, "run", side_effect=AssertionError("unexpected subprocess")) as run,
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            tests = root / "tests/controller"
            tests.mkdir(parents=True)
            (tests / "test_other.py").write_text("")
            self.assertEqual(build._controller_test(argparse.Namespace(scope="all", filter="missing")), 1)
        run.assert_not_called()
        self.assertEqual(error.getvalue(), "error: no controller test modules match 'missing'\n")

    def test_controller_scope_separates_portable_from_prepared_native_modules(self) -> None:
        launched: list[str] = []

        def execute(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            launched.append(command[-1])
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="Ran 1 test in 0.0s")

        with (
            workspace() as root,
            patch.object(build, "ROOT", root),
            patch.object(build.subprocess, "run", side_effect=execute),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            tests = root / "tests/controller"
            tests.mkdir(parents=True)
            for name in ("test_native_audit.py", "test_native_tls.py", "test_tls.py", "test_cli.py"):
                (tests / name).write_text("")
            for scope, expected in (
                ("portable", ["test_cli.py", "test_tls.py"]),
                ("native", ["test_native_audit.py", "test_native_tls.py"]),
                ("all", ["test_cli.py", "test_native_audit.py", "test_native_tls.py", "test_tls.py"]),
            ):
                with self.subTest(scope=scope):
                    launched.clear()
                    self.assertEqual(build._controller_test(argparse.Namespace(scope=scope, filter=None)), 0)
                    self.assertEqual(sorted(launched), expected)
        self.assertEqual(build._parser().parse_args(["controller-test"]).scope, "all")

    def test_controller_bounds_worker_count_without_a_cpu_count(self) -> None:
        with (
            workspace() as root,
            patch.object(build, "ROOT", root),
            patch.object(build.os, "cpu_count", return_value=None),
            patch.object(build, "ThreadPoolExecutor", wraps=build.ThreadPoolExecutor) as executor,
            patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="Ran 1 test in 0.0s")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            tests = root / "tests/controller"
            tests.mkdir(parents=True)
            for index in range(6):
                (tests / f"test_{index}.py").write_text("")
            self.assertEqual(build._controller_test(argparse.Namespace(scope="all", filter=None)), 0)
        executor.assert_called_once_with(max_workers=4)

    def test_dispatch_reports_controller_errors_and_invalid_status(self) -> None:
        handler = Mock()
        for outcome, message in (
            (build.InputError("fixture acquisition failed"), "fixture acquisition failed"),
            ("17", "command did not return an integer exit status"),
        ):
            with (
                self.subTest(message=message),
                patch.object(build, "_parser") as parser,
                contextlib.redirect_stderr(io.StringIO()) as error,
                self.assertRaises(SystemExit) as caught,
            ):
                parser.return_value.parse_args.return_value = argparse.Namespace(handler=handler)
                handler.side_effect = outcome if isinstance(outcome, Exception) else None
                handler.return_value = outcome
                build.main([])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(error.getvalue(), f"error: {message}\n")

    def test_source_identity_requires_committed_inputs_and_a_full_revision(self) -> None:
        expected = "0123456789abcdef0123456789abcdef01234567"
        with workspace() as root, patch.object(build, "ROOT", root):
            with patch.object(build.subprocess, "run", side_effect=[
                subprocess.CompletedProcess([], 0, stdout=""),
                subprocess.CompletedProcess([], 0, stdout=f"{expected}\n"),
            ]) as git:
                self.assertEqual(build._source_commit(), expected)
            status, revision = git.call_args_list
            self.assertEqual(status.args[0][:5], ["git", "status", "--porcelain", "--untracked-files=all", "--"])
            self.assertEqual(
                status.args[0][5:],
                ["build.py", "buildsys", "docker", "patches", "tests", "licenses", "NOTICE", "sources.lock.json", "bootstrap.lock.json", "release-budgets.json"],
            )
            self.assertEqual(revision.args[0], ["git", "rev-parse", "HEAD"])
            self.assertEqual(status.kwargs, {"cwd": root, "capture_output": True, "text": True, "check": True})
            self.assertEqual(revision.kwargs, status.kwargs)
            cases = (
                ([" M build.py\n"], "packaging requires committed build and qualification inputs"),
                (["", expected[:8]], "repository commit identity is invalid"),
            )
            for results, message in cases:
                with (
                    self.subTest(message=message),
                    patch.object(build.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0, stdout=result) for result in results]) as git,
                    contextlib.redirect_stderr(io.StringIO()) as error,
                    self.assertRaises(SystemExit) as caught,
                ):
                    build._source_commit()
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual(error.getvalue(), f"error: {message}\n")
                self.assertEqual(git.call_count, len(results))
