# Section garbage collection on x86-64

Linking the CMake executable with `--gc-sections` removed 2,825,392 bytes
from the stripped x86-64 executable, a 9.28% reduction. The five-run timing
ranges overlap in every operation, so the samples do not establish a runtime
change. The candidate passed the workload graph checks and the ELF audit.
Native qualification and clean-build reproduction remain necessary for a
release.

The candidate and baseline use the same source, toolchain, Rustls release
build, and link inputs. The experiment appended only `-Wl,--gc-sections` to
the baseline CMake link command and stripped both binaries with the pinned LLVM
tools. The baseline executable SHA-256 is
`63f316b7e2a1371c918237ced5788dd4487823b71be98896d1b572a1fdac1887`.
The candidate SHA-256 is
`f53bd11fb5beb68320766184ef5705986bd9ad89ee5f5177b5cfa6042160d7fa`.
Their sizes are 30,452,896 and 27,627,504 bytes. ELF `.text` decreased from
16,263,760 to 14,868,702 bytes, and `.eh_frame` decreased from 1,843,876 to
1,590,024 bytes. The linker discarded unreachable sections; no CPU-specific
flags or reduced security settings were used.

Five repetitions alternated variants on one native x86-64 host and in one
Debian container, with four CPUs assigned to each run. Workloads were fmt
12.2.1, zstd 1.5.7, libjpeg-turbo 3.2.1, and LLVM 23.1.5 with Clang.
The host's one-minute load at sample boundaries ranged from 1.84 to 3.56.
Filesystem caches were warm or uncontrolled. Cold-cache behavior was not
measured. Configure timings include tracing overhead used to measure RSS.
Startup timings use separate untraced invocations.

| Workload and operation | Baseline median seconds (range) | Candidate median seconds (range) | Baseline median RSS KiB | Candidate median RSS KiB |
| --- | ---: | ---: | ---: | ---: |
| fmt initial | 0.413 (0.392–0.469) | 0.418 (0.397–0.443) | 17,384 | 15,360 |
| zstd initial | 2.083 (1.996–2.291) | 2.082 (2.072–2.109) | 19,512 | 17,164 |
| libjpeg-turbo initial | 1.219 (1.136–1.252) | 1.253 (1.143–1.267) | 18,600 | 16,344 |
| LLVM initial | 29.808 (29.156–30.587) | 30.192 (29.340–30.430) | 491,136 | 489,412 |
| LLVM unchanged | 17.926 (17.861–18.269) | 17.936 (17.743–18.363) | 480,560 | 479,044 |

RSS is the CMake process image's high-water mark and excludes children. CPU
seconds include waited child processes. All 180 recorded operations completed.
The [raw results](results/cmake-gc-x86_64.json) include every operation,
iteration, CPU measurement, load observation, and untimed syscall profile.
The `musl` variant is the baseline; `product` is the candidate. The benchmark
runner came from commit `d258b25b56948dac35f7852b317a202372ba38f6`, restricted
to those two variants. Each generated Ninja graph passed a dry run.

A separate x86-64 link with `--icf=safe` produced a 29,869,408-byte stripped
executable and passed the ELF audit. It was not combined with section garbage
collection or subjected to workload qualification. The larger independent
section-garbage-collection reduction was selected for further qualification.
