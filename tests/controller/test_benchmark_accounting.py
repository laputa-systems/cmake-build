from __future__ import annotations

import errno
import os
import signal
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from helpers import workspace

from buildsys import benchmark_process


class BenchmarkAccountingTests(unittest.TestCase):
    def test_proc_peak_ignores_other_counters_and_requires_valid_units(self) -> None:
        with workspace() as directory:
            report = directory / "status"
            report.write_text("VmRSS: 8192 kB\nVmHWM: 0 kB\nVmHWM: unknown kB\nVmHWM: 2048 bytes\nVmHWM: 1280 kB\n")
            with patch.object(benchmark_process, "Path", return_value=report) as status:
                self.assertEqual(benchmark_process._peak(431), 1280)
            status.assert_called_once_with("/proc/431/status")
            report.write_text("VmHWM: 1 kB\n")
            with patch.object(benchmark_process, "Path", return_value=report):
                self.assertEqual(benchmark_process._peak(431), 1)
            for contents in ("VmRSS: 8192 kB\n", "VmHWM: 0 kB\n", "VmHWM: 42 kB extra\n"):
                with self.subTest(contents=contents):
                    report.write_text(contents)
                    with patch.object(benchmark_process, "Path", return_value=report), self.assertRaises(benchmark_process.MeasurementError) as caught:
                        benchmark_process._peak(431)
                    self.assertEqual(str(caught.exception), "process image peak RSS was unavailable at exit")

    def test_trace_success_uses_null_data_by_default(self) -> None:
        with patch.object(benchmark_process._libc, "ptrace", return_value=0) as ptrace:
            self.assertIsNone(benchmark_process._trace(7, 431))
        self.assertEqual(ptrace.call_args.args[:3], (7, 431, None))
        self.assertIsNone(ptrace.call_args.args[3].value)

    def test_trace_error_preserves_errno(self) -> None:
        with (
            patch.object(benchmark_process._libc, "ptrace", return_value=-1) as ptrace,
            patch.object(benchmark_process.ctypes, "get_errno", return_value=errno.ESRCH),
            self.assertRaises(ProcessLookupError) as caught,
        ):
            benchmark_process._trace(7, 431, signal.SIGTERM)
        self.assertEqual(caught.exception.errno, errno.ESRCH)
        self.assertEqual(str(caught.exception.strerror), os.strerror(errno.ESRCH))
        self.assertEqual(ptrace.call_args.args[:3], (7, 431, None))
        self.assertEqual(ptrace.call_args.args[3].value, signal.SIGTERM)

    def test_image_peak_and_usage_come_from_the_exit_event_and_final_status(self) -> None:
        pid = 431
        setup_stop = (signal.SIGSTOP << 8) | 0x7F
        signal_stop = (signal.SIGTERM << 8) | 0x7F
        exit_event = (6 << 16) | (signal.SIGTRAP << 8) | 0x7F
        usage = SimpleNamespace(ru_utime=0.5, ru_stime=0.25)
        statuses = [
            (pid, setup_stop, usage),
            (pid, signal_stop, usage),
            (pid, exit_event, usage),
            (pid, 7 << 8, usage),
        ]
        with (
            workspace() as directory,
            patch.object(benchmark_process.os, "fork", return_value=pid),
            patch.object(benchmark_process.os, "wait4", side_effect=statuses) as wait,
            patch.object(benchmark_process, "_trace") as trace,
            patch.object(benchmark_process, "_peak", return_value=1280) as peak,
            patch.object(benchmark_process, "_reap_after_failure") as reap,
        ):
            result = benchmark_process.run(["fixture"], cwd=directory, env={}, output=directory / "output")
        self.assertEqual(result, benchmark_process.Result(7, 0.75, 1280))
        peak.assert_called_once_with(pid)
        reap.assert_not_called()
        self.assertEqual(wait.call_args_list, [call(pid, 0)] * 4)
        self.assertEqual(
            trace.call_args_list,
            [call(0x4200, pid, 0x100050), call(7, pid), call(7, pid, signal.SIGTERM), call(7, pid, 0)],
        )

    def test_exit_without_image_evidence_never_returns_a_measurement(self) -> None:
        pid = 431
        setup_stop = (signal.SIGSTOP << 8) | 0x7F
        for statuses, message in (
            ([(pid, 127 << 8, None)], "benchmark process could not be traced"),
            ([(pid, setup_stop, None), (pid, 0, None)], "benchmark process exited without an image RSS measurement"),
        ):
            with (
                self.subTest(message=message),
                workspace() as directory,
                patch.object(benchmark_process.os, "fork", return_value=pid),
                patch.object(benchmark_process.os, "wait4", side_effect=statuses),
                patch.object(benchmark_process, "_trace"),
                patch.object(benchmark_process, "_reap_after_failure") as reap,
                self.assertRaises(benchmark_process.MeasurementError) as caught,
            ):
                benchmark_process.run(["fixture"], cwd=directory, env={}, output=directory / "output")
            self.assertEqual(str(caught.exception), message)
            reap.assert_not_called()
