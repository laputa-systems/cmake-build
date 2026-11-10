import mmap
import os
import platform
import resource
import signal
import sys
import unittest

from buildsys import benchmark_process
from helpers import workspace


@unittest.skipUnless(platform.system() == 'Linux', 'Linux process accounting is required')
class BenchmarkProcessTests(unittest.TestCase):
    def test_peak_rss_excludes_the_launchers_previous_high_water_mark(self) -> None:
        memory = mmap.mmap(-1, 128 * 1024 * 1024)
        memory[::4096] = b'x' * (len(memory) // 4096)
        memory.close()
        parent_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        with workspace() as directory:
            result = benchmark_process.run(['/bin/true'], cwd=directory, env=dict(os.environ),
                                           output=directory / 'output')
        self.assertEqual(result.returncode, 0)
        self.assertGreater(result.max_rss_kib, 0)
        self.assertLess(result.max_rss_kib, parent_peak // 2)

    def test_exit_status_and_output_are_preserved(self) -> None:
        with workspace() as directory:
            output = directory / 'output'
            result = benchmark_process.run(['/bin/sh', '-c', 'printf benchmark-error >&2; exit 7'],
                                           cwd=directory, env=dict(os.environ), output=output)
            self.assertEqual(result.returncode, 7)
            self.assertEqual(output.read_text(), 'benchmark-error')
            result = benchmark_process.run(['/bin/sh', '-c', 'kill -TERM $$'],
                                           cwd=directory, env=dict(os.environ), output=output)
            self.assertEqual(result.returncode, -signal.SIGTERM)
            result = benchmark_process.run(['/bin/sh', '-c', 'kill -TRAP $$'],
                                           cwd=directory, env=dict(os.environ), output=output)
            self.assertEqual(result.returncode, -signal.SIGTRAP)

    def test_peak_rss_excludes_a_larger_waited_child(self) -> None:
        with workspace() as directory:
            output = directory / 'output'
            baseline = benchmark_process.run([sys.executable, '-c', 'pass'], cwd=directory,
                                             env=dict(os.environ), output=output)
            program = ('import subprocess, sys; subprocess.run([sys.executable, "-c", '
                       '"x=bytearray(64*1024*1024)"], check=True)')
            result = benchmark_process.run([sys.executable, '-c', program], cwd=directory,
                                           env=dict(os.environ), output=output)
            self.assertEqual(result.returncode, 0)
            self.assertLess(result.max_rss_kib, baseline.max_rss_kib + 32 * 1024)

    def test_interruption_kills_and_reaps_the_measured_process(self) -> None:
        class Interrupted(Exception):
            pass

        def interrupt(signum, frame):
            raise Interrupted()

        previous = signal.signal(signal.SIGALRM, interrupt)
        try:
            with workspace() as directory:
                signal.setitimer(signal.ITIMER_REAL, 0.1)
                with self.assertRaises(Interrupted):
                    benchmark_process.run(['/bin/sleep', '10'], cwd=directory, env=dict(os.environ),
                                          output=directory / 'output')
            with self.assertRaises(ChildProcessError):
                os.waitpid(-1, os.WNOHANG)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
