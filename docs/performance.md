# CMake executable performance

The historical RSS values in this report are invalid: `wait4` can include the
benchmark launcher's earlier high-water mark. They are retained only as raw
historical data and must not be used as memory budgets. Timing samples are
unaffected by that accounting error.

Target: `x86_64-unknown-linux-musl`. Runs per variant: 10.

All three binaries ran in the same native Debian container with the pinned musl toolchain.
Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource
differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with
OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those
product differences and does not isolate an individual compiler flag.
A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not
measured. Timings are not release gates.

Host: `Linux-7.3.1-0-stable-x86_64-with-musl1`. CPU: `AMD Ryzen 5 PRO 2400GE w/ Radeon Vega Graphics`. Container: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
CPU affinity: `[0, 1, 2, 3]`. Product archive SHA-256: `b53ca751fd8c1f0c3b3918c7c9aed7f5a30a79b2bbf4f9289ec567ede5a0cc3e`.
Official archive SHA-256: `ed85135c5a5135b45e50423cb406dea04ca3338da0b8ef3c9ede963559680be0`. Baseline output digest: `178c0d07ed7fdc6ed8252d4216f62dfb651d65295b2836731663eb89e8f9a8a9`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `c43f18f143cc17f49814b6c5dda8a1122d17b6bcdff9848b6f77e97b33026dfe`.
Benchmark implementation SHA-256: `de493a27e8d834239cb8f1b8626c50dd06c0328c11a457409584d2c3a0f907f3` (commit `d7225b8`).
Tracer: `strace -- version 7.2`. Runner SHA-256: `4b853657f2beb3946e1140efab93943c0c8c6f7e8a23ee9150306d4326ff33ef`.

| Project | Version | Source SHA-256 |
| --- | --- | --- |
| fmt-source | 12.2.1 | `449374d74f31b67796dece454d59b93e6f1538efcce0e9ac78000c98142c139e` |
| zstd-source | 1.5.7 | `eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3` |
| libjpeg-turbo-source | 3.2.1 | `c27ad72a68da151177929aa969ae773a2da5ac2af9ce946079314fdac8cece7f` |
| llvm-project-source | 23.1.5 | `fb50b1eac93ddeb3aa8dab4cfe324dff74f4a9c2bdee6160c9e36188f8d06a6e` |

See the [baseline analysis](performance-analysis.md) for the interpretation and limits of this run.

## Size

The official archive includes additional tools and resources, so total package sizes are not like-for-like.

| Variant | CMake executable bytes | Regular-file bytes | Archive bytes |
| --- | ---: | ---: | ---: |
| product | 41805976 | 54476668 | 10171144 |
| musl | 24404144 | 36026480 | not packaged |
| kitware | 21469504 | 190375166 | 64865573 |

## Measurements

The legacy RSS column is invalid for comparing executable memory, as noted above.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Invalid RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.037395 | 0.031258–0.050411 | 0.036302 | 22584 |
| fmt | cmakelists-edit | musl | 0.058848 | 0.053267–0.068288 | 0.058810 | 22584 |
| fmt | cmakelists-edit | product | 0.061117 | 0.053971–0.085860 | 0.061047 | 22584 |
| fmt | initial | kitware | 0.432855 | 0.388802–0.460832 | 0.446658 | 60664 |
| fmt | initial | musl | 0.440700 | 0.396795–0.491039 | 0.447509 | 60824 |
| fmt | initial | product | 0.441896 | 0.413430–0.498453 | 0.458445 | 60760 |
| fmt | option-change | kitware | 0.036669 | 0.034987–0.046237 | 0.035992 | 22584 |
| fmt | option-change | musl | 0.064872 | 0.056293–0.079649 | 0.061524 | 22584 |
| fmt | option-change | product | 0.062031 | 0.055101–0.072512 | 0.059196 | 22584 |
| fmt | unchanged | kitware | 0.045208 | 0.034957–0.061746 | 0.040013 | 22584 |
| fmt | unchanged | musl | 0.061831 | 0.056558–0.078301 | 0.059385 | 22584 |
| fmt | unchanged | product | 0.064722 | 0.055742–0.078400 | 0.061174 | 22584 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.174621 | 0.153073–0.198080 | 0.172452 | 62868 |
| libjpeg-turbo | cmakelists-edit | musl | 0.197177 | 0.176385–0.214338 | 0.200784 | 63160 |
| libjpeg-turbo | cmakelists-edit | product | 0.193854 | 0.187323–0.460024 | 0.196233 | 63180 |
| libjpeg-turbo | initial | kitware | 1.237966 | 1.099465–1.397811 | 1.291636 | 65684 |
| libjpeg-turbo | initial | musl | 1.297181 | 1.156363–1.485329 | 1.345555 | 65672 |
| libjpeg-turbo | initial | product | 1.255567 | 1.186360–1.408121 | 1.306429 | 65576 |
| libjpeg-turbo | option-change | kitware | 0.179958 | 0.168989–0.209731 | 0.182561 | 63120 |
| libjpeg-turbo | option-change | musl | 0.199708 | 0.191104–0.247853 | 0.201944 | 63176 |
| libjpeg-turbo | option-change | product | 0.208729 | 0.196609–0.471587 | 0.208846 | 62788 |
| libjpeg-turbo | unchanged | kitware | 0.168554 | 0.155069–0.186919 | 0.170413 | 63156 |
| libjpeg-turbo | unchanged | musl | 0.187525 | 0.181449–0.217233 | 0.189593 | 62696 |
| libjpeg-turbo | unchanged | product | 0.200562 | 0.181481–0.250706 | 0.201778 | 62884 |
| llvm-clang | cmakelists-edit | kitware | 15.928072 | 15.740472–16.190621 | 15.934528 | 380800 |
| llvm-clang | cmakelists-edit | musl | 17.919478 | 17.650914–18.334108 | 17.920741 | 478840 |
| llvm-clang | cmakelists-edit | product | 17.966774 | 17.755589–18.534702 | 17.905056 | 484728 |
| llvm-clang | initial | kitware | 27.625721 | 26.661417–28.693714 | 27.844304 | 389996 |
| llvm-clang | initial | musl | 29.914382 | 28.931404–31.848954 | 30.110988 | 488716 |
| llvm-clang | initial | product | 30.102251 | 29.279966–31.463758 | 30.476787 | 495152 |
| llvm-clang | option-change | kitware | 15.963636 | 15.583828–16.694227 | 15.966883 | 380924 |
| llvm-clang | option-change | musl | 17.752222 | 17.500086–18.336598 | 17.760531 | 478172 |
| llvm-clang | option-change | product | 17.836821 | 17.607971–18.712407 | 17.890237 | 484024 |
| llvm-clang | unchanged | kitware | 15.904475 | 15.538711–16.143381 | 15.912392 | 381764 |
| llvm-clang | unchanged | musl | 18.004730 | 17.651288–18.295352 | 18.032766 | 478944 |
| llvm-clang | unchanged | product | 18.127244 | 17.793317–18.251697 | 18.137042 | 484152 |
| process | script | kitware | 0.006218 | 0.003662–0.007893 | 0.005956 | 22584 |
| process | script | musl | 0.004974 | 0.002725–0.007344 | 0.004691 | 22584 |
| process | script | product | 0.006584 | 0.004037–0.008344 | 0.006354 | 22584 |
| process | version | kitware | 0.004824 | 0.003053–0.007183 | 0.004623 | 22584 |
| process | version | musl | 0.004478 | 0.002869–0.006924 | 0.004212 | 22584 |
| process | version | product | 0.004560 | 0.003332–0.007578 | 0.004294 | 22584 |
| zstd | cmakelists-edit | kitware | 0.055637 | 0.051189–0.061410 | 0.055526 | 22584 |
| zstd | cmakelists-edit | musl | 0.080822 | 0.074594–0.095479 | 0.080802 | 22584 |
| zstd | cmakelists-edit | product | 0.080655 | 0.074181–0.094892 | 0.080562 | 22584 |
| zstd | initial | kitware | 2.258751 | 2.108319–3.523206 | 2.325522 | 68168 |
| zstd | initial | musl | 2.315754 | 2.194218–2.608440 | 2.355226 | 68624 |
| zstd | initial | product | 2.322858 | 2.210565–2.801789 | 2.462626 | 68632 |
| zstd | option-change | kitware | 0.057090 | 0.054228–0.077988 | 0.056178 | 22584 |
| zstd | option-change | musl | 0.089651 | 0.078654–0.102871 | 0.085152 | 22584 |
| zstd | option-change | product | 0.089353 | 0.080423–0.101577 | 0.089243 | 22584 |
| zstd | unchanged | kitware | 0.060961 | 0.051103–0.072972 | 0.059200 | 22584 |
| zstd | unchanged | musl | 0.089583 | 0.075203–0.130978 | 0.087271 | 22584 |
| zstd | unchanged | product | 0.092675 | 0.079766–0.212507 | 0.090297 | 22584 |

## Raw samples

Seconds, invalid legacy RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Invalid RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.007304 | 0.007128 | 22584 | 4.17 | 4.17 |
| process | script | product | 1 | 0.004037 | 0.003840 | 22584 | 4.17 | 4.17 |
| process | version | musl | 1 | 0.002869 | 0.002667 | 22584 | 4.17 | 4.17 |
| process | script | musl | 1 | 0.004241 | 0.004019 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 1 | 0.004245 | 0.004036 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 1 | 0.004876 | 0.004595 | 22584 | 4.17 | 4.17 |
| process | version | musl | 2 | 0.003908 | 0.003622 | 22584 | 4.17 | 4.17 |
| process | script | musl | 2 | 0.004385 | 0.004068 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 2 | 0.004253 | 0.003961 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 2 | 0.004599 | 0.004324 | 22584 | 4.17 | 4.17 |
| process | version | product | 2 | 0.004906 | 0.004583 | 22584 | 4.17 | 4.17 |
| process | script | product | 2 | 0.008308 | 0.008032 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 3 | 0.007183 | 0.006941 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 3 | 0.007893 | 0.007663 | 22584 | 4.17 | 4.17 |
| process | version | product | 3 | 0.003709 | 0.003474 | 22584 | 4.17 | 4.17 |
| process | script | product | 3 | 0.006569 | 0.006297 | 22584 | 4.17 | 4.17 |
| process | version | musl | 3 | 0.005112 | 0.004867 | 22584 | 4.17 | 4.17 |
| process | script | musl | 3 | 0.002725 | 0.002479 | 22584 | 4.17 | 4.17 |
| process | version | product | 4 | 0.003332 | 0.003090 | 22584 | 4.17 | 4.17 |
| process | script | product | 4 | 0.006276 | 0.005997 | 22584 | 4.17 | 4.17 |
| process | version | musl | 4 | 0.005049 | 0.004802 | 22584 | 4.17 | 4.17 |
| process | script | musl | 4 | 0.005871 | 0.005583 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 4 | 0.005647 | 0.005308 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 4 | 0.003662 | 0.003415 | 22584 | 4.17 | 4.17 |
| process | version | musl | 5 | 0.005092 | 0.004807 | 22584 | 4.17 | 4.17 |
| process | script | musl | 5 | 0.005563 | 0.005313 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 5 | 0.005455 | 0.005243 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 5 | 0.006059 | 0.005818 | 22584 | 4.17 | 4.17 |
| process | version | product | 5 | 0.005839 | 0.005641 | 22584 | 4.17 | 4.17 |
| process | script | product | 5 | 0.006298 | 0.006094 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 6 | 0.005395 | 0.005210 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 6 | 0.007381 | 0.007068 | 22584 | 4.17 | 4.17 |
| process | version | product | 6 | 0.003628 | 0.003387 | 22584 | 4.17 | 4.17 |
| process | script | product | 6 | 0.008344 | 0.008044 | 22584 | 4.17 | 4.17 |
| process | version | musl | 6 | 0.003063 | 0.002832 | 22584 | 4.17 | 4.17 |
| process | script | musl | 6 | 0.007344 | 0.007089 | 22584 | 4.17 | 4.17 |
| process | version | product | 7 | 0.007539 | 0.007242 | 22584 | 4.17 | 4.17 |
| process | script | product | 7 | 0.005330 | 0.005073 | 22584 | 4.17 | 4.17 |
| process | version | musl | 7 | 0.003164 | 0.002940 | 22584 | 4.17 | 4.17 |
| process | script | musl | 7 | 0.003188 | 0.003016 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 7 | 0.003053 | 0.002887 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 7 | 0.006019 | 0.005814 | 22584 | 4.17 | 4.17 |
| process | version | musl | 8 | 0.006119 | 0.005923 | 22584 | 4.17 | 4.17 |
| process | script | musl | 8 | 0.005755 | 0.005554 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 8 | 0.003553 | 0.003386 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 8 | 0.006736 | 0.006522 | 22584 | 4.17 | 4.17 |
| process | version | product | 8 | 0.004214 | 0.004006 | 22584 | 4.17 | 4.17 |
| process | script | product | 8 | 0.007068 | 0.006758 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 9 | 0.005993 | 0.005732 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 9 | 0.006377 | 0.006094 | 22584 | 4.17 | 4.17 |
| process | version | product | 9 | 0.003831 | 0.003560 | 22584 | 4.17 | 4.17 |
| process | script | product | 9 | 0.006600 | 0.006412 | 22584 | 4.17 | 4.17 |
| process | version | musl | 9 | 0.003119 | 0.002949 | 22584 | 4.17 | 4.17 |
| process | script | musl | 9 | 0.007157 | 0.006973 | 22584 | 4.17 | 4.17 |
| process | version | product | 10 | 0.007578 | 0.007310 | 22584 | 4.17 | 4.17 |
| process | script | product | 10 | 0.008293 | 0.007993 | 22584 | 4.17 | 4.17 |
| process | version | musl | 10 | 0.006924 | 0.006655 | 22584 | 4.17 | 4.17 |
| process | script | musl | 10 | 0.003787 | 0.003546 | 22584 | 4.17 | 4.17 |
| process | version | kitware | 10 | 0.003209 | 0.003010 | 22584 | 4.17 | 4.17 |
| process | script | kitware | 10 | 0.006757 | 0.006578 | 22584 | 4.17 | 4.17 |
| fmt | initial | product | 1 | 0.466495 | 0.482087 | 54932 | 4.17 | 4.16 |
| fmt | unchanged | product | 1 | 0.059879 | 0.059823 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | product | 1 | 0.061560 | 0.061482 | 22584 | 4.16 | 4.16 |
| fmt | option-change | product | 1 | 0.058584 | 0.058522 | 22584 | 4.16 | 4.16 |
| fmt | initial | musl | 1 | 0.463133 | 0.479924 | 59236 | 4.16 | 4.16 |
| fmt | unchanged | musl | 1 | 0.057236 | 0.057144 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | musl | 1 | 0.055693 | 0.055587 | 22584 | 4.16 | 4.16 |
| fmt | option-change | musl | 1 | 0.065208 | 0.063510 | 22584 | 4.16 | 4.16 |
| fmt | initial | kitware | 1 | 0.445411 | 0.463747 | 59136 | 4.16 | 4.16 |
| fmt | unchanged | kitware | 1 | 0.044247 | 0.044189 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | kitware | 1 | 0.044403 | 0.043544 | 22584 | 4.16 | 4.16 |
| fmt | option-change | kitware | 1 | 0.044147 | 0.044066 | 22584 | 4.16 | 4.16 |
| fmt | initial | musl | 2 | 0.396795 | 0.406299 | 60560 | 4.16 | 4.16 |
| fmt | unchanged | musl | 2 | 0.078301 | 0.056571 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | musl | 2 | 0.061326 | 0.061220 | 22584 | 4.16 | 4.16 |
| fmt | option-change | musl | 2 | 0.064559 | 0.064333 | 22584 | 4.16 | 4.16 |
| fmt | initial | kitware | 2 | 0.432448 | 0.446967 | 59500 | 4.16 | 4.16 |
| fmt | unchanged | kitware | 2 | 0.042639 | 0.034846 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | kitware | 2 | 0.037543 | 0.037451 | 22584 | 4.16 | 4.16 |
| fmt | option-change | kitware | 2 | 0.046237 | 0.034813 | 22584 | 4.16 | 4.16 |
| fmt | initial | product | 2 | 0.421856 | 0.467997 | 58452 | 4.16 | 4.16 |
| fmt | unchanged | product | 2 | 0.062582 | 0.062526 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | product | 2 | 0.060519 | 0.060413 | 22584 | 4.16 | 4.16 |
| fmt | option-change | product | 2 | 0.058661 | 0.058649 | 22584 | 4.16 | 4.16 |
| fmt | initial | kitware | 3 | 0.460087 | 0.480377 | 57500 | 4.16 | 4.16 |
| fmt | unchanged | kitware | 3 | 0.046170 | 0.046290 | 22584 | 4.16 | 4.16 |
| fmt | cmakelists-edit | kitware | 3 | 0.050411 | 0.034741 | 22584 | 4.16 | 4.16 |
| fmt | option-change | kitware | 3 | 0.036834 | 0.036815 | 22584 | 4.16 | 4.16 |
| fmt | initial | product | 3 | 0.429992 | 0.438709 | 60760 | 4.16 | 4.14 |
| fmt | unchanged | product | 3 | 0.066863 | 0.066487 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | product | 3 | 0.085860 | 0.067853 | 22584 | 4.14 | 4.14 |
| fmt | option-change | product | 3 | 0.055101 | 0.054323 | 22584 | 4.14 | 4.14 |
| fmt | initial | musl | 3 | 0.418113 | 0.432849 | 60676 | 4.14 | 4.14 |
| fmt | unchanged | musl | 3 | 0.056558 | 0.056533 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | musl | 3 | 0.053267 | 0.053113 | 22584 | 4.14 | 4.14 |
| fmt | option-change | musl | 3 | 0.056293 | 0.056263 | 22584 | 4.14 | 4.14 |
| fmt | initial | product | 4 | 0.480034 | 0.498482 | 59500 | 4.14 | 4.14 |
| fmt | unchanged | product | 4 | 0.074019 | 0.055123 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | product | 4 | 0.053971 | 0.053896 | 22584 | 4.14 | 4.14 |
| fmt | option-change | product | 4 | 0.071654 | 0.055395 | 22584 | 4.14 | 4.14 |
| fmt | initial | musl | 4 | 0.463632 | 0.479759 | 57236 | 4.14 | 4.14 |
| fmt | unchanged | musl | 4 | 0.064091 | 0.064017 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | musl | 4 | 0.068288 | 0.068296 | 22584 | 4.14 | 4.14 |
| fmt | option-change | musl | 4 | 0.071838 | 0.071885 | 22584 | 4.14 | 4.14 |
| fmt | initial | kitware | 4 | 0.433262 | 0.446350 | 54788 | 4.14 | 4.14 |
| fmt | unchanged | kitware | 4 | 0.051261 | 0.034414 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | kitware | 4 | 0.034080 | 0.034046 | 22584 | 4.14 | 4.14 |
| fmt | option-change | kitware | 4 | 0.035734 | 0.035568 | 22584 | 4.14 | 4.14 |
| fmt | initial | musl | 5 | 0.491039 | 0.507247 | 54256 | 4.14 | 4.14 |
| fmt | unchanged | musl | 5 | 0.057773 | 0.057522 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | musl | 5 | 0.060992 | 0.060882 | 22584 | 4.14 | 4.14 |
| fmt | option-change | musl | 5 | 0.061122 | 0.058479 | 22584 | 4.14 | 4.14 |
| fmt | initial | kitware | 5 | 0.389869 | 0.396466 | 57484 | 4.14 | 4.14 |
| fmt | unchanged | kitware | 5 | 0.034957 | 0.034972 | 22584 | 4.14 | 4.14 |
| fmt | cmakelists-edit | kitware | 5 | 0.036055 | 0.034156 | 22584 | 4.14 | 4.14 |
| fmt | option-change | kitware | 5 | 0.035465 | 0.035397 | 22584 | 4.14 | 4.14 |
| fmt | initial | product | 5 | 0.445257 | 0.454456 | 58632 | 4.14 | 4.21 |
| fmt | unchanged | product | 5 | 0.058830 | 0.058743 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | product | 5 | 0.060674 | 0.060613 | 22584 | 4.21 | 4.21 |
| fmt | option-change | product | 5 | 0.057620 | 0.057452 | 22584 | 4.21 | 4.21 |
| fmt | initial | kitware | 6 | 0.460832 | 0.471599 | 55880 | 4.21 | 4.21 |
| fmt | unchanged | kitware | 6 | 0.055208 | 0.035113 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | kitware | 6 | 0.037247 | 0.037338 | 22584 | 4.21 | 4.21 |
| fmt | option-change | kitware | 6 | 0.036504 | 0.036415 | 22584 | 4.21 | 4.21 |
| fmt | initial | product | 6 | 0.428397 | 0.453705 | 58552 | 4.21 | 4.21 |
| fmt | unchanged | product | 6 | 0.055742 | 0.055494 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | product | 6 | 0.060367 | 0.060252 | 22584 | 4.21 | 4.21 |
| fmt | option-change | product | 6 | 0.064265 | 0.064197 | 22584 | 4.21 | 4.21 |
| fmt | initial | musl | 6 | 0.427037 | 0.446440 | 60824 | 4.21 | 4.21 |
| fmt | unchanged | musl | 6 | 0.061455 | 0.061249 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | musl | 6 | 0.056119 | 0.053972 | 22584 | 4.21 | 4.21 |
| fmt | option-change | musl | 6 | 0.065186 | 0.065180 | 22584 | 4.21 | 4.21 |
| fmt | initial | product | 7 | 0.498453 | 0.515381 | 57360 | 4.21 | 4.21 |
| fmt | unchanged | product | 7 | 0.059334 | 0.059247 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | product | 7 | 0.082713 | 0.064357 | 22584 | 4.21 | 4.21 |
| fmt | option-change | product | 7 | 0.059798 | 0.059743 | 22584 | 4.21 | 4.21 |
| fmt | initial | musl | 7 | 0.448185 | 0.448578 | 57072 | 4.21 | 4.21 |
| fmt | unchanged | musl | 7 | 0.056879 | 0.056607 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | musl | 7 | 0.055160 | 0.055158 | 22584 | 4.21 | 4.21 |
| fmt | option-change | musl | 7 | 0.063984 | 0.053855 | 22584 | 4.21 | 4.21 |
| fmt | initial | kitware | 7 | 0.388802 | 0.396359 | 58548 | 4.21 | 4.21 |
| fmt | unchanged | kitware | 7 | 0.043276 | 0.043250 | 22584 | 4.21 | 4.21 |
| fmt | cmakelists-edit | kitware | 7 | 0.050282 | 0.050383 | 22584 | 4.21 | 4.21 |
| fmt | option-change | kitware | 7 | 0.037928 | 0.037695 | 22584 | 4.21 | 4.21 |
| fmt | initial | musl | 8 | 0.433214 | 0.430305 | 57608 | 4.21 | 4.12 |
| fmt | unchanged | musl | 8 | 0.063365 | 0.063303 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | musl | 8 | 0.060476 | 0.060383 | 22584 | 4.12 | 4.12 |
| fmt | option-change | musl | 8 | 0.057241 | 0.057077 | 22584 | 4.12 | 4.12 |
| fmt | initial | kitware | 8 | 0.389896 | 0.418800 | 59344 | 4.12 | 4.12 |
| fmt | unchanged | kitware | 8 | 0.039945 | 0.039801 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | kitware | 8 | 0.031258 | 0.031240 | 22584 | 4.12 | 4.12 |
| fmt | option-change | kitware | 8 | 0.043682 | 0.043493 | 22584 | 4.12 | 4.12 |
| fmt | initial | product | 8 | 0.438535 | 0.445767 | 58628 | 4.12 | 4.12 |
| fmt | unchanged | product | 8 | 0.074123 | 0.074075 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | product | 8 | 0.060507 | 0.059298 | 22584 | 4.12 | 4.12 |
| fmt | option-change | product | 8 | 0.072512 | 0.059749 | 22584 | 4.12 | 4.12 |
| fmt | initial | kitware | 9 | 0.457720 | 0.466128 | 58636 | 4.12 | 4.12 |
| fmt | unchanged | kitware | 9 | 0.047291 | 0.047356 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | kitware | 9 | 0.035288 | 0.035265 | 22584 | 4.12 | 4.12 |
| fmt | option-change | kitware | 9 | 0.035313 | 0.033324 | 22584 | 4.12 | 4.12 |
| fmt | initial | product | 9 | 0.413430 | 0.441857 | 58628 | 4.12 | 4.12 |
| fmt | unchanged | product | 9 | 0.078400 | 0.067179 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | product | 9 | 0.074181 | 0.074070 | 22584 | 4.12 | 4.12 |
| fmt | option-change | product | 9 | 0.070865 | 0.070842 | 22584 | 4.12 | 4.12 |
| fmt | initial | musl | 9 | 0.409972 | 0.419734 | 60228 | 4.12 | 4.12 |
| fmt | unchanged | musl | 9 | 0.066149 | 0.065876 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | musl | 9 | 0.057219 | 0.057238 | 22584 | 4.12 | 4.12 |
| fmt | option-change | musl | 9 | 0.071449 | 0.071329 | 22584 | 4.12 | 4.12 |
| fmt | initial | product | 10 | 0.447946 | 0.462435 | 58804 | 4.12 | 4.12 |
| fmt | unchanged | product | 10 | 0.072376 | 0.072149 | 22584 | 4.12 | 4.12 |
| fmt | cmakelists-edit | product | 10 | 0.065263 | 0.065114 | 22584 | 4.12 | 4.12 |
| fmt | option-change | product | 10 | 0.067681 | 0.067550 | 22584 | 4.12 | 4.12 |
| fmt | initial | musl | 10 | 0.472612 | 0.482645 | 59332 | 4.12 | 4.11 |
| fmt | unchanged | musl | 10 | 0.062207 | 0.062020 | 22584 | 4.11 | 4.11 |
| fmt | cmakelists-edit | musl | 10 | 0.063022 | 0.062822 | 22584 | 4.11 | 4.11 |
| fmt | option-change | musl | 10 | 0.079649 | 0.059539 | 22584 | 4.11 | 4.11 |
| fmt | initial | kitware | 10 | 0.425211 | 0.435384 | 60664 | 4.11 | 4.11 |
| fmt | unchanged | kitware | 10 | 0.061746 | 0.040225 | 22584 | 4.11 | 4.11 |
| fmt | cmakelists-edit | kitware | 10 | 0.040697 | 0.040616 | 22584 | 4.11 | 4.11 |
| fmt | option-change | kitware | 10 | 0.034987 | 0.034963 | 22584 | 4.11 | 4.11 |
| zstd | initial | product | 1 | 2.801789 | 2.566460 | 66940 | 4.07 | 3.98 |
| zstd | unchanged | product | 1 | 0.089605 | 0.088502 | 22584 | 3.98 | 3.98 |
| zstd | cmakelists-edit | product | 1 | 0.076532 | 0.076453 | 22584 | 3.98 | 3.98 |
| zstd | option-change | product | 1 | 0.080423 | 0.080330 | 22584 | 3.98 | 3.98 |
| zstd | initial | musl | 1 | 2.485426 | 2.442148 | 67600 | 3.98 | 3.98 |
| zstd | unchanged | musl | 1 | 0.079958 | 0.072684 | 22584 | 3.98 | 3.98 |
| zstd | cmakelists-edit | musl | 1 | 0.088758 | 0.088647 | 22584 | 3.98 | 3.98 |
| zstd | option-change | musl | 1 | 0.084934 | 0.077146 | 22584 | 3.98 | 3.98 |
| zstd | initial | kitware | 1 | 3.523206 | 2.536746 | 67052 | 3.98 | 3.99 |
| zstd | unchanged | kitware | 1 | 0.060950 | 0.060602 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | kitware | 1 | 0.053382 | 0.052049 | 22584 | 3.99 | 3.99 |
| zstd | option-change | kitware | 1 | 0.077988 | 0.077925 | 22584 | 3.99 | 3.99 |
| zstd | initial | musl | 2 | 2.252174 | 2.309913 | 68164 | 3.99 | 3.99 |
| zstd | unchanged | musl | 2 | 0.130978 | 0.086293 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | musl | 2 | 0.074594 | 0.074386 | 22584 | 3.99 | 3.99 |
| zstd | option-change | musl | 2 | 0.078654 | 0.078609 | 22584 | 3.99 | 3.99 |
| zstd | initial | kitware | 2 | 2.224365 | 2.199300 | 67392 | 3.99 | 3.99 |
| zstd | unchanged | kitware | 2 | 0.072044 | 0.064059 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | kitware | 2 | 0.058378 | 0.058297 | 22584 | 3.99 | 3.99 |
| zstd | option-change | kitware | 2 | 0.059686 | 0.054263 | 22584 | 3.99 | 3.99 |
| zstd | initial | product | 2 | 2.243185 | 2.252077 | 66888 | 3.99 | 3.99 |
| zstd | unchanged | product | 2 | 0.212507 | 0.090801 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | product | 2 | 0.085100 | 0.085006 | 22584 | 3.99 | 3.99 |
| zstd | option-change | product | 2 | 0.089230 | 0.089156 | 22584 | 3.99 | 3.99 |
| zstd | initial | kitware | 3 | 2.435551 | 2.240338 | 68168 | 3.99 | 3.99 |
| zstd | unchanged | kitware | 3 | 0.060972 | 0.055275 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | kitware | 3 | 0.053000 | 0.052843 | 22584 | 3.99 | 3.99 |
| zstd | option-change | kitware | 3 | 0.070255 | 0.054886 | 22584 | 3.99 | 3.99 |
| zstd | initial | product | 3 | 2.635715 | 2.565539 | 68632 | 3.99 | 3.99 |
| zstd | unchanged | product | 3 | 0.111659 | 0.089179 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | product | 3 | 0.074181 | 0.074050 | 22584 | 3.99 | 3.99 |
| zstd | option-change | product | 3 | 0.081907 | 0.081855 | 22584 | 3.99 | 3.99 |
| zstd | initial | musl | 3 | 2.608440 | 2.324619 | 67072 | 3.99 | 3.99 |
| zstd | unchanged | musl | 3 | 0.098044 | 0.095966 | 22584 | 3.99 | 3.99 |
| zstd | cmakelists-edit | musl | 3 | 0.089403 | 0.089277 | 22584 | 3.99 | 3.99 |
| zstd | option-change | musl | 3 | 0.094707 | 0.088513 | 22584 | 3.99 | 3.99 |
| zstd | initial | product | 4 | 2.300133 | 2.255726 | 66740 | 3.99 | 4.31 |
| zstd | unchanged | product | 4 | 0.093890 | 0.092249 | 22584 | 4.31 | 4.31 |
| zstd | cmakelists-edit | product | 4 | 0.081812 | 0.081601 | 22584 | 4.31 | 4.31 |
| zstd | option-change | product | 4 | 0.090348 | 0.090310 | 22584 | 4.31 | 4.31 |
| zstd | initial | musl | 4 | 2.360373 | 2.358447 | 68624 | 4.31 | 4.31 |
| zstd | unchanged | musl | 4 | 0.097251 | 0.096069 | 22584 | 4.31 | 4.29 |
| zstd | cmakelists-edit | musl | 4 | 0.095479 | 0.093679 | 22584 | 4.29 | 4.29 |
| zstd | option-change | musl | 4 | 0.097061 | 0.097055 | 22584 | 4.29 | 4.29 |
| zstd | initial | kitware | 4 | 2.127325 | 2.165908 | 67388 | 4.29 | 4.29 |
| zstd | unchanged | kitware | 4 | 0.055974 | 0.055218 | 22584 | 4.29 | 4.29 |
| zstd | cmakelists-edit | kitware | 4 | 0.057882 | 0.056255 | 22584 | 4.29 | 4.29 |
| zstd | option-change | kitware | 4 | 0.057360 | 0.056925 | 22584 | 4.29 | 4.29 |
| zstd | initial | musl | 5 | 2.295648 | 2.428463 | 65772 | 4.29 | 4.26 |
| zstd | unchanged | musl | 5 | 0.081047 | 0.080955 | 22584 | 4.26 | 4.26 |
| zstd | cmakelists-edit | musl | 5 | 0.075641 | 0.075534 | 22584 | 4.26 | 4.26 |
| zstd | option-change | musl | 5 | 0.081284 | 0.081022 | 22584 | 4.26 | 4.26 |
| zstd | initial | kitware | 5 | 2.183655 | 2.288117 | 66880 | 4.26 | 4.26 |
| zstd | unchanged | kitware | 5 | 0.053727 | 0.053467 | 22584 | 4.26 | 4.26 |
| zstd | cmakelists-edit | kitware | 5 | 0.055067 | 0.054909 | 22584 | 4.26 | 4.26 |
| zstd | option-change | kitware | 5 | 0.056819 | 0.056679 | 22584 | 4.26 | 4.26 |
| zstd | initial | product | 5 | 2.404268 | 2.526391 | 61612 | 4.26 | 4.16 |
| zstd | unchanged | product | 5 | 0.094442 | 0.091125 | 22584 | 4.16 | 4.16 |
| zstd | cmakelists-edit | product | 5 | 0.081115 | 0.080893 | 22584 | 4.16 | 4.16 |
| zstd | option-change | product | 5 | 0.094081 | 0.093932 | 22584 | 4.16 | 4.16 |
| zstd | initial | kitware | 6 | 2.417168 | 2.560378 | 60080 | 4.16 | 4.16 |
| zstd | unchanged | kitware | 6 | 0.072972 | 0.071479 | 22584 | 4.16 | 4.16 |
| zstd | cmakelists-edit | kitware | 6 | 0.061410 | 0.061321 | 22584 | 4.16 | 4.16 |
| zstd | option-change | kitware | 6 | 0.054228 | 0.053975 | 22584 | 4.16 | 4.16 |
| zstd | initial | product | 6 | 2.592198 | 2.736257 | 64808 | 4.16 | 4.15 |
| zstd | unchanged | product | 6 | 0.089953 | 0.089794 | 22584 | 4.15 | 4.15 |
| zstd | cmakelists-edit | product | 6 | 0.080629 | 0.080589 | 22584 | 4.15 | 4.15 |
| zstd | option-change | product | 6 | 0.089476 | 0.089329 | 22584 | 4.15 | 4.15 |
| zstd | initial | musl | 6 | 2.366570 | 2.478641 | 61792 | 4.15 | 4.15 |
| zstd | unchanged | musl | 6 | 0.076036 | 0.075189 | 22584 | 4.15 | 4.15 |
| zstd | cmakelists-edit | musl | 6 | 0.078767 | 0.078734 | 22584 | 4.15 | 4.15 |
| zstd | option-change | musl | 6 | 0.094368 | 0.094365 | 22584 | 4.15 | 4.15 |
| zstd | initial | product | 7 | 2.210565 | 2.331024 | 62592 | 4.15 | 4.14 |
| zstd | unchanged | product | 7 | 0.094712 | 0.094544 | 22584 | 4.14 | 4.14 |
| zstd | cmakelists-edit | product | 7 | 0.076648 | 0.076540 | 22584 | 4.14 | 4.14 |
| zstd | option-change | product | 7 | 0.088615 | 0.088500 | 22584 | 4.14 | 4.14 |
| zstd | initial | musl | 7 | 2.194218 | 2.291560 | 63864 | 4.14 | 4.14 |
| zstd | unchanged | musl | 7 | 0.089364 | 0.089338 | 22584 | 4.14 | 4.14 |
| zstd | cmakelists-edit | musl | 7 | 0.076079 | 0.075991 | 22584 | 4.14 | 4.14 |
| zstd | option-change | musl | 7 | 0.082069 | 0.081791 | 22584 | 4.14 | 4.14 |
| zstd | initial | kitware | 7 | 2.108319 | 2.192859 | 67604 | 4.14 | 4.04 |
| zstd | unchanged | kitware | 7 | 0.070800 | 0.061235 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | kitware | 7 | 0.058047 | 0.057904 | 22584 | 4.04 | 4.04 |
| zstd | option-change | kitware | 7 | 0.056237 | 0.056040 | 22584 | 4.04 | 4.04 |
| zstd | initial | musl | 8 | 2.232344 | 2.350197 | 64952 | 4.04 | 4.04 |
| zstd | unchanged | musl | 8 | 0.075203 | 0.075105 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | musl | 8 | 0.078620 | 0.075528 | 22584 | 4.04 | 4.04 |
| zstd | option-change | musl | 8 | 0.084781 | 0.081083 | 22584 | 4.04 | 4.04 |
| zstd | initial | kitware | 8 | 2.478341 | 2.618468 | 63888 | 4.04 | 4.04 |
| zstd | unchanged | kitware | 8 | 0.058019 | 0.057798 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | kitware | 8 | 0.056207 | 0.056143 | 22584 | 4.04 | 4.04 |
| zstd | option-change | kitware | 8 | 0.056453 | 0.056317 | 22584 | 4.04 | 4.04 |
| zstd | initial | product | 8 | 2.257794 | 2.393927 | 67992 | 4.04 | 4.04 |
| zstd | unchanged | product | 8 | 0.091461 | 0.091455 | 22584 | 4.04 | 3.96 |
| zstd | cmakelists-edit | product | 8 | 0.078906 | 0.078870 | 22584 | 3.96 | 3.96 |
| zstd | option-change | product | 8 | 0.088475 | 0.088094 | 22584 | 3.96 | 3.96 |
| zstd | initial | kitware | 9 | 2.204189 | 2.362928 | 67068 | 3.96 | 3.96 |
| zstd | unchanged | kitware | 9 | 0.061670 | 0.061581 | 22584 | 3.96 | 3.96 |
| zstd | cmakelists-edit | kitware | 9 | 0.054742 | 0.054670 | 22584 | 3.96 | 3.96 |
| zstd | option-change | kitware | 9 | 0.055114 | 0.054858 | 22584 | 3.96 | 3.96 |
| zstd | initial | product | 9 | 2.301692 | 2.438533 | 67692 | 3.96 | 4.04 |
| zstd | unchanged | product | 9 | 0.089488 | 0.089448 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | product | 9 | 0.094892 | 0.094830 | 22584 | 4.04 | 4.04 |
| zstd | option-change | product | 9 | 0.101577 | 0.099748 | 22584 | 4.04 | 4.04 |
| zstd | initial | musl | 9 | 2.258531 | 2.352006 | 63560 | 4.04 | 4.04 |
| zstd | unchanged | musl | 9 | 0.089801 | 0.089546 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | musl | 9 | 0.082878 | 0.082871 | 22584 | 4.04 | 4.04 |
| zstd | option-change | musl | 9 | 0.102871 | 0.102638 | 22584 | 4.04 | 4.04 |
| zstd | initial | product | 10 | 2.344023 | 2.486719 | 64936 | 4.04 | 4.04 |
| zstd | unchanged | product | 10 | 0.079766 | 0.079612 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | product | 10 | 0.080682 | 0.080536 | 22584 | 4.04 | 4.04 |
| zstd | option-change | product | 10 | 0.097260 | 0.097118 | 22584 | 4.04 | 4.04 |
| zstd | initial | musl | 10 | 2.335860 | 2.506928 | 66300 | 4.04 | 4.04 |
| zstd | unchanged | musl | 10 | 0.095206 | 0.088248 | 22584 | 4.04 | 4.04 |
| zstd | cmakelists-edit | musl | 10 | 0.088415 | 0.088390 | 22584 | 4.04 | 4.04 |
| zstd | option-change | musl | 10 | 0.101582 | 0.101476 | 22584 | 4.04 | 4.04 |
| zstd | initial | kitware | 10 | 2.293137 | 2.522628 | 62880 | 4.04 | 4.03 |
| zstd | unchanged | kitware | 10 | 0.051103 | 0.050864 | 22584 | 4.03 | 4.03 |
| zstd | cmakelists-edit | kitware | 10 | 0.051189 | 0.051040 | 22584 | 4.03 | 4.03 |
| zstd | option-change | kitware | 10 | 0.057653 | 0.057261 | 22584 | 4.03 | 4.03 |
| libjpeg-turbo | initial | product | 1 | 1.383633 | 1.425959 | 65500 | 5.11 | 5.10 |
| libjpeg-turbo | unchanged | product | 1 | 0.218550 | 0.209888 | 62696 | 5.10 | 5.10 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.192920 | 0.195029 | 63144 | 5.10 | 5.10 |
| libjpeg-turbo | option-change | product | 1 | 0.208348 | 0.203069 | 62452 | 5.10 | 5.10 |
| libjpeg-turbo | initial | musl | 1 | 1.325134 | 1.403071 | 65488 | 5.10 | 5.10 |
| libjpeg-turbo | unchanged | musl | 1 | 0.200763 | 0.189571 | 62520 | 5.10 | 5.10 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.206938 | 0.205855 | 61672 | 5.10 | 5.10 |
| libjpeg-turbo | option-change | musl | 1 | 0.193805 | 0.192613 | 62700 | 5.10 | 5.10 |
| libjpeg-turbo | initial | kitware | 1 | 1.324435 | 1.401103 | 65372 | 5.10 | 5.01 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.174626 | 0.173510 | 62832 | 5.01 | 5.01 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.178350 | 0.170488 | 62576 | 5.01 | 5.01 |
| libjpeg-turbo | option-change | kitware | 1 | 0.175378 | 0.182972 | 62352 | 5.01 | 5.01 |
| libjpeg-turbo | initial | musl | 2 | 1.355852 | 1.463315 | 65548 | 5.01 | 5.01 |
| libjpeg-turbo | unchanged | musl | 2 | 0.216341 | 0.213679 | 62408 | 5.01 | 5.01 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.195794 | 0.193196 | 63160 | 5.01 | 5.01 |
| libjpeg-turbo | option-change | musl | 2 | 0.212713 | 0.232567 | 62360 | 5.01 | 5.01 |
| libjpeg-turbo | initial | kitware | 2 | 1.271326 | 1.319311 | 65676 | 5.01 | 4.93 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.167831 | 0.169472 | 62628 | 4.93 | 4.93 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.177222 | 0.185461 | 62432 | 4.93 | 4.93 |
| libjpeg-turbo | option-change | kitware | 2 | 0.182919 | 0.182149 | 61592 | 4.93 | 4.93 |
| libjpeg-turbo | initial | product | 2 | 1.356824 | 1.435961 | 65308 | 4.93 | 4.93 |
| libjpeg-turbo | unchanged | product | 2 | 0.199779 | 0.200964 | 62884 | 4.93 | 4.93 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.192172 | 0.194300 | 62704 | 4.93 | 4.93 |
| libjpeg-turbo | option-change | product | 2 | 0.209109 | 0.209394 | 62000 | 4.93 | 4.93 |
| libjpeg-turbo | initial | kitware | 3 | 1.292328 | 1.314723 | 65684 | 4.93 | 4.93 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.163354 | 0.165664 | 62440 | 4.93 | 4.86 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.170005 | 0.170335 | 61444 | 4.86 | 4.86 |
| libjpeg-turbo | option-change | kitware | 3 | 0.180417 | 0.184598 | 63100 | 4.86 | 4.86 |
| libjpeg-turbo | initial | product | 3 | 1.251562 | 1.303097 | 65100 | 4.86 | 4.86 |
| libjpeg-turbo | unchanged | product | 3 | 0.190603 | 0.190778 | 62436 | 4.86 | 4.86 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.194691 | 0.197437 | 62616 | 4.86 | 4.86 |
| libjpeg-turbo | option-change | product | 3 | 0.196609 | 0.196706 | 62520 | 4.86 | 4.86 |
| libjpeg-turbo | initial | musl | 3 | 1.227847 | 1.261760 | 65444 | 4.86 | 4.86 |
| libjpeg-turbo | unchanged | musl | 3 | 0.200158 | 0.202541 | 62396 | 4.86 | 4.86 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.182070 | 0.183750 | 62484 | 4.86 | 4.86 |
| libjpeg-turbo | option-change | musl | 3 | 0.191104 | 0.192172 | 61400 | 4.86 | 4.79 |
| libjpeg-turbo | initial | product | 4 | 1.408121 | 1.446978 | 64908 | 4.79 | 4.79 |
| libjpeg-turbo | unchanged | product | 4 | 0.181481 | 0.181785 | 62488 | 4.79 | 4.79 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.187485 | 0.183778 | 62856 | 4.79 | 4.79 |
| libjpeg-turbo | option-change | product | 4 | 0.201093 | 0.203827 | 62364 | 4.79 | 4.79 |
| libjpeg-turbo | initial | musl | 4 | 1.300657 | 1.331321 | 65652 | 4.79 | 4.79 |
| libjpeg-turbo | unchanged | musl | 4 | 0.186937 | 0.189615 | 62192 | 4.79 | 4.79 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.199581 | 0.203651 | 61436 | 4.79 | 4.79 |
| libjpeg-turbo | option-change | musl | 4 | 0.201455 | 0.204254 | 62756 | 4.79 | 4.79 |
| libjpeg-turbo | initial | kitware | 4 | 1.134720 | 1.165492 | 65500 | 4.79 | 4.73 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.161316 | 0.163919 | 63156 | 4.73 | 4.73 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.153073 | 0.154300 | 62684 | 4.73 | 4.73 |
| libjpeg-turbo | option-change | kitware | 4 | 0.170239 | 0.171593 | 61748 | 4.73 | 4.73 |
| libjpeg-turbo | initial | musl | 5 | 1.156363 | 1.183764 | 65672 | 4.73 | 4.73 |
| libjpeg-turbo | unchanged | musl | 5 | 0.184898 | 0.186647 | 62464 | 4.73 | 4.73 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.178252 | 0.180196 | 61656 | 4.73 | 4.73 |
| libjpeg-turbo | option-change | musl | 5 | 0.197961 | 0.199634 | 62536 | 4.73 | 4.73 |
| libjpeg-turbo | initial | kitware | 5 | 1.099465 | 1.130258 | 65668 | 4.73 | 4.73 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.165547 | 0.167278 | 61472 | 4.73 | 4.73 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.198080 | 0.168323 | 62116 | 4.73 | 4.67 |
| libjpeg-turbo | option-change | kitware | 5 | 0.192182 | 0.193893 | 61680 | 4.67 | 4.67 |
| libjpeg-turbo | initial | product | 5 | 1.253004 | 1.293378 | 65576 | 4.67 | 4.67 |
| libjpeg-turbo | unchanged | product | 5 | 0.196952 | 0.199500 | 62776 | 4.67 | 4.67 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.193017 | 0.194642 | 62664 | 4.67 | 4.67 |
| libjpeg-turbo | option-change | product | 5 | 0.216313 | 0.218988 | 62488 | 4.67 | 4.67 |
| libjpeg-turbo | initial | kitware | 6 | 1.176590 | 1.216814 | 65176 | 4.67 | 4.67 |
| libjpeg-turbo | unchanged | kitware | 6 | 0.171788 | 0.174489 | 61424 | 4.67 | 4.67 |
| libjpeg-turbo | cmakelists-edit | kitware | 6 | 0.182987 | 0.185455 | 62868 | 4.67 | 4.67 |
| libjpeg-turbo | option-change | kitware | 6 | 0.169402 | 0.171917 | 61360 | 4.67 | 4.67 |
| libjpeg-turbo | initial | product | 6 | 1.186360 | 1.236906 | 65332 | 4.67 | 4.53 |
| libjpeg-turbo | unchanged | product | 6 | 0.203812 | 0.205532 | 62764 | 4.53 | 4.53 |
| libjpeg-turbo | cmakelists-edit | product | 6 | 0.197563 | 0.199973 | 62456 | 4.53 | 4.53 |
| libjpeg-turbo | option-change | product | 6 | 0.200202 | 0.202928 | 62788 | 4.53 | 4.53 |
| libjpeg-turbo | initial | musl | 6 | 1.299274 | 1.359789 | 65260 | 4.53 | 4.53 |
| libjpeg-turbo | unchanged | musl | 6 | 0.184426 | 0.186723 | 61668 | 4.53 | 4.53 |
| libjpeg-turbo | cmakelists-edit | musl | 6 | 0.190789 | 0.197917 | 61764 | 4.53 | 4.53 |
| libjpeg-turbo | option-change | musl | 6 | 0.195321 | 0.198056 | 61464 | 4.53 | 4.53 |
| libjpeg-turbo | initial | product | 7 | 1.201822 | 1.267295 | 65544 | 4.53 | 4.49 |
| libjpeg-turbo | unchanged | product | 7 | 0.197208 | 0.199964 | 61388 | 4.49 | 4.49 |
| libjpeg-turbo | cmakelists-edit | product | 7 | 0.196018 | 0.198731 | 63180 | 4.49 | 4.49 |
| libjpeg-turbo | option-change | product | 7 | 0.220837 | 0.223794 | 62404 | 4.49 | 4.49 |
| libjpeg-turbo | initial | musl | 7 | 1.178581 | 1.213681 | 65224 | 4.49 | 4.49 |
| libjpeg-turbo | unchanged | musl | 7 | 0.181449 | 0.182944 | 62540 | 4.49 | 4.49 |
| libjpeg-turbo | cmakelists-edit | musl | 7 | 0.176385 | 0.177696 | 62588 | 4.49 | 4.49 |
| libjpeg-turbo | option-change | musl | 7 | 0.191647 | 0.194260 | 63176 | 4.49 | 4.49 |
| libjpeg-turbo | initial | kitware | 7 | 1.211269 | 1.277515 | 64912 | 4.49 | 4.49 |
| libjpeg-turbo | unchanged | kitware | 7 | 0.186919 | 0.187545 | 62732 | 4.49 | 4.49 |
| libjpeg-turbo | cmakelists-edit | kitware | 7 | 0.162448 | 0.164798 | 62048 | 4.49 | 4.37 |
| libjpeg-turbo | option-change | kitware | 7 | 0.192511 | 0.196704 | 61680 | 4.37 | 4.37 |
| libjpeg-turbo | initial | musl | 8 | 1.220828 | 1.271812 | 65528 | 4.37 | 4.37 |
| libjpeg-turbo | unchanged | musl | 8 | 0.186262 | 0.188440 | 61464 | 4.37 | 4.37 |
| libjpeg-turbo | cmakelists-edit | musl | 8 | 0.214338 | 0.223154 | 61460 | 4.37 | 4.37 |
| libjpeg-turbo | option-change | musl | 8 | 0.207837 | 0.216670 | 61664 | 4.37 | 4.37 |
| libjpeg-turbo | initial | kitware | 8 | 1.230349 | 1.268040 | 65600 | 4.37 | 4.37 |
| libjpeg-turbo | unchanged | kitware | 8 | 0.171282 | 0.174265 | 62448 | 4.37 | 4.37 |
| libjpeg-turbo | cmakelists-edit | kitware | 8 | 0.190962 | 0.194980 | 61412 | 4.37 | 4.37 |
| libjpeg-turbo | option-change | kitware | 8 | 0.209731 | 0.212405 | 63120 | 4.37 | 4.37 |
| libjpeg-turbo | initial | product | 8 | 1.209533 | 1.260195 | 65568 | 4.37 | 4.34 |
| libjpeg-turbo | unchanged | product | 8 | 0.201345 | 0.202592 | 62580 | 4.34 | 4.34 |
| libjpeg-turbo | cmakelists-edit | product | 8 | 0.187323 | 0.188859 | 62680 | 4.34 | 4.34 |
| libjpeg-turbo | option-change | product | 8 | 0.220047 | 0.221874 | 61460 | 4.34 | 4.34 |
| libjpeg-turbo | initial | kitware | 9 | 1.245583 | 1.305757 | 65028 | 4.34 | 4.34 |
| libjpeg-turbo | unchanged | kitware | 9 | 0.169278 | 0.171354 | 63148 | 4.34 | 4.34 |
| libjpeg-turbo | cmakelists-edit | kitware | 9 | 0.169722 | 0.174416 | 62680 | 4.34 | 4.34 |
| libjpeg-turbo | option-change | kitware | 9 | 0.179499 | 0.182064 | 62184 | 4.34 | 4.34 |
| libjpeg-turbo | initial | product | 9 | 1.258131 | 1.309761 | 65228 | 4.34 | 4.23 |
| libjpeg-turbo | unchanged | product | 9 | 0.203926 | 0.209821 | 61664 | 4.23 | 4.23 |
| libjpeg-turbo | cmakelists-edit | product | 9 | 0.219725 | 0.226734 | 63080 | 4.23 | 4.23 |
| libjpeg-turbo | option-change | product | 9 | 0.205719 | 0.208298 | 62388 | 4.23 | 4.23 |
| libjpeg-turbo | initial | musl | 9 | 1.295087 | 1.362184 | 65396 | 4.23 | 4.23 |
| libjpeg-turbo | unchanged | musl | 9 | 0.188113 | 0.190601 | 62696 | 4.23 | 4.23 |
| libjpeg-turbo | cmakelists-edit | musl | 9 | 0.198560 | 0.204847 | 61436 | 4.23 | 4.23 |
| libjpeg-turbo | option-change | musl | 9 | 0.207111 | 0.209507 | 63088 | 4.23 | 4.23 |
| libjpeg-turbo | initial | product | 10 | 1.338524 | 1.370856 | 65404 | 4.23 | 4.23 |
| libjpeg-turbo | unchanged | product | 10 | 0.250706 | 0.259384 | 59632 | 4.23 | 4.21 |
| libjpeg-turbo | cmakelists-edit | product | 10 | 0.460024 | 0.547016 | 62200 | 4.21 | 4.21 |
| libjpeg-turbo | option-change | product | 10 | 0.471587 | 0.467468 | 62152 | 4.21 | 4.21 |
| libjpeg-turbo | initial | musl | 10 | 1.485329 | 1.605305 | 65108 | 4.21 | 4.21 |
| libjpeg-turbo | unchanged | musl | 10 | 0.217233 | 0.221886 | 61228 | 4.21 | 4.21 |
| libjpeg-turbo | cmakelists-edit | musl | 10 | 0.211849 | 0.214794 | 62624 | 4.21 | 4.21 |
| libjpeg-turbo | option-change | musl | 10 | 0.247853 | 0.248720 | 62524 | 4.21 | 4.21 |
| libjpeg-turbo | initial | kitware | 10 | 1.397811 | 1.436656 | 64516 | 4.21 | 4.20 |
| libjpeg-turbo | unchanged | kitware | 10 | 0.155069 | 0.166021 | 62432 | 4.20 | 4.20 |
| libjpeg-turbo | cmakelists-edit | kitware | 10 | 0.172019 | 0.177645 | 62368 | 4.20 | 4.20 |
| libjpeg-turbo | option-change | kitware | 10 | 0.168989 | 0.173491 | 61956 | 4.20 | 4.20 |
| llvm-clang | initial | product | 1 | 31.463758 | 31.558345 | 491040 | 3.46 | 3.03 |
| llvm-clang | unchanged | product | 1 | 18.122608 | 18.132293 | 481032 | 3.03 | 2.81 |
| llvm-clang | cmakelists-edit | product | 1 | 18.534702 | 18.437177 | 481108 | 2.81 | 2.69 |
| llvm-clang | option-change | product | 1 | 18.712407 | 18.681464 | 480888 | 2.52 | 2.43 |
| llvm-clang | initial | musl | 1 | 31.848954 | 31.989835 | 488704 | 2.43 | 2.42 |
| llvm-clang | unchanged | musl | 1 | 17.926914 | 17.993429 | 478000 | 2.42 | 2.40 |
| llvm-clang | cmakelists-edit | musl | 1 | 18.108905 | 18.128413 | 478108 | 2.40 | 2.37 |
| llvm-clang | option-change | musl | 1 | 18.336598 | 18.324273 | 478032 | 2.26 | 2.13 |
| llvm-clang | initial | kitware | 1 | 28.048751 | 28.425045 | 387984 | 2.12 | 2.02 |
| llvm-clang | unchanged | kitware | 1 | 16.052877 | 16.059264 | 378828 | 1.94 | 2.08 |
| llvm-clang | cmakelists-edit | kitware | 1 | 16.189277 | 16.189654 | 378772 | 2.08 | 1.91 |
| llvm-clang | option-change | kitware | 1 | 16.115485 | 16.110689 | 379464 | 1.94 | 2.04 |
| llvm-clang | initial | musl | 2 | 29.931763 | 30.034925 | 488668 | 2.11 | 2.33 |
| llvm-clang | unchanged | musl | 2 | 18.211669 | 18.072103 | 478160 | 2.33 | 2.52 |
| llvm-clang | cmakelists-edit | musl | 2 | 17.650914 | 17.654352 | 478064 | 2.52 | 2.56 |
| llvm-clang | option-change | musl | 2 | 17.815901 | 17.833751 | 478172 | 2.87 | 3.12 |
| llvm-clang | initial | kitware | 2 | 28.693714 | 29.246886 | 387924 | 3.03 | 2.55 |
| llvm-clang | unchanged | kitware | 2 | 15.876218 | 15.878596 | 378880 | 2.55 | 2.65 |
| llvm-clang | cmakelists-edit | kitware | 2 | 16.114134 | 16.127312 | 378852 | 2.65 | 2.74 |
| llvm-clang | option-change | kitware | 2 | 15.895201 | 15.917889 | 378944 | 2.58 | 2.58 |
| llvm-clang | initial | product | 2 | 30.244606 | 30.711528 | 491176 | 2.58 | 2.55 |
| llvm-clang | unchanged | product | 2 | 17.793317 | 17.816727 | 480792 | 2.55 | 2.53 |
| llvm-clang | cmakelists-edit | product | 2 | 18.010522 | 18.014883 | 480688 | 2.53 | 2.58 |
| llvm-clang | option-change | product | 2 | 17.607971 | 17.619742 | 480872 | 2.42 | 2.30 |
| llvm-clang | initial | kitware | 3 | 28.368859 | 28.780959 | 388068 | 2.30 | 2.09 |
| llvm-clang | unchanged | kitware | 3 | 15.932731 | 15.946187 | 378820 | 2.09 | 2.15 |
| llvm-clang | cmakelists-edit | kitware | 3 | 16.190621 | 16.195238 | 378584 | 2.15 | 2.27 |
| llvm-clang | option-change | kitware | 3 | 16.101542 | 16.108739 | 378620 | 2.28 | 2.20 |
| llvm-clang | initial | product | 3 | 30.181162 | 30.825113 | 491132 | 2.20 | 2.23 |
| llvm-clang | unchanged | product | 3 | 18.082733 | 18.093812 | 480616 | 2.23 | 2.24 |
| llvm-clang | cmakelists-edit | product | 3 | 17.755589 | 17.789228 | 480864 | 2.24 | 2.41 |
| llvm-clang | option-change | product | 3 | 17.898556 | 17.933674 | 481012 | 2.45 | 2.40 |
| llvm-clang | initial | musl | 3 | 31.532546 | 31.435321 | 488464 | 2.40 | 2.38 |
| llvm-clang | unchanged | musl | 3 | 17.671774 | 17.683203 | 477980 | 2.35 | 2.19 |
| llvm-clang | cmakelists-edit | musl | 3 | 17.934473 | 17.932055 | 478100 | 2.19 | 2.14 |
| llvm-clang | option-change | musl | 3 | 17.500086 | 17.499434 | 477860 | 2.11 | 2.15 |
| llvm-clang | initial | product | 4 | 30.323759 | 30.793385 | 491320 | 2.15 | 2.09 |
| llvm-clang | unchanged | product | 4 | 17.999045 | 18.006869 | 480932 | 2.09 | 2.13 |
| llvm-clang | cmakelists-edit | product | 4 | 17.776854 | 17.791169 | 480848 | 2.13 | 2.32 |
| llvm-clang | option-change | product | 4 | 17.828408 | 17.840236 | 480796 | 2.32 | 2.29 |
| llvm-clang | initial | musl | 4 | 29.642449 | 30.012801 | 488392 | 2.29 | 2.73 |
| llvm-clang | unchanged | musl | 4 | 18.203050 | 18.207667 | 477856 | 2.73 | 2.52 |
| llvm-clang | cmakelists-edit | musl | 4 | 18.334108 | 18.345643 | 478060 | 2.52 | 2.46 |
| llvm-clang | option-change | musl | 4 | 17.660983 | 17.674014 | 478136 | 2.27 | 2.29 |
| llvm-clang | initial | kitware | 4 | 27.498690 | 27.833399 | 388560 | 2.29 | 2.19 |
| llvm-clang | unchanged | kitware | 4 | 16.143381 | 16.149509 | 378788 | 2.09 | 2.07 |
| llvm-clang | cmakelists-edit | kitware | 4 | 15.847867 | 15.856295 | 379368 | 2.07 | 2.06 |
| llvm-clang | option-change | kitware | 4 | 16.694227 | 16.725437 | 378632 | 1.96 | 1.91 |
| llvm-clang | initial | musl | 5 | 29.945207 | 30.277064 | 488380 | 1.91 | 2.29 |
| llvm-clang | unchanged | musl | 5 | 17.651288 | 17.672697 | 478244 | 2.29 | 2.27 |
| llvm-clang | cmakelists-edit | musl | 5 | 18.260263 | 18.266670 | 478084 | 2.27 | 2.28 |
| llvm-clang | option-change | musl | 5 | 18.091857 | 18.123512 | 478100 | 2.26 | 2.32 |
| llvm-clang | initial | kitware | 5 | 27.752751 | 27.855209 | 387944 | 2.32 | 2.28 |
| llvm-clang | unchanged | kitware | 5 | 16.137382 | 16.145627 | 378596 | 2.28 | 2.44 |
| llvm-clang | cmakelists-edit | kitware | 5 | 15.740472 | 15.748568 | 378792 | 2.44 | 2.34 |
| llvm-clang | option-change | kitware | 5 | 15.863876 | 15.872024 | 378512 | 2.28 | 2.33 |
| llvm-clang | initial | product | 5 | 30.318559 | 30.597018 | 491144 | 2.33 | 2.20 |
| llvm-clang | unchanged | product | 5 | 18.237301 | 18.244803 | 480840 | 2.20 | 2.41 |
| llvm-clang | cmakelists-edit | product | 5 | 17.856735 | 17.863195 | 481084 | 2.41 | 2.48 |
| llvm-clang | option-change | product | 5 | 17.782375 | 17.788152 | 480980 | 2.20 | 2.06 |
| llvm-clang | initial | kitware | 6 | 27.206861 | 27.570192 | 389124 | 2.06 | 2.40 |
| llvm-clang | unchanged | kitware | 6 | 15.538711 | 15.546532 | 379852 | 2.53 | 2.49 |
| llvm-clang | cmakelists-edit | kitware | 6 | 15.842216 | 15.891941 | 379776 | 2.49 | 2.45 |
| llvm-clang | option-change | kitware | 6 | 16.284925 | 16.294734 | 379836 | 2.42 | 2.47 |
| llvm-clang | initial | product | 6 | 29.591510 | 29.858046 | 492112 | 2.43 | 2.55 |
| llvm-clang | unchanged | product | 6 | 18.140995 | 18.148449 | 484076 | 2.55 | 2.36 |
| llvm-clang | cmakelists-edit | product | 6 | 17.948426 | 17.946916 | 483944 | 2.36 | 2.32 |
| llvm-clang | option-change | product | 6 | 17.835414 | 17.937715 | 483736 | 2.37 | 2.53 |
| llvm-clang | initial | musl | 6 | 29.736528 | 30.014627 | 488580 | 2.53 | 2.48 |
| llvm-clang | unchanged | musl | 6 | 18.112022 | 18.118095 | 478944 | 2.44 | 2.41 |
| llvm-clang | cmakelists-edit | musl | 6 | 17.690164 | 17.696725 | 478028 | 2.41 | 2.29 |
| llvm-clang | option-change | musl | 6 | 17.861062 | 17.861585 | 478056 | 2.38 | 2.21 |
| llvm-clang | initial | product | 7 | 30.023340 | 30.356556 | 495152 | 2.21 | 2.18 |
| llvm-clang | unchanged | product | 7 | 18.230492 | 18.262267 | 484152 | 2.16 | 2.13 |
| llvm-clang | cmakelists-edit | product | 7 | 18.142094 | 17.839410 | 483992 | 2.13 | 2.09 |
| llvm-clang | option-change | product | 7 | 18.124758 | 18.130369 | 483784 | 2.13 | 2.11 |
| llvm-clang | initial | musl | 7 | 29.897002 | 30.187051 | 488520 | 2.11 | 2.12 |
| llvm-clang | unchanged | musl | 7 | 18.082546 | 18.087356 | 477848 | 2.19 | 2.08 |
| llvm-clang | cmakelists-edit | musl | 7 | 17.697459 | 17.705315 | 478840 | 2.08 | 2.21 |
| llvm-clang | option-change | musl | 7 | 17.600838 | 17.608978 | 478000 | 2.01 | 2.00 |
| llvm-clang | initial | kitware | 7 | 27.405561 | 27.655324 | 388996 | 2.00 | 2.07 |
| llvm-clang | unchanged | kitware | 7 | 16.044559 | 16.046281 | 379920 | 2.07 | 2.13 |
| llvm-clang | cmakelists-edit | kitware | 7 | 15.935507 | 15.941528 | 379964 | 2.13 | 2.24 |
| llvm-clang | option-change | kitware | 7 | 15.959382 | 15.960595 | 380824 | 2.10 | 1.92 |
| llvm-clang | initial | musl | 8 | 28.931404 | 29.172792 | 488320 | 1.92 | 2.19 |
| llvm-clang | unchanged | musl | 8 | 17.876951 | 17.885875 | 477924 | 2.19 | 2.22 |
| llvm-clang | cmakelists-edit | musl | 8 | 18.146143 | 18.151482 | 477692 | 2.22 | 2.25 |
| llvm-clang | option-change | musl | 8 | 17.721170 | 17.729425 | 477968 | 2.40 | 2.31 |
| llvm-clang | initial | kitware | 8 | 27.773622 | 28.010362 | 389964 | 2.28 | 2.25 |
| llvm-clang | unchanged | kitware | 8 | 15.604664 | 15.610734 | 380808 | 2.23 | 2.18 |
| llvm-clang | cmakelists-edit | kitware | 8 | 16.047743 | 16.056526 | 380800 | 2.18 | 2.14 |
| llvm-clang | option-change | kitware | 8 | 15.583828 | 15.590982 | 380792 | 2.19 | 2.23 |
| llvm-clang | initial | product | 8 | 29.607447 | 29.853531 | 494208 | 2.21 | 2.14 |
| llvm-clang | unchanged | product | 8 | 17.936602 | 17.948716 | 483820 | 2.29 | 2.16 |
| llvm-clang | cmakelists-edit | product | 8 | 17.985123 | 17.990575 | 483764 | 2.16 | 2.12 |
| llvm-clang | option-change | product | 8 | 17.838228 | 17.846801 | 483872 | 2.01 | 2.09 |
| llvm-clang | initial | kitware | 9 | 26.941212 | 26.981081 | 389908 | 2.09 | 2.14 |
| llvm-clang | unchanged | kitware | 9 | 15.596030 | 15.606908 | 381764 | 2.14 | 2.49 |
| llvm-clang | cmakelists-edit | kitware | 9 | 15.920637 | 15.927528 | 380444 | 2.49 | 2.52 |
| llvm-clang | option-change | kitware | 9 | 15.718347 | 15.722337 | 380924 | 2.37 | 2.53 |
| llvm-clang | initial | product | 9 | 29.279966 | 29.528314 | 494388 | 2.53 | 2.53 |
| llvm-clang | unchanged | product | 9 | 18.251697 | 18.257351 | 483792 | 2.53 | 2.51 |
| llvm-clang | cmakelists-edit | product | 9 | 18.026483 | 18.006596 | 484016 | 2.51 | 2.39 |
| llvm-clang | option-change | product | 9 | 17.747892 | 17.749674 | 484024 | 2.28 | 2.26 |
| llvm-clang | initial | musl | 9 | 29.081719 | 29.319881 | 488716 | 2.26 | 2.17 |
| llvm-clang | unchanged | musl | 9 | 17.825834 | 17.833306 | 477996 | 2.17 | 2.13 |
| llvm-clang | cmakelists-edit | musl | 9 | 17.834664 | 17.841876 | 477896 | 2.13 | 2.18 |
| llvm-clang | option-change | musl | 9 | 17.698833 | 17.708595 | 477876 | 2.13 | 2.18 |
| llvm-clang | initial | product | 10 | 29.746238 | 29.966539 | 494360 | 2.16 | 2.05 |
| llvm-clang | unchanged | product | 10 | 18.131879 | 18.141792 | 484104 | 2.05 | 1.96 |
| llvm-clang | cmakelists-edit | product | 10 | 17.772699 | 17.779954 | 484728 | 1.96 | 1.98 |
| llvm-clang | option-change | product | 10 | 18.099313 | 18.105289 | 484004 | 2.13 | 2.10 |
| llvm-clang | initial | musl | 10 | 29.972960 | 30.241740 | 488380 | 2.18 | 2.16 |
| llvm-clang | unchanged | musl | 10 | 18.295352 | 18.304035 | 477896 | 2.16 | 2.18 |
| llvm-clang | cmakelists-edit | musl | 10 | 17.904482 | 17.909427 | 477924 | 2.18 | 2.14 |
| llvm-clang | option-change | musl | 10 | 17.783273 | 17.791637 | 477924 | 2.32 | 2.25 |
| llvm-clang | initial | kitware | 10 | 26.661417 | 26.883567 | 389996 | 2.23 | 2.16 |
| llvm-clang | unchanged | kitware | 10 | 15.620962 | 15.627743 | 380740 | 2.16 | 2.13 |
| llvm-clang | cmakelists-edit | kitware | 10 | 15.841932 | 15.847575 | 380716 | 2.13 | 2.09 |
| llvm-clang | option-change | kitware | 10 | 15.967890 | 15.973172 | 380760 | 2.14 | 2.26 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 38.25    0.005676        2838         2           wait4
 10.80    0.001603         534         3           execve
  9.11    0.001352          12       110         5 open
  8.29    0.001230           6       204        13 stat
  7.85    0.001165           4       283        42 access
  6.61    0.000981           5       187       179 readlink
  5.43    0.000806          16        49        39 unlink
  5.11    0.000758         108         7         2 rename
  4.84    0.000718         359         2           fork
  2.43    0.000361           6        53         1 lstat
  1.00    0.000148          21         7         6 mkdir
  0.22    0.000032           5         6           chmod
  0.06    0.000009           9         1           chdir
  0.00    0.000000           0         1           getcwd
  0.00    0.000000           0         1           rmdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.014839          16       916       287 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 21.41    0.001669         834         2           wait4
 17.71    0.001381           4       283        42 access
 14.34    0.001118          10       110         5 open
 11.21    0.000874           4       204        13 stat
  9.22    0.000719          14        49        39 unlink
  7.68    0.000599         199         3           execve
  5.16    0.000402           2       187       179 readlink
  3.86    0.000301         150         2           fork
  3.49    0.000272           5        53         1 lstat
  3.42    0.000267          38         7         2 rename
  0.94    0.000073          10         7         6 mkdir
  0.83    0.000065          10         6           chmod
  0.64    0.000050          50         1           rmdir
  0.08    0.000006           6         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.007796           8       916       287 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 32.31    0.002630        1315         2           wait4
 12.69    0.001033           3       284        40 access
 12.31    0.001002         334         3           execve
 10.12    0.000824           7       114         7 openat
  7.30    0.000594           2       204        13 stat
  5.76    0.000469         234         2           clone
  5.11    0.000416           2       187       179 readlink
  4.36    0.000355           7        49        39 unlink
  3.71    0.000302          43         7         2 rename
  2.17    0.000177           3        53         1 lstat
  1.78    0.000145          20         7         6 mkdir
  0.92    0.000075          10         7         1 open
  0.81    0.000066          66         1           rmdir
  0.49    0.000040           6         6           chmod
  0.16    0.000013          13         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.008141           8       928       288 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 29.23    0.005296        2648         2           wait4
 21.41    0.003879           5       685       211 access
  9.74    0.001764           5       339        28 stat
  8.84    0.001601           9       161         5 open
  8.61    0.001559           4       385       369 readlink
  6.12    0.001109          11        94        85 unlink
  5.08    0.000921         307         3           execve
  3.21    0.000582         291         2           fork
  3.17    0.000574          63         9         2 rename
  2.71    0.000491           4       109         9 lstat
  0.84    0.000152          21         7         6 mkdir
  0.50    0.000091          18         5           chmod
  0.47    0.000085          85         1           rmdir
  0.07    0.000013          13         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.018117          10      1804       715 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 31.83    0.005056        2528         2           wait4
 19.50    0.003097           4       685       211 access
  9.39    0.001492           4       339        28 stat
  9.18    0.001458           9       161         5 open
  8.49    0.001349           3       385       369 readlink
  7.71    0.001224         408         3           execve
  4.27    0.000678           6       109         9 lstat
  4.07    0.000646           6        94        85 unlink
  2.78    0.000442          49         9         2 rename
  2.42    0.000384         192         2           fork
  0.33    0.000052          10         5           chmod
  0.04    0.000006           6         1           getcwd
  0.00    0.000000           0         1           chdir
  0.00    0.000000           0         7         6 mkdir
  0.00    0.000000           0         1           rmdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.015884           8      1804       715 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 21.96    0.002846        1423         2           wait4
 21.82    0.002827           4       686       209 access
 12.94    0.001677           4       378       362 readlink
 10.30    0.001334           8       165         7 openat
 10.26    0.001330           3       339        28 stat
  5.36    0.000695           7        94        85 unlink
  5.06    0.000655         218         3           execve
  3.13    0.000405          45         9         2 rename
  3.03    0.000392           3       109         9 lstat
  2.79    0.000362         181         2           clone
  1.15    0.000149          21         7         6 mkdir
  0.86    0.000111          15         7         1 open
  0.68    0.000088          88         1           rmdir
  0.49    0.000063          12         5           chmod
  0.09    0.000012          12         1           chdir
  0.08    0.000011          11         1           getcwd
  0.00    0.000000           0         7           faccessat2
------ ----------- ----------- --------- --------- ----------------
100.00    0.012957           7      1816       709 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 87.31    0.197912       14136        14         2 wait4
  2.77    0.006288           3      1718      1623 readlink
  2.04    0.004625           4      1040       451 access
  1.60    0.003638           3       927       121 stat
  1.41    0.003196          10       308        19 open
  1.15    0.002612         200        13           execve
  0.96    0.002179         311         7           fork
  0.81    0.001832           3       473         7 lstat
  0.77    0.001750           8       200       155 unlink
  0.56    0.001273          60        21         5 rename
  0.19    0.000429          61         7           clone
  0.17    0.000375          15        25        21 mkdir
  0.10    0.000236          59         4           rmdir
  0.09    0.000199           7        27           chmod
  0.04    0.000085          42         2           vfork
  0.02    0.000036           5         7           chdir
  0.01    0.000017           5         3           getcwd
  0.00    0.000000           0         4           openat
------ ----------- ----------- --------- --------- ----------------
100.00    0.226682          47      4800      2404 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 97.64    1.125036       80359        14         2 wait4
  0.49    0.005640           3      1718      1623 readlink
  0.33    0.003765           4       927       121 stat
  0.28    0.003274           3      1040       451 access
  0.26    0.002982           9       308        19 open
  0.21    0.002461          12       200       155 unlink
  0.20    0.002312           4       473         7 lstat
  0.18    0.002119         302         7           clone
  0.13    0.001510         116        13           execve
  0.12    0.001370          65        21         5 rename
  0.09    0.001034         147         7           fork
  0.02    0.000244           9        27           chmod
  0.02    0.000218          54         4           rmdir
  0.02    0.000174           6        25        21 mkdir
  0.00    0.000050           7         7           chdir
  0.00    0.000009           3         3           getcwd
  0.00    0.000000           0         2           vfork
  0.00    0.000000           0         4           openat
------ ----------- ----------- --------- --------- ----------------
100.00    1.152198         240      4800      2404 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 93.38    0.351093       25078        14         2 wait4
  1.69    0.006361           3      1718      1623 readlink
  0.78    0.002937           3       927       121 stat
  0.75    0.002814           2      1041       449 access
  0.71    0.002668         205        13           execve
  0.66    0.002471         176        14           clone
  0.54    0.002038           7       259        12 openat
  0.45    0.001685           8       200       155 unlink
  0.36    0.001340           2       473         7 lstat
  0.29    0.001098          17        64        10 open
  0.25    0.000957          45        21         5 rename
  0.05    0.000184           6        27           chmod
  0.04    0.000140           5        25        21 mkdir
  0.03    0.000110          27         4           rmdir
  0.01    0.000049          24         2           vfork
  0.01    0.000036           5         7           chdir
  0.00    0.000013           4         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.375994          78      4812      2405 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 27.62    1.417159           5    241126      3506 stat
 20.03    1.028011       16580        62         9 wait4
 16.35    0.838761           7    117306        25 lstat
 12.92    0.662986           4    150759    147465 readlink
  5.69    0.291856        5722        51           execve
  5.36    0.274956           3     70886     42409 access
  5.29    0.271318        6782        40           fork
  2.51    0.128841           6     19689     19585 unlink
  2.08    0.106990         156       682         5 rename
  2.08    0.106904           7     13777       220 open
  0.02    0.001048          69        15           clone
  0.02    0.000771           7       109           chmod
  0.01    0.000491          12        38           openat
  0.01    0.000476           7        64        54 newfstatat
  0.01    0.000304           3        80           getcwd
  0.00    0.000244           9        25        21 mkdir
  0.00    0.000139          69         2           vfork
  0.00    0.000121          30         4           rmdir
  0.00    0.000093           6        15           chdir
  0.00    0.000025           5         5           utimensat
  0.00    0.000015           7         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    5.131509           8    614737    213301 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 27.27    1.378862           5    241126      3506 stat
 19.87    1.004818       16206        62         9 wait4
 15.89    0.803557           6    117306        25 lstat
 13.54    0.684742           4    150759    147465 readlink
  6.07    0.306798        6015        51           execve
  5.92    0.299115        7477        40           fork
  5.33    0.269516           3     70886     42409 access
  2.25    0.113730           5     19689     19585 unlink
  2.21    0.111719           8     13777       220 open
  1.57    0.079613         116       682         5 rename
  0.02    0.000990           9       109           chmod
  0.01    0.000698          46        15           clone
  0.01    0.000457           7        64        54 newfstatat
  0.01    0.000345           9        38           openat
  0.01    0.000269           3        80           getcwd
  0.00    0.000213           8        25        21 mkdir
  0.00    0.000145          72         2           vfork
  0.00    0.000135           9        15           chdir
  0.00    0.000128          32         4           rmdir
  0.00    0.000017           3         5           utimensat
  0.00    0.000000           0         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    5.055867           8    614737    213301 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 29.04    1.317884           5    241126      3506 stat
 20.71    0.939939       15160        62         9 wait4
 17.56    0.797119           6    117306        25 lstat
 12.04    0.546577           3    150735    147441 readlink
  5.09    0.231087        4531        51           execve
  4.69    0.213050        3873        55           clone
  4.52    0.205187           2     70889     42403 access
  2.34    0.106126           5     19689     19585 unlink
  2.04    0.092441           7     12763        73 openat
  1.75    0.079641         116       682         5 rename
  0.16    0.007208           6      1085       156 open
  0.01    0.000602           5       109           chmod
  0.01    0.000366          14        25        21 mkdir
  0.01    0.000323           4        80           getcwd
  0.01    0.000242           3        64        54 newfstatat
  0.00    0.000214          53         4           rmdir
  0.00    0.000124           8        15           chdir
  0.00    0.000123          61         2           vfork
  0.00    0.000060           2        24           faccessat2
  0.00    0.000025          12         2         2 statfs
  0.00    0.000000           0         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.538338           7    614773    213280 total
```
