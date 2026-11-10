from __future__ import annotations

import ctypes
import os
import signal
from dataclasses import dataclass
from pathlib import Path


class MeasurementError(Exception):
    pass


@dataclass(frozen=True)
class Result:
    returncode: int
    cpu_seconds: float
    max_rss_kib: int


_libc = ctypes.CDLL(None, use_errno=True)
_libc.ptrace.restype = ctypes.c_long
_TRACE_ME = 0
_CONTINUE = 7
_SET_OPTIONS = 0x4200
_TRACE_EXEC = 0x10
_TRACE_EXIT = 0x40
_EXIT_KILL = 0x00100000
_EVENT_EXIT = 6


def _trace(request: int, pid: int, data: int = 0) -> None:
    if _libc.ptrace(request, pid, None, ctypes.c_void_p(data)) < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _peak(pid: int) -> int:
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        if line.startswith('VmHWM:'):
            fields = line.split()
            if len(fields) == 3 and fields[2] == 'kB' and fields[1].isdigit() and int(fields[1]) > 0:
                return int(fields[1])
    raise MeasurementError('process image peak RSS was unavailable at exit')


def _reap_after_failure(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    while True:
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            return
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            return
        if os.WIFSTOPPED(status):
            try:
                _trace(_CONTINUE, pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def run(command: list[str], *, cwd: Path, env: dict[str, str], output: Path) -> Result:
    if not command:
        raise MeasurementError('cannot measure an empty command')
    with output.open('wb') as stream:
        pid = os.fork()
        if pid == 0:
            try:
                os.chdir(cwd)
                os.dup2(stream.fileno(), 1)
                os.dup2(stream.fileno(), 2)
                _trace(_TRACE_ME, 0)
                os.kill(os.getpid(), signal.SIGSTOP)
                os.execvpe(command[0], command, env)
            except BaseException as error:
                os.write(2, f'benchmark process setup failed: {error}\n'.encode(errors='replace'))
                os._exit(127)
        reaped = False
        try:
            _, status, _ = os.wait4(pid, 0)
            if not os.WIFSTOPPED(status) or os.WSTOPSIG(status) != signal.SIGSTOP:
                reaped = os.WIFEXITED(status) or os.WIFSIGNALED(status)
                raise MeasurementError('benchmark process could not be traced')
            _trace(_SET_OPTIONS, pid, _TRACE_EXEC | _TRACE_EXIT | _EXIT_KILL)
            _trace(_CONTINUE, pid)
            peak = None
            while True:
                _, status, usage = os.wait4(pid, 0)
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    reaped = True
                    if peak is None:
                        raise MeasurementError('benchmark process exited without an image RSS measurement')
                    return Result(os.waitstatus_to_exitcode(status), usage.ru_utime + usage.ru_stime, peak)
                if not os.WIFSTOPPED(status):
                    raise MeasurementError('unexpected benchmark process status')
                event = status >> 16
                if event == _EVENT_EXIT:
                    peak = _peak(pid)
                _trace(_CONTINUE, pid, 0 if event else os.WSTOPSIG(status))
        finally:
            if not reaped:
                _reap_after_failure(pid)
