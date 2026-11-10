# Build system measurements

## Executor no-op comparison

On 2026-11-10, x86_64 Samurai 1.3 and Ninja 1.13.2 each ran five
interleaved no-op builds. Both executors used separate completed CMake 4.4.5
build trees configured by the same bootstrap CMake and P4 toolchain. Every
run reported no work and passed `perf-gate-ready` before and after the run.
The timed region starts immediately before the executor process and ends when
it exits. The host ran another workload during the comparison.

| Executor | Median | Range | Runs |
| --- | ---: | ---: | ---: |
| Samurai | 111.33 ms | 97.82–119.77 ms | 5 |
| Ninja | 71.61 ms | 64.69–73.28 ms | 5 |

The Ninja median was 35.7% lower. Treat this as provisional until the full
build comparison is complete and the no-op limiter is established. CMake
generates linker dependency files for Ninja but not for Samurai. In a separate
`strace -c` diagnostic, file status calls accounted for most measured syscall
time for both executors. That diagnostic does not establish the total runtime
limiter. Ninja rejects Samurai's build log, so the executors cannot share a
completed tree for this comparison.

The cold bootstrap and full-build comparisons remain unmeasured. The completed
Alpine CMake and executor builds overlapped load and failed their post-run
readiness checks; their timings were discarded.
