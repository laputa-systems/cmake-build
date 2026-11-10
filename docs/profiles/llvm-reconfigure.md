# LLVM unchanged-reconfigure CPU sample

On 2026-11-10, the x86-64 release-profile CMake executable reconfigured the
pinned LLVM 23.1.5 and Clang workload in the same native Debian container and
with the same four-CPU affinity as the [paired study](../performance-rust-release.md).
The command succeeded. Its CMake executable SHA-256 was
`63f316b7e2a1371c918237ced5788dd4487823b71be98896d1b572a1fdac1887`;
the first clean build of release commit `91983ee` produced the same executable.
The host had eight logical CPUs, and the one-minute load was 2.54 at both
sample boundaries. The filesystem was warm.

The host did not have the `perf` command. A one-off sampler used Linux's
`perf_event_open` interface directly with the software CPU-clock event, a
1 ms sample period, and kernel and hypervisor samples excluded. It attached
after CMake started and recorded 8,386 samples from one process and one
thread, with no reported lost records. A separate CPU-bound Python probe
confirmed that the sampler recorded nonzero instruction pointers in the
expected interpreter mappings. The samples cover the CMake main thread's
user-space CPU only: they exclude kernel time, child processes, other threads,
waiting, and the beginning of startup. No call stacks were captured. They are
not a distribution of total elapsed time.

The executable was debug-stripped but retained symbols. LLVM symbolizer 23.1.4
resolved the PIE-relative instruction pointers without inline frames. The
largest individual symbol groups were:

| Symbol or symbol group | Samples | Share |
| --- | ---: | ---: |
| libc++ string hash-table insertion lambda | 832 | 9.92% |
| `memcmp` | 690 | 8.23% |
| `memcpy` | 617 | 7.36% |
| `__libc_malloc_impl` | 580 | 6.92% |
| `get_meta` | 390 | 4.65% |
| libc++ string hash function | 320 | 3.82% |
| `__libc_free` | 316 | 3.77% |
| `alloc_slot` | 191 | 2.28% |
| `cmList::Insert` | 131 | 1.56% |
| `cmDefinitions` hash-table lookup | 130 | 1.55% |

These samples show substantial string, hash-table and allocation activity in
the sampled task. Without call stacks they do not identify which CMake callers
caused the linked-library samples. The separate untimed `strace` process-tree
profile recorded 241,126 `stat`, 117,306 `lstat`, 150,759 `readlink`, 51
`execve`, and 62 `wait4` calls for each product. That trace includes child
processes and does not assign the calls or elapsed time to individual owners.
Compiler discovery and other external subprocesses are therefore observed but
not separately timed; build-executor overhead is not isolated. Kernel and
filesystem wait are outside the CPU sample. The official Kitware binary uses a
different runtime, and its timing difference cannot be assigned to CMake alone.
The available profile supports further investigation of string and allocation
work; it does not by itself justify changing compiler flags or claiming a
wall-time improvement.

The [PIE-relative instruction-pointer counts](llvm-reconfigure-relative-ips.tsv)
contain one hexadecimal address and its sample count per line. Their counts sum
to 8,386. They can be symbolized with the executable above and
`llvm-symbolizer --obj=<cmake> --no-inlines`. The sampler, container launcher,
and workload wrapper used for this run are in this directory.

To repeat the run, first prepare the exact archives and workspace described in
the [paired study](../performance-rust-release.md). Copy
`llvm-reconfigure.py` to `.work/tmp/perf-study/profile.py`, then start
`launch-llvm-reconfigure.py` from the repository root with `PYTHONPATH=$PWD`
and `TMPDIR=$PWD/.work/tmp`. Find the running
`/variants/product/bin/cmake` host PID, and run
`python3 docs/profiles/perf-sampler.py <pid> 30 .work/tmp/perf-study/cmake.tsv`
while it is active. Both processes must be owned by the same user and the host
must permit `perf_event_open`. The sampler fails if it sees no samples or lost
records. Its `.maps` output provides the address base needed to normalize PIE
instruction pointers.
