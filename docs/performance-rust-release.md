# Rustls release-profile study

The historical RSS values in this study are invalid: `wait4` can include the
benchmark launcher's earlier high-water mark. They are retained in the raw
data and table for transparency, but must not be used as memory budgets.
Timing samples are unaffected by that accounting error.

The x86-64 study compares the qualified prerelease at `58313ac` with the
release-profile experiment at `46103c8`. Both use the same pinned toolchain,
workloads, Debian container, CPU affinity `[0, 1, 2, 3]`, and the benchmark
runner. Five repetitions were interleaved; a warmup preceded them. Filesystem
caches were warm, and cold-cache behavior was not measured. Host load at
sample boundaries ranged from 1.87 to 3.15 on eight logical CPUs.

The original archive SHA-256 is
`b53ca751fd8c1f0c3b3918c7c9aed7f5a30a79b2bbf4f9289ec567ede5a0cc3e`;
the experiment archive is
`4ecd74ab145a36aa6348f1d7fb48fb006113a892106effe162c9360a01e6782a`.
The original CMake executable is 41,805,976 bytes; the experiment is
30,452,896 bytes, 27.2% smaller. The archive decreased from 10,171,144 to
8,724,488 bytes, 14.2% smaller. The paired timing ranges overlap in every
case, so these samples do not establish a runtime speedup or a clear
regression. The old RSS numbers are not reliable measurements of either
executable's memory.

The change uses Cargo's standard release profile for Rustls. That profile
also changes Rust's default debug-assertion and integer-overflow checks from
the development profile. The experimental archive passed the x86-64 project,
upstream, ELF, relocation and HTTPS qualification, including untrusted
certificates and hostname mismatches. ARM qualification is required for the
release candidate.

The table lists median and observed range in seconds, plus the invalid legacy
RSS figures in KiB. `product` is the release-profile experiment; `musl` is the previous
qualified product, not the separate unmodified musl reference used in the
[original x86-64 report](performance.md). The [raw measurements and syscall
profiles](performance-rust-release.json) contain all five samples and the
sample-boundary loads. The untimed LLVM traces recorded the same 614,737
file/process calls for each executable, including child processes; tracing
cannot attribute their wall time to CMake itself.

| Workload | Scenario | Variant | Median seconds | Minimum | Maximum | Invalid legacy RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | musl | 0.055226 | 0.053619 | 0.058742 | 23252 |
| fmt | cmakelists-edit | product | 0.057388 | 0.054022 | 0.065686 | 23252 |
| fmt | initial | musl | 0.387587 | 0.382769 | 0.415335 | 63760 |
| fmt | initial | product | 0.389681 | 0.377827 | 0.429956 | 63224 |
| fmt | option-change | musl | 0.058776 | 0.053899 | 0.065249 | 23252 |
| fmt | option-change | product | 0.059722 | 0.058006 | 0.067693 | 23252 |
| fmt | unchanged | musl | 0.057077 | 0.056632 | 0.058229 | 23252 |
| fmt | unchanged | product | 0.057095 | 0.055493 | 0.069706 | 23252 |
| libjpeg-turbo | cmakelists-edit | musl | 0.198151 | 0.173180 | 0.215220 | 62804 |
| libjpeg-turbo | cmakelists-edit | product | 0.180867 | 0.178758 | 0.188364 | 62796 |
| libjpeg-turbo | initial | musl | 1.228667 | 1.149007 | 1.271999 | 65808 |
| libjpeg-turbo | initial | product | 1.189090 | 1.133796 | 1.227703 | 65616 |
| libjpeg-turbo | option-change | musl | 0.200548 | 0.186151 | 0.223733 | 61832 |
| libjpeg-turbo | option-change | product | 0.202078 | 0.187986 | 0.216968 | 62664 |
| libjpeg-turbo | unchanged | musl | 0.177929 | 0.174620 | 0.192280 | 62660 |
| libjpeg-turbo | unchanged | product | 0.182061 | 0.177236 | 0.198833 | 62644 |
| llvm-clang | cmakelists-edit | musl | 17.942016 | 17.607399 | 18.387951 | 483060 |
| llvm-clang | cmakelists-edit | product | 18.061048 | 17.773505 | 18.108505 | 479828 |
| llvm-clang | initial | musl | 30.159234 | 29.472946 | 30.999823 | 493564 |
| llvm-clang | initial | product | 30.256089 | 29.732120 | 36.526812 | 490336 |
| llvm-clang | option-change | musl | 17.763966 | 17.553374 | 18.331964 | 483040 |
| llvm-clang | option-change | product | 18.126041 | 17.818373 | 18.489815 | 479916 |
| llvm-clang | unchanged | musl | 17.850538 | 17.630463 | 18.019630 | 482972 |
| llvm-clang | unchanged | product | 18.042979 | 17.771982 | 18.265446 | 479912 |
| process | script | musl | 0.007123 | 0.004558 | 0.007766 | 23252 |
| process | script | product | 0.006131 | 0.005060 | 0.006515 | 23252 |
| process | version | musl | 0.006634 | 0.004286 | 0.046410 | 23252 |
| process | version | product | 0.005853 | 0.005661 | 0.006804 | 23252 |
| zstd | cmakelists-edit | musl | 0.081752 | 0.073499 | 0.088094 | 23252 |
| zstd | cmakelists-edit | product | 0.074126 | 0.073300 | 0.083598 | 23252 |
| zstd | initial | musl | 2.033422 | 1.924104 | 2.048185 | 68576 |
| zstd | initial | product | 2.052362 | 1.883722 | 2.146247 | 68140 |
| zstd | option-change | musl | 0.084752 | 0.081607 | 0.086517 | 23252 |
| zstd | option-change | product | 0.078565 | 0.076650 | 0.089615 | 23252 |
| zstd | unchanged | musl | 0.079936 | 0.073579 | 0.086334 | 23252 |
| zstd | unchanged | product | 0.075940 | 0.074678 | 0.087453 | 23252 |

## Reproduce the study

Use a native x86-64 host with the locked sources, the CMake reference runtime,
`strace`, and the completed project-source, prepare and bootstrap phases.
Build and qualify commit `46103c8` in `.work/wt/rust-release`, extract its
archive to `.work/tmp/rust-release-candidate`, and activate the original
`58313ac` qualified generation. Verify both archive SHA-256 values above and
verify the executable hashes: the experiment is
`63f316b7e2a1371c918237ced5788dd4487823b71be98896d1b572a1fdac1887`
and the original is
`e53436f3696c32eb40a3389ce15937d24dfb8cfef63e5afbb8b53f9e2b895121`.
The study script expects these paths and creates a fresh
`.work/tmp/rust-release-comparison` directory. With `TMPDIR` set to
`.work/tmp`, run `PYTHONPATH=$PWD python3 docs/rust-release-study.py` from the
repository root. The script is the one used for this run, with SHA-256
`3d63da339b7b736b16b44a816f671601658adc7220b730ecb47f0ccbf78baa5a`.
Its runner is `tests/benchmark/run.py` with the variant list narrowed to the
two product executables; the measured runner SHA-256 is
`e3547ac9951e3fc339b03a3f1c7533ad502618cd10d427e3f8f6ce2afdcffb85`.
