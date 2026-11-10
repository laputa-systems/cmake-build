from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

import build
from helpers import ROOT, workspace


class CliTests(unittest.TestCase):
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
