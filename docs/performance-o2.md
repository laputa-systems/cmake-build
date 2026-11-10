# CMake optimization level on x86-64

The `-O2` experiment did not demonstrate a runtime improvement over the shipped
`-O3` settings. The observed ranges overlap for every measured operation. The
`-O2` executable is 1.81% smaller, but the gain does not justify adding a
separate optimization setting without a demonstrated consumer benefit. The
candidate did not undergo full release qualification.

Both executables use the pinned static-musl toolchain, the Rustls release build,
and the same CMake source and patches. The candidate changes only
`CMAKE_C_FLAGS_RELEASE` and `CMAKE_CXX_FLAGS_RELEASE` to `-O2 -DNDEBUG`.
The `-O3` executable SHA-256 is
`63f316b7e2a1371c918237ced5788dd4487823b71be98896d1b572a1fdac1887`.
The `-O2` executable SHA-256 is
`29cc7e531ac8da11f623c36d8de8f53c669ccefbaf31531cf8ec165e0895c470`.
Their stripped sizes are 30,452,896 and 29,901,376 bytes, respectively.
The corresponding archives are 8,724,488 and 8,564,176 bytes.

Five repetitions alternated variants on the same native x86-64 host and in the
same Debian container, with four CPUs assigned to each run. The workloads were
fmt 12.2.1, zstd 1.5.7, libjpeg-turbo 3.2.1, and LLVM 23.1.5 with Clang.
The one-minute host load across recorded operations ranged from 1.98 to 3.37.
Filesystem caches were warm or uncontrolled. These are not cold-cache results.

| Workload and operation | `-O3` median seconds (range) | `-O2` median seconds (range) |
| --- | ---: | ---: |
| fmt initial | 0.410 (0.379–0.453) | 0.391 (0.369–0.408) |
| zstd initial | 2.061 (1.982–2.152) | 1.992 (1.923–2.061) |
| libjpeg-turbo initial | 1.213 (1.155–1.235) | 1.160 (1.120–1.226) |
| LLVM initial | 29.396 (29.114–29.686) | 29.526 (29.083–29.608) |
| LLVM unchanged | 17.922 (17.734–18.052) | 17.809 (17.707–17.986) |

The [raw results](results/cmake-o2-x86_64.json) include all operations, CPU
measurements, load observations, and syscall profiles. The `musl` variant is
`-O3`; `product` is `-O2`. The RSS fields are invalid: the runner used
`wait4`, which can inherit the Python launcher's high-water mark. The elapsed
and CPU measurements do not use that RSS value.

The experiment used the benchmark runner from commit `9be9124cf6baa927d6ca3d2654f760f08393185c`,
restricted to the two candidate variants. Configure and graph checks passed for
each workload. The host tracer profiles include child processes and do not
represent untraced time shares.
