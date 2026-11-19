from __future__ import annotations

import errno
import os
import signal
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from helpers import workspace

from buildsys import benchmark_process


class ChildExit(Exception):
    pass


class BenchmarkAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.process = SimpleNamespace(
            fork=Mock(return_value=431),
            chdir=Mock(), dup2=Mock(), getpid=Mock(return_value=431),
            kill=Mock(), execvpe=Mock(),
            wait4=Mock(side_effect=AssertionError("unexpected wait4")),
            waitpid=Mock(side_effect=AssertionError("unexpected waitpid")),
            write=Mock(), _exit=Mock(side_effect=ChildExit),
            strerror=os.strerror, WIFEXITED=os.WIFEXITED, WIFSIGNALED=os.WIFSIGNALED,
            WIFSTOPPED=lambda status: status != 0xFFFF and os.WIFSTOPPED(status), WSTOPSIG=os.WSTOPSIG,
            waitstatus_to_exitcode=os.waitstatus_to_exitcode,
        )
        replacement = patch.object(benchmark_process, "os", self.process)
        replacement.start()
        self.addCleanup(replacement.stop)

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
            def exited_image() -> int:
                self.assertEqual(wait.call_count, 3)
                return 1280

            peak.side_effect = lambda _pid: exited_image()
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

    def test_empty_command_leaves_output_untouched(self) -> None:
        with workspace() as directory:
            output = directory / "output"
            output.write_bytes(b"previous output")
            with self.assertRaises(benchmark_process.MeasurementError) as caught:
                benchmark_process.run([], cwd=directory, env={}, output=output)
            self.assertEqual(str(caught.exception), "cannot measure an empty command")
            self.assertEqual(output.read_bytes(), b"previous output")
        self.process.fork.assert_not_called()

    def test_child_sets_up_the_command_and_reports_launch_failure(self) -> None:
        self.process.fork.return_value = 0
        command = ["fixture", "argument"]
        environment = {"FIXTURE": "value"}
        self.process.execvpe.side_effect = FileNotFoundError("fixture executable missing: \udcff")
        with workspace() as directory, patch.object(benchmark_process, "_trace") as trace:
            with self.assertRaises(ChildExit):
                benchmark_process.run(command, cwd=directory, env=environment, output=directory / "output")
            self.process.chdir.assert_called_once_with(directory)
        descriptors = self.process.dup2.call_args_list
        self.assertEqual(len(descriptors), 2)
        fd = descriptors[0].args[0]
        self.assertEqual(descriptors, [call(fd, 1), call(fd, 2)])
        trace.assert_called_once_with(0, 0)
        self.process.kill.assert_called_once_with(431, signal.SIGSTOP)
        self.process.execvpe.assert_called_once_with("fixture", command, environment)
        self.process.write.assert_called_once_with(2, b"benchmark process setup failed: fixture executable missing: ?\n")
        self.process._exit.assert_called_once_with(127)
        self.process.wait4.assert_not_called()

    def test_reaps_the_traced_process_when_measurement_fails(self) -> None:
        pid = 431
        setup_stop = (signal.SIGSTOP << 8) | 0x7F
        cases = (
            ([(pid, (signal.SIGTERM << 8) | 0x7F, None)], "benchmark process could not be traced"),
            ([(pid, setup_stop, None), (pid, 0xFFFF, None)], "unexpected benchmark process status"),
        )
        for statuses, message in cases:
            with (
                self.subTest(message=message),
                workspace() as directory,
                patch.object(benchmark_process.os, "wait4", side_effect=statuses),
                patch.object(benchmark_process, "_trace"),
                patch.object(benchmark_process, "_reap_after_failure") as reap,
                self.assertRaises(benchmark_process.MeasurementError) as caught,
            ):
                benchmark_process.run(["fixture"], cwd=directory, env={}, output=directory / "output")
            self.assertEqual(str(caught.exception), message)
            reap.assert_called_once_with(pid)

    def test_reap_retries_stopped_children_and_accepts_no_remaining_child(self) -> None:
        pid = 431
        stop = (signal.SIGSTOP << 8) | 0x7F
        cases = (
            (None, [(pid, stop), (pid, signal.SIGKILL)], None, 2, [call(7, pid, signal.SIGKILL)]),
            (ProcessLookupError(), [(pid, stop), ChildProcessError()], ProcessLookupError(), 2, [call(7, pid, signal.SIGKILL)]),
            (None, [(pid, 7 << 8)], None, 1, []),
        )
        for kill_error, statuses, continue_error, waits, trace_calls in cases:
            with (
                self.subTest(statuses=statuses),
                patch.object(benchmark_process.os, "kill", side_effect=kill_error) as kill,
                patch.object(benchmark_process.os, "waitpid", side_effect=statuses) as wait,
                patch.object(benchmark_process, "_trace", side_effect=continue_error) as trace,
            ):
                benchmark_process._reap_after_failure(pid)
            kill.assert_called_once_with(pid, signal.SIGKILL)
            self.assertEqual(wait.call_args_list, [call(pid, 0)] * waits)
            self.assertEqual(trace.call_args_list, trace_calls)
