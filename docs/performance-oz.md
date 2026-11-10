# Size-oriented optimization on x86-64

The `-Oz` candidate is not a worthwhile replacement for the released `-O3`
binary. It is 1.83% smaller, below the 3% size threshold, while LLVM unchanged
reconfiguration took 22.7% longer at the median. The two timing ranges did
not overlap. The candidate was not release-qualified and was not adopted.

The candidate changes `CMAKE_C_FLAGS_RELEASE` and `CMAKE_CXX_FLAGS_RELEASE`
to `-Oz -DNDEBUG`. Both binaries retain section garbage collection, the same
pinned toolchain, patches, Rustls release library, static PIE, and hardening
settings. The released executable SHA-256 is
`f53bd11fb5beb68320766184ef5705986bd9ad89ee5f5177b5cfa6042160d7fa`;
the candidate SHA-256 is
`574f6c2cb6abed78b9ec6dc52f3278888fe7d0c6333e201571c97dbe906e332b`.
Their stripped sizes are 27,627,504 and 27,123,088 bytes.

Five repetitions alternated variants on an eight-CPU AMD Ryzen 5 PRO 2400GE
host and in the same Debian container, with four CPUs assigned to each run.
The workloads were fmt 12.2.1, zstd 1.5.7, libjpeg-turbo 3.2.1, and LLVM
23.1.5 with Clang. The one-minute host load at sample boundaries ranged from
3.01 to 6.34. Filesystem caches were warm or uncontrolled, not cold. The
configure timings include tracing overhead used to measure RSS. CPU time
includes waited child processes.

| Workload and operation | Released median seconds (range) | `-Oz` median seconds (range) | Released median CPU seconds | `-Oz` median CPU seconds |
| --- | ---: | ---: | ---: | ---: |
| fmt initial | 0.486 (0.378–0.492) | 0.512 (0.406–0.570) | 0.489 | 0.518 |
| zstd initial | 2.153 (2.112–2.300) | 2.236 (1.990–2.586) | 2.201 | 2.283 |
| libjpeg-turbo initial | 1.374 (1.119–1.531) | 1.413 (1.303–1.500) | 1.401 | 1.447 |
| LLVM initial | 31.099 (29.950–32.482) | 34.821 (34.233–39.244) | 31.405 | 35.060 |
| LLVM unchanged | 17.916 (17.906–18.491) | 21.978 (21.672–22.466) | 17.920 | 21.898 |

The candidate lowered median CMake-image RSS in these samples: fmt initial
fell from 15,612 to 11,752 KiB, and LLVM unchanged fell from 478,540 to
475,680 KiB. This measurement excludes child processes. The LLVM timing
and CPU regressions outweigh those savings for the tested workflow. All 180
recorded operations succeeded, and each generated Ninja graph passed a dry
run. The [raw samples and syscall profiles](results/cmake-oz-x86_64.json)
include all four operations for every project, startup, CPU time, memory, and
host load. The `musl` variant is the released binary; `product` is `-Oz`.

An untimed `strace -f -c` of LLVM unchanged reconfiguration recorded the
same 614,737 process-tree syscalls for both binaries, including 241,126
`stat`, 117,306 `lstat`, 150,759 `readlink`, 51 `execve`, and 62 `wait4`
calls. This does not attribute the regression to a particular process.
Separate user-space CPU-clock samples of the CMake main thread captured 7,300
samples for the released executable and 5,151 for `-Oz`, with no reported
lost samples. The sample covered only part of each run and recorded no call
stacks. Both profiles spent substantial time in string hashing, hash-table
insertion, and `memcmp`; those samples do not identify the exact cause of the
regression or rule out child-process and kernel effects.

The [released relative instruction-pointer counts](profiles/oz-musl-relative-ips.tsv)
and [`-Oz` counts](profiles/oz-product-relative-ips.tsv) can be symbolized
with the corresponding executable and the existing
[`perf_event_open` sampler](profiles/perf-sampler.py). The official Kitware
binary is a different-runtime reference in the [native report](performance.md),
not a matched compiler-flag baseline.
