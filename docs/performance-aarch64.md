# CMake executable performance

This is the original ARM prerelease measured by [native run 42859968423](https://github.com/laputa-systems/cmake-build/actions/runs/42859968423).

Target: `aarch64-unknown-linux-musl`. Runs per variant: 5.

All three binaries ran in the same native Debian container with the pinned musl toolchain.
Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource
differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with
OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those
product differences and does not isolate an individual compiler flag.
A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not
measured. Timings are not release gates.

Host: `Linux-7.0.0-1017-azure-aarch64-with-glibc2.39`. CPU: `not reported`. Container: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
CPU affinity: `[0, 1, 2, 3]`. Product archive SHA-256: `61f116c8638f56e2ec7173137ba33dac16dc43bacf54f58c496649761bbfe343`.
Official archive SHA-256: `301d5063ab259577c1b57ce5490b1aab9ea5c56dc4c822f73499553dab94925f`. Baseline output digest: `3dd3d3ec1e4511e1085f10a5120141339483691c83e04eb55991a15e68190087`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `fe0a382993c36a04a505157b59503a7294db97e2ac9923e5630f8b393b78f118`.
Tracer: `strace -- version 6.8`. Runner SHA-256: `4b853657f2beb3946e1140efab93943c0c8c6f7e8a23ee9150306d4326ff33ef`.
Benchmark implementation SHA-256: `e384a9e7bedc351819e9dd189efec0fbcaf617bb26035ba4f3bc52b4db5a68f6`.
The [initial analysis](performance-analysis.md) discusses the separate x86-64 run.

| Project | Version | Source SHA-256 |
| --- | --- | --- |
| fmt-source | 12.2.1 | `449374d74f31b67796dece454d59b93e6f1538efcce0e9ac78000c98142c139e` |
| zstd-source | 1.5.7 | `eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3` |
| libjpeg-turbo-source | 3.2.1 | `c27ad72a68da151177929aa969ae773a2da5ac2af9ce946079314fdac8cece7f` |
| llvm-project-source | 23.1.5 | `fb50b1eac93ddeb3aa8dab4cfe324dff74f4a9c2bdee6160c9e36188f8d06a6e` |

## Size

The official archive includes additional tools and resources, so total package sizes are not like-for-like.

| Variant | CMake executable bytes | Regular-file bytes | Archive bytes |
| --- | ---: | ---: | ---: |
| product | 40748528 | 53419267 | 9377384 |
| musl | 23719224 | 35341561 | not packaged |
| kitware | 18976896 | 121223111 | 52041209 |

## Measurements

RSS is the kernel-reported maximum for the process and its waited-for children, not the sum
of simultaneous process memory.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.023576 | 0.023254–0.024103 | 0.022956 | 22916 |
| fmt | cmakelists-edit | musl | 0.037693 | 0.037032–0.038534 | 0.037162 | 22916 |
| fmt | cmakelists-edit | product | 0.039330 | 0.039214–0.040466 | 0.038897 | 22916 |
| fmt | initial | kitware | 0.173142 | 0.172514–0.174505 | 0.175406 | 77340 |
| fmt | initial | musl | 0.195387 | 0.193184–0.198987 | 0.198466 | 77460 |
| fmt | initial | product | 0.199272 | 0.197924–0.200048 | 0.201020 | 77400 |
| fmt | option-change | kitware | 0.023879 | 0.023296–0.024285 | 0.023358 | 22916 |
| fmt | option-change | musl | 0.038260 | 0.038079–0.039146 | 0.037731 | 22916 |
| fmt | option-change | product | 0.039971 | 0.039598–0.040932 | 0.039320 | 22916 |
| fmt | unchanged | kitware | 0.022666 | 0.022521–0.023047 | 0.022567 | 22916 |
| fmt | unchanged | musl | 0.037372 | 0.037060–0.038734 | 0.037232 | 22916 |
| fmt | unchanged | product | 0.039541 | 0.039099–0.039990 | 0.039442 | 22916 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.091266 | 0.089448–0.093235 | 0.091393 | 77248 |
| libjpeg-turbo | cmakelists-edit | musl | 0.105657 | 0.105588–0.106560 | 0.106003 | 77312 |
| libjpeg-turbo | cmakelists-edit | product | 0.109377 | 0.107503–0.110553 | 0.108766 | 77316 |
| libjpeg-turbo | initial | kitware | 0.606363 | 0.596957–0.614043 | 0.610588 | 78436 |
| libjpeg-turbo | initial | musl | 0.635056 | 0.634066–0.641088 | 0.643095 | 78468 |
| libjpeg-turbo | initial | product | 0.644636 | 0.638198–0.651696 | 0.648579 | 78400 |
| libjpeg-turbo | option-change | kitware | 0.095553 | 0.094303–0.095946 | 0.094408 | 77248 |
| libjpeg-turbo | option-change | musl | 0.113058 | 0.112621–0.114464 | 0.113010 | 77124 |
| libjpeg-turbo | option-change | product | 0.117875 | 0.114561–0.119543 | 0.117055 | 77248 |
| libjpeg-turbo | unchanged | kitware | 0.090646 | 0.088819–0.091185 | 0.090557 | 77188 |
| libjpeg-turbo | unchanged | musl | 0.107096 | 0.104986–0.108310 | 0.105759 | 77124 |
| libjpeg-turbo | unchanged | product | 0.109602 | 0.106030–0.110498 | 0.108632 | 77316 |
| llvm-clang | cmakelists-edit | kitware | 10.973240 | 10.603724–11.354576 | 10.705105 | 506808 |
| llvm-clang | cmakelists-edit | musl | 11.716704 | 11.479480–12.073275 | 11.460866 | 477024 |
| llvm-clang | cmakelists-edit | product | 11.701554 | 11.605227–12.060713 | 11.648624 | 479460 |
| llvm-clang | initial | kitware | 16.609982 | 16.102541–17.105663 | 16.671172 | 516100 |
| llvm-clang | initial | musl | 17.494946 | 16.928865–17.828212 | 17.563755 | 487676 |
| llvm-clang | initial | product | 17.590739 | 17.369243–18.413211 | 17.661215 | 489932 |
| llvm-clang | option-change | kitware | 10.918972 | 10.767112–11.042208 | 10.741457 | 507060 |
| llvm-clang | option-change | musl | 11.489766 | 11.278450–11.695797 | 11.430605 | 476996 |
| llvm-clang | option-change | product | 11.913287 | 11.704994–12.084155 | 11.675217 | 479516 |
| llvm-clang | unchanged | kitware | 10.692153 | 10.584487–11.030163 | 10.594788 | 506944 |
| llvm-clang | unchanged | musl | 11.478695 | 11.264600–11.504553 | 11.354163 | 477100 |
| llvm-clang | unchanged | product | 11.577704 | 11.429943–12.112098 | 11.581669 | 479460 |
| process | script | kitware | 0.002132 | 0.001970–0.002200 | 0.002014 | 22660 |
| process | script | musl | 0.002089 | 0.001900–0.002156 | 0.001939 | 22660 |
| process | script | product | 0.002577 | 0.002480–0.002589 | 0.002455 | 22660 |
| process | version | kitware | 0.002000 | 0.001922–0.002113 | 0.001865 | 22660 |
| process | version | musl | 0.001875 | 0.001832–0.001981 | 0.001738 | 22660 |
| process | version | product | 0.002429 | 0.002246–0.002455 | 0.002287 | 22660 |
| zstd | cmakelists-edit | kitware | 0.035984 | 0.035389–0.036585 | 0.035174 | 22916 |
| zstd | cmakelists-edit | musl | 0.052701 | 0.049842–0.053310 | 0.051772 | 22916 |
| zstd | cmakelists-edit | product | 0.053348 | 0.052184–0.053677 | 0.052375 | 22916 |
| zstd | initial | kitware | 0.990111 | 0.968620–1.009625 | 0.995695 | 79116 |
| zstd | initial | musl | 1.036640 | 1.015544–1.044090 | 1.046825 | 79056 |
| zstd | initial | product | 1.045227 | 1.041391–1.063396 | 1.057657 | 79116 |
| zstd | option-change | kitware | 0.036719 | 0.036543–0.037120 | 0.036016 | 22916 |
| zstd | option-change | musl | 0.053988 | 0.052724–0.055106 | 0.053146 | 22916 |
| zstd | option-change | product | 0.055849 | 0.054616–0.057046 | 0.055140 | 22916 |
| zstd | unchanged | kitware | 0.035066 | 0.034381–0.035835 | 0.034895 | 22916 |
| zstd | unchanged | musl | 0.052212 | 0.051046–0.053811 | 0.052126 | 22916 |
| zstd | unchanged | product | 0.053430 | 0.052581–0.053799 | 0.053327 | 22916 |

## Raw samples

Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.002429 | 0.002287 | 22660 | 1.33 | 1.33 |
| process | script | product | 1 | 0.002518 | 0.002333 | 22660 | 1.33 | 1.33 |
| process | version | musl | 1 | 0.001852 | 0.001724 | 22660 | 1.33 | 1.33 |
| process | script | musl | 1 | 0.002089 | 0.001939 | 22660 | 1.33 | 1.33 |
| process | version | kitware | 1 | 0.002113 | 0.001994 | 22660 | 1.33 | 1.33 |
| process | script | kitware | 1 | 0.002138 | 0.002018 | 22660 | 1.33 | 1.33 |
| process | version | musl | 2 | 0.001918 | 0.001793 | 22660 | 1.33 | 1.33 |
| process | script | musl | 2 | 0.002156 | 0.002028 | 22660 | 1.33 | 1.33 |
| process | version | kitware | 2 | 0.002000 | 0.001865 | 22660 | 1.33 | 1.33 |
| process | script | kitware | 2 | 0.002056 | 0.001945 | 22660 | 1.33 | 1.33 |
| process | version | product | 2 | 0.002455 | 0.002331 | 22660 | 1.33 | 1.33 |
| process | script | product | 2 | 0.002583 | 0.002471 | 22660 | 1.33 | 1.33 |
| process | version | kitware | 3 | 0.001952 | 0.001843 | 22660 | 1.33 | 1.33 |
| process | script | kitware | 3 | 0.001970 | 0.001864 | 22660 | 1.33 | 1.33 |
| process | version | product | 3 | 0.002440 | 0.002308 | 22660 | 1.33 | 1.33 |
| process | script | product | 3 | 0.002589 | 0.002470 | 22660 | 1.33 | 1.33 |
| process | version | musl | 3 | 0.001981 | 0.001858 | 22660 | 1.33 | 1.33 |
| process | script | musl | 3 | 0.002142 | 0.002008 | 22660 | 1.33 | 1.33 |
| process | version | product | 4 | 0.002246 | 0.002125 | 22660 | 1.33 | 1.33 |
| process | script | product | 4 | 0.002480 | 0.002362 | 22660 | 1.33 | 1.33 |
| process | version | musl | 4 | 0.001832 | 0.001712 | 22660 | 1.33 | 1.33 |
| process | script | musl | 4 | 0.001900 | 0.001798 | 22660 | 1.33 | 1.33 |
| process | version | kitware | 4 | 0.002055 | 0.001938 | 22660 | 1.33 | 1.33 |
| process | script | kitware | 4 | 0.002132 | 0.002014 | 22660 | 1.33 | 1.33 |
| process | version | musl | 5 | 0.001875 | 0.001738 | 22660 | 1.33 | 1.33 |
| process | script | musl | 5 | 0.001978 | 0.001870 | 22660 | 1.33 | 1.33 |
| process | version | kitware | 5 | 0.001922 | 0.001802 | 22660 | 1.33 | 1.33 |
| process | script | kitware | 5 | 0.002200 | 0.002096 | 22660 | 1.33 | 1.33 |
| process | version | product | 5 | 0.002355 | 0.002248 | 22660 | 1.33 | 1.33 |
| process | script | product | 5 | 0.002577 | 0.002455 | 22660 | 1.33 | 1.33 |
| fmt | initial | product | 1 | 0.199600 | 0.200653 | 77016 | 1.33 | 1.33 |
| fmt | unchanged | product | 1 | 0.039541 | 0.039442 | 22660 | 1.33 | 1.33 |
| fmt | cmakelists-edit | product | 1 | 0.040466 | 0.039827 | 22660 | 1.33 | 1.33 |
| fmt | option-change | product | 1 | 0.039894 | 0.039317 | 22660 | 1.33 | 1.33 |
| fmt | initial | musl | 1 | 0.194832 | 0.197034 | 77460 | 1.33 | 1.33 |
| fmt | unchanged | musl | 1 | 0.037106 | 0.037053 | 22660 | 1.33 | 1.33 |
| fmt | cmakelists-edit | musl | 1 | 0.037032 | 0.036333 | 22788 | 1.33 | 1.33 |
| fmt | option-change | musl | 1 | 0.038095 | 0.037398 | 22788 | 1.33 | 1.33 |
| fmt | initial | kitware | 1 | 0.174505 | 0.176794 | 77340 | 1.33 | 1.33 |
| fmt | unchanged | kitware | 1 | 0.022666 | 0.022567 | 22788 | 1.33 | 1.33 |
| fmt | cmakelists-edit | kitware | 1 | 0.023379 | 0.022879 | 22916 | 1.33 | 1.33 |
| fmt | option-change | kitware | 1 | 0.023374 | 0.022872 | 22916 | 1.33 | 1.33 |
| fmt | initial | musl | 2 | 0.198987 | 0.200925 | 76928 | 1.33 | 1.33 |
| fmt | unchanged | musl | 2 | 0.038030 | 0.037949 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | musl | 2 | 0.037693 | 0.037162 | 22916 | 1.33 | 1.33 |
| fmt | option-change | musl | 2 | 0.038260 | 0.037731 | 22916 | 1.33 | 1.33 |
| fmt | initial | kitware | 2 | 0.173046 | 0.174743 | 76980 | 1.33 | 1.33 |
| fmt | unchanged | kitware | 2 | 0.022564 | 0.022455 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | kitware | 2 | 0.024103 | 0.023433 | 22916 | 1.33 | 1.33 |
| fmt | option-change | kitware | 2 | 0.023879 | 0.023437 | 22916 | 1.33 | 1.33 |
| fmt | initial | product | 2 | 0.198283 | 0.201020 | 77400 | 1.33 | 1.33 |
| fmt | unchanged | product | 2 | 0.039174 | 0.039097 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | product | 2 | 0.039314 | 0.038897 | 22916 | 1.33 | 1.33 |
| fmt | option-change | product | 2 | 0.040932 | 0.040427 | 22916 | 1.33 | 1.33 |
| fmt | initial | kitware | 3 | 0.174301 | 0.175406 | 76956 | 1.33 | 1.33 |
| fmt | unchanged | kitware | 3 | 0.022875 | 0.022753 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | kitware | 3 | 0.023254 | 0.022702 | 22916 | 1.33 | 1.33 |
| fmt | option-change | kitware | 3 | 0.023296 | 0.022772 | 22916 | 1.33 | 1.33 |
| fmt | initial | product | 3 | 0.199272 | 0.200232 | 76952 | 1.33 | 1.33 |
| fmt | unchanged | product | 3 | 0.039713 | 0.039656 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | product | 3 | 0.040281 | 0.039578 | 22916 | 1.33 | 1.33 |
| fmt | option-change | product | 3 | 0.039971 | 0.039320 | 22916 | 1.33 | 1.33 |
| fmt | initial | musl | 3 | 0.195387 | 0.198466 | 77276 | 1.33 | 1.33 |
| fmt | unchanged | musl | 3 | 0.037060 | 0.036959 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | musl | 3 | 0.037195 | 0.036732 | 22916 | 1.33 | 1.33 |
| fmt | option-change | musl | 3 | 0.038079 | 0.037617 | 22916 | 1.33 | 1.33 |
| fmt | initial | product | 4 | 0.197924 | 0.201508 | 77372 | 1.33 | 1.33 |
| fmt | unchanged | product | 4 | 0.039099 | 0.039031 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | product | 4 | 0.039330 | 0.038770 | 22916 | 1.33 | 1.33 |
| fmt | option-change | product | 4 | 0.039598 | 0.039093 | 22916 | 1.33 | 1.33 |
| fmt | initial | musl | 4 | 0.193184 | 0.196458 | 77404 | 1.33 | 1.33 |
| fmt | unchanged | musl | 4 | 0.037372 | 0.037232 | 22916 | 1.33 | 1.33 |
| fmt | cmakelists-edit | musl | 4 | 0.037766 | 0.037262 | 22916 | 1.33 | 1.33 |
| fmt | option-change | musl | 4 | 0.039146 | 0.038545 | 22916 | 1.33 | 1.30 |
| fmt | initial | kitware | 4 | 0.172514 | 0.174693 | 76760 | 1.30 | 1.30 |
| fmt | unchanged | kitware | 4 | 0.022521 | 0.022392 | 22916 | 1.30 | 1.30 |
| fmt | cmakelists-edit | kitware | 4 | 0.023576 | 0.022956 | 22916 | 1.30 | 1.30 |
| fmt | option-change | kitware | 4 | 0.023912 | 0.023358 | 22916 | 1.30 | 1.30 |
| fmt | initial | musl | 5 | 0.195798 | 0.198513 | 77404 | 1.30 | 1.30 |
| fmt | unchanged | musl | 5 | 0.038734 | 0.038407 | 22916 | 1.30 | 1.30 |
| fmt | cmakelists-edit | musl | 5 | 0.038534 | 0.038130 | 22916 | 1.30 | 1.30 |
| fmt | option-change | musl | 5 | 0.038649 | 0.038076 | 22916 | 1.30 | 1.30 |
| fmt | initial | kitware | 5 | 0.173142 | 0.175882 | 77084 | 1.30 | 1.30 |
| fmt | unchanged | kitware | 5 | 0.023047 | 0.022958 | 22916 | 1.30 | 1.30 |
| fmt | cmakelists-edit | kitware | 5 | 0.024066 | 0.023610 | 22916 | 1.30 | 1.30 |
| fmt | option-change | kitware | 5 | 0.024285 | 0.023677 | 22916 | 1.30 | 1.30 |
| fmt | initial | product | 5 | 0.200048 | 0.203071 | 77016 | 1.30 | 1.30 |
| fmt | unchanged | product | 5 | 0.039990 | 0.039908 | 22916 | 1.30 | 1.30 |
| fmt | cmakelists-edit | product | 5 | 0.039214 | 0.038640 | 22916 | 1.30 | 1.30 |
| fmt | option-change | product | 5 | 0.040290 | 0.039693 | 22916 | 1.30 | 1.30 |
| zstd | initial | product | 1 | 1.041391 | 1.053500 | 79052 | 1.34 | 1.34 |
| zstd | unchanged | product | 1 | 0.052581 | 0.052499 | 22916 | 1.34 | 1.34 |
| zstd | cmakelists-edit | product | 1 | 0.052184 | 0.051418 | 22916 | 1.34 | 1.34 |
| zstd | option-change | product | 1 | 0.054616 | 0.053906 | 22916 | 1.34 | 1.34 |
| zstd | initial | musl | 1 | 1.015544 | 1.030061 | 79056 | 1.34 | 1.34 |
| zstd | unchanged | musl | 1 | 0.051384 | 0.051238 | 22916 | 1.34 | 1.34 |
| zstd | cmakelists-edit | musl | 1 | 0.049842 | 0.049330 | 22916 | 1.34 | 1.34 |
| zstd | option-change | musl | 1 | 0.052724 | 0.051974 | 22916 | 1.34 | 1.34 |
| zstd | initial | kitware | 1 | 0.968620 | 0.976171 | 78700 | 1.34 | 1.34 |
| zstd | unchanged | kitware | 1 | 0.034381 | 0.034218 | 22916 | 1.34 | 1.39 |
| zstd | cmakelists-edit | kitware | 1 | 0.035389 | 0.034688 | 22916 | 1.39 | 1.39 |
| zstd | option-change | kitware | 1 | 0.036543 | 0.035923 | 22916 | 1.39 | 1.39 |
| zstd | initial | musl | 2 | 1.038749 | 1.046825 | 78608 | 1.39 | 1.39 |
| zstd | unchanged | musl | 2 | 0.051046 | 0.050842 | 22916 | 1.39 | 1.39 |
| zstd | cmakelists-edit | musl | 2 | 0.052905 | 0.052102 | 22916 | 1.39 | 1.39 |
| zstd | option-change | musl | 2 | 0.055106 | 0.054180 | 22916 | 1.39 | 1.39 |
| zstd | initial | kitware | 2 | 0.976236 | 0.990321 | 79052 | 1.39 | 1.39 |
| zstd | unchanged | kitware | 2 | 0.034782 | 0.034652 | 22916 | 1.39 | 1.39 |
| zstd | cmakelists-edit | kitware | 2 | 0.035984 | 0.035174 | 22916 | 1.39 | 1.39 |
| zstd | option-change | kitware | 2 | 0.036719 | 0.036132 | 22916 | 1.39 | 1.39 |
| zstd | initial | product | 2 | 1.041579 | 1.045848 | 79116 | 1.39 | 1.39 |
| zstd | unchanged | product | 2 | 0.053516 | 0.053454 | 22916 | 1.39 | 1.39 |
| zstd | cmakelists-edit | product | 2 | 0.053444 | 0.052771 | 22916 | 1.39 | 1.39 |
| zstd | option-change | product | 2 | 0.057046 | 0.055768 | 22916 | 1.39 | 1.39 |
| zstd | initial | kitware | 3 | 0.990111 | 0.995695 | 79116 | 1.39 | 1.39 |
| zstd | unchanged | kitware | 3 | 0.035066 | 0.034895 | 22916 | 1.39 | 1.39 |
| zstd | cmakelists-edit | kitware | 3 | 0.036249 | 0.035502 | 22916 | 1.39 | 1.39 |
| zstd | option-change | kitware | 3 | 0.036864 | 0.036016 | 22916 | 1.39 | 1.39 |
| zstd | initial | product | 3 | 1.045227 | 1.057657 | 78468 | 1.39 | 1.36 |
| zstd | unchanged | product | 3 | 0.053430 | 0.053327 | 22916 | 1.36 | 1.36 |
| zstd | cmakelists-edit | product | 3 | 0.053348 | 0.052375 | 22916 | 1.36 | 1.36 |
| zstd | option-change | product | 3 | 0.055433 | 0.054819 | 22916 | 1.36 | 1.36 |
| zstd | initial | musl | 3 | 1.024877 | 1.038611 | 78860 | 1.36 | 1.36 |
| zstd | unchanged | musl | 3 | 0.052632 | 0.052541 | 22916 | 1.36 | 1.36 |
| zstd | cmakelists-edit | musl | 3 | 0.053310 | 0.052610 | 22916 | 1.36 | 1.36 |
| zstd | option-change | musl | 3 | 0.052733 | 0.051935 | 22916 | 1.36 | 1.36 |
| zstd | initial | product | 4 | 1.063396 | 1.072452 | 78540 | 1.36 | 1.36 |
| zstd | unchanged | product | 4 | 0.053799 | 0.053707 | 22916 | 1.36 | 1.36 |
| zstd | cmakelists-edit | product | 4 | 0.053677 | 0.052901 | 22916 | 1.36 | 1.36 |
| zstd | option-change | product | 4 | 0.056526 | 0.055772 | 22916 | 1.36 | 1.36 |
| zstd | initial | musl | 4 | 1.036640 | 1.048463 | 78860 | 1.36 | 1.36 |
| zstd | unchanged | musl | 4 | 0.052212 | 0.052126 | 22916 | 1.36 | 1.36 |
| zstd | cmakelists-edit | musl | 4 | 0.051453 | 0.050713 | 22916 | 1.36 | 1.36 |
| zstd | option-change | musl | 4 | 0.053988 | 0.053146 | 22916 | 1.33 | 1.33 |
| zstd | initial | kitware | 4 | 1.009625 | 1.009814 | 78536 | 1.33 | 1.33 |
| zstd | unchanged | kitware | 4 | 0.035835 | 0.035738 | 22916 | 1.33 | 1.33 |
| zstd | cmakelists-edit | kitware | 4 | 0.035828 | 0.034992 | 22916 | 1.33 | 1.33 |
| zstd | option-change | kitware | 4 | 0.037120 | 0.036309 | 22916 | 1.33 | 1.33 |
| zstd | initial | musl | 5 | 1.044090 | 1.053448 | 78736 | 1.33 | 1.33 |
| zstd | unchanged | musl | 5 | 0.053811 | 0.053684 | 22916 | 1.33 | 1.33 |
| zstd | cmakelists-edit | musl | 5 | 0.052701 | 0.051772 | 22916 | 1.33 | 1.33 |
| zstd | option-change | musl | 5 | 0.054154 | 0.053180 | 22916 | 1.33 | 1.33 |
| zstd | initial | kitware | 5 | 0.994774 | 1.007468 | 78796 | 1.33 | 1.33 |
| zstd | unchanged | kitware | 5 | 0.035506 | 0.035376 | 22916 | 1.33 | 1.33 |
| zstd | cmakelists-edit | kitware | 5 | 0.036585 | 0.035753 | 22916 | 1.33 | 1.33 |
| zstd | option-change | kitware | 5 | 0.036546 | 0.035958 | 22916 | 1.33 | 1.33 |
| zstd | initial | product | 5 | 1.056720 | 1.071706 | 79052 | 1.33 | 1.33 |
| zstd | unchanged | product | 5 | 0.053314 | 0.053108 | 22916 | 1.33 | 1.33 |
| zstd | cmakelists-edit | product | 5 | 0.053056 | 0.052309 | 22916 | 1.33 | 1.33 |
| zstd | option-change | product | 5 | 0.055849 | 0.055140 | 22916 | 1.33 | 1.33 |
| libjpeg-turbo | initial | product | 1 | 0.638237 | 0.645210 | 78084 | 1.97 | 1.89 |
| libjpeg-turbo | unchanged | product | 1 | 0.106030 | 0.107012 | 76612 | 1.89 | 1.89 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.110553 | 0.109521 | 77316 | 1.89 | 1.89 |
| libjpeg-turbo | option-change | product | 1 | 0.118796 | 0.117534 | 77188 | 1.89 | 1.89 |
| libjpeg-turbo | initial | musl | 1 | 0.641088 | 0.643674 | 77892 | 1.89 | 1.89 |
| libjpeg-turbo | unchanged | musl | 1 | 0.107096 | 0.105581 | 76608 | 1.89 | 1.89 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.105687 | 0.106254 | 76964 | 1.89 | 1.89 |
| libjpeg-turbo | option-change | musl | 1 | 0.114464 | 0.114848 | 76740 | 1.89 | 1.89 |
| libjpeg-turbo | initial | kitware | 1 | 0.606363 | 0.610588 | 78436 | 1.89 | 1.89 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.088907 | 0.089868 | 76548 | 1.89 | 1.89 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.091266 | 0.090288 | 76804 | 1.89 | 1.89 |
| libjpeg-turbo | option-change | kitware | 1 | 0.095553 | 0.094520 | 77248 | 1.89 | 1.89 |
| libjpeg-turbo | initial | musl | 2 | 0.639336 | 0.646637 | 78436 | 1.89 | 1.89 |
| libjpeg-turbo | unchanged | musl | 2 | 0.104986 | 0.105759 | 76484 | 1.89 | 1.89 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.106560 | 0.105195 | 77312 | 1.89 | 1.89 |
| libjpeg-turbo | option-change | musl | 2 | 0.112621 | 0.111604 | 76804 | 1.89 | 1.89 |
| libjpeg-turbo | initial | kitware | 2 | 0.614043 | 0.615956 | 77824 | 1.89 | 1.89 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.091144 | 0.091086 | 77188 | 1.89 | 1.89 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.089448 | 0.089890 | 76804 | 1.89 | 1.89 |
| libjpeg-turbo | option-change | kitware | 2 | 0.095728 | 0.093872 | 76868 | 1.89 | 1.89 |
| libjpeg-turbo | initial | product | 2 | 0.644636 | 0.652365 | 78000 | 1.89 | 1.90 |
| libjpeg-turbo | unchanged | product | 2 | 0.110272 | 0.109683 | 77316 | 1.90 | 1.90 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.107503 | 0.107798 | 76612 | 1.90 | 1.90 |
| libjpeg-turbo | option-change | product | 2 | 0.115196 | 0.115366 | 77188 | 1.90 | 1.90 |
| libjpeg-turbo | initial | kitware | 3 | 0.610303 | 0.617326 | 78080 | 1.90 | 1.90 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.088819 | 0.089809 | 76992 | 1.90 | 1.90 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.093235 | 0.091393 | 76520 | 1.90 | 1.90 |
| libjpeg-turbo | option-change | kitware | 3 | 0.095946 | 0.094408 | 76732 | 1.90 | 1.90 |
| libjpeg-turbo | initial | product | 3 | 0.648371 | 0.648579 | 78400 | 1.90 | 1.90 |
| libjpeg-turbo | unchanged | product | 3 | 0.109602 | 0.108632 | 77124 | 1.90 | 1.90 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.109377 | 0.108766 | 76836 | 1.90 | 1.90 |
| libjpeg-turbo | option-change | product | 3 | 0.117875 | 0.117055 | 77248 | 1.90 | 1.90 |
| libjpeg-turbo | initial | musl | 3 | 0.635039 | 0.643095 | 77828 | 1.90 | 1.90 |
| libjpeg-turbo | unchanged | musl | 3 | 0.107630 | 0.106265 | 76868 | 1.90 | 1.90 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.105649 | 0.106003 | 77252 | 1.90 | 1.90 |
| libjpeg-turbo | option-change | musl | 3 | 0.113058 | 0.113496 | 76664 | 1.90 | 1.90 |
| libjpeg-turbo | initial | product | 4 | 0.638198 | 0.643595 | 78144 | 1.90 | 1.90 |
| libjpeg-turbo | unchanged | product | 4 | 0.107922 | 0.108049 | 76612 | 1.90 | 1.90 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.107920 | 0.108351 | 76740 | 1.90 | 1.83 |
| libjpeg-turbo | option-change | product | 4 | 0.119543 | 0.117466 | 77188 | 1.83 | 1.83 |
| libjpeg-turbo | initial | musl | 4 | 0.635056 | 0.641509 | 78380 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | musl | 4 | 0.108310 | 0.105740 | 77124 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.105657 | 0.106061 | 77188 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | musl | 4 | 0.112643 | 0.113010 | 76584 | 1.83 | 1.83 |
| libjpeg-turbo | initial | kitware | 4 | 0.603346 | 0.609048 | 77892 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.091185 | 0.090950 | 76864 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.091575 | 0.091884 | 77248 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | kitware | 4 | 0.095514 | 0.094025 | 76636 | 1.83 | 1.83 |
| libjpeg-turbo | initial | musl | 5 | 0.634066 | 0.635726 | 78468 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | musl | 5 | 0.106903 | 0.106191 | 76868 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.105588 | 0.105967 | 76580 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | musl | 5 | 0.114025 | 0.112629 | 77124 | 1.83 | 1.83 |
| libjpeg-turbo | initial | kitware | 5 | 0.596957 | 0.605263 | 78336 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.090646 | 0.090557 | 77188 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.091253 | 0.091664 | 76736 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | kitware | 5 | 0.094303 | 0.094536 | 76992 | 1.83 | 1.83 |
| libjpeg-turbo | initial | product | 5 | 0.651696 | 0.659815 | 77824 | 1.83 | 1.76 |
| libjpeg-turbo | unchanged | product | 5 | 0.110498 | 0.109910 | 77316 | 1.76 | 1.76 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.110488 | 0.110757 | 76868 | 1.76 | 1.76 |
| libjpeg-turbo | option-change | product | 5 | 0.114561 | 0.114809 | 77092 | 1.76 | 1.76 |
| llvm-clang | initial | product | 1 | 18.413211 | 17.929870 | 489892 | 1.58 | 1.68 |
| llvm-clang | unchanged | product | 1 | 12.112098 | 11.891984 | 479460 | 1.68 | 1.53 |
| llvm-clang | cmakelists-edit | product | 1 | 12.060713 | 11.768710 | 479220 | 1.53 | 1.44 |
| llvm-clang | option-change | product | 1 | 12.069978 | 12.009456 | 479472 | 1.35 | 1.29 |
| llvm-clang | initial | musl | 1 | 17.828212 | 17.853371 | 487600 | 1.29 | 1.34 |
| llvm-clang | unchanged | musl | 1 | 11.492330 | 11.499004 | 477100 | 1.34 | 1.27 |
| llvm-clang | cmakelists-edit | musl | 1 | 11.526951 | 11.460866 | 477008 | 1.27 | 1.23 |
| llvm-clang | option-change | musl | 1 | 11.608612 | 11.545632 | 476900 | 1.27 | 1.28 |
| llvm-clang | initial | kitware | 1 | 17.048268 | 17.099356 | 516100 | 1.28 | 1.28 |
| llvm-clang | unchanged | kitware | 1 | 10.740239 | 10.744017 | 506944 | 1.28 | 1.24 |
| llvm-clang | cmakelists-edit | kitware | 1 | 10.973240 | 10.705105 | 506804 | 1.24 | 1.25 |
| llvm-clang | option-change | kitware | 1 | 10.918972 | 10.849021 | 506936 | 1.22 | 1.26 |
| llvm-clang | initial | musl | 2 | 17.654796 | 17.710142 | 487676 | 1.26 | 1.18 |
| llvm-clang | unchanged | musl | 2 | 11.478695 | 11.485015 | 476912 | 1.18 | 1.15 |
| llvm-clang | cmakelists-edit | musl | 2 | 12.073275 | 11.775870 | 476984 | 1.15 | 1.27 |
| llvm-clang | option-change | musl | 2 | 11.489766 | 11.430605 | 476996 | 1.23 | 1.20 |
| llvm-clang | initial | kitware | 2 | 17.105663 | 17.166861 | 515912 | 1.18 | 1.21 |
| llvm-clang | unchanged | kitware | 2 | 11.030163 | 11.035579 | 506928 | 1.21 | 1.17 |
| llvm-clang | cmakelists-edit | kitware | 2 | 11.354576 | 11.036180 | 506700 | 1.17 | 1.41 |
| llvm-clang | option-change | kitware | 2 | 10.996670 | 10.910443 | 506900 | 1.34 | 1.29 |
| llvm-clang | initial | product | 2 | 17.590739 | 17.661215 | 489776 | 1.29 | 1.27 |
| llvm-clang | unchanged | product | 2 | 11.577704 | 11.581669 | 479460 | 1.27 | 1.38 |
| llvm-clang | cmakelists-edit | product | 2 | 11.605227 | 11.545484 | 479200 | 1.38 | 1.37 |
| llvm-clang | option-change | product | 2 | 11.726857 | 11.675217 | 479292 | 1.31 | 1.26 |
| llvm-clang | initial | kitware | 3 | 16.609982 | 16.671172 | 515960 | 1.24 | 1.26 |
| llvm-clang | unchanged | kitware | 3 | 10.584487 | 10.414983 | 506936 | 1.26 | 1.22 |
| llvm-clang | cmakelists-edit | kitware | 3 | 11.025090 | 10.715538 | 506808 | 1.22 | 1.19 |
| llvm-clang | option-change | kitware | 3 | 10.767112 | 10.498751 | 507060 | 1.14 | 1.12 |
| llvm-clang | initial | product | 3 | 17.369243 | 17.400130 | 489932 | 1.12 | 1.25 |
| llvm-clang | unchanged | product | 3 | 11.503735 | 11.509136 | 479460 | 1.31 | 1.34 |
| llvm-clang | cmakelists-edit | product | 3 | 11.659415 | 11.602750 | 479348 | 1.34 | 1.28 |
| llvm-clang | option-change | product | 3 | 12.084155 | 11.767138 | 479516 | 1.22 | 1.19 |
| llvm-clang | initial | musl | 3 | 17.426820 | 17.453762 | 487528 | 1.19 | 1.13 |
| llvm-clang | unchanged | musl | 3 | 11.313047 | 11.235643 | 477044 | 1.13 | 1.11 |
| llvm-clang | cmakelists-edit | musl | 3 | 11.479480 | 11.338009 | 476880 | 1.11 | 1.09 |
| llvm-clang | option-change | musl | 3 | 11.314007 | 11.264187 | 476828 | 1.14 | 1.27 |
| llvm-clang | initial | product | 4 | 17.458320 | 17.527140 | 489752 | 1.27 | 1.39 |
| llvm-clang | unchanged | product | 4 | 11.684426 | 11.690578 | 479356 | 1.39 | 1.33 |
| llvm-clang | cmakelists-edit | product | 4 | 11.701554 | 11.648624 | 479460 | 1.33 | 1.28 |
| llvm-clang | option-change | product | 4 | 11.704994 | 11.629083 | 479376 | 1.21 | 1.18 |
| llvm-clang | initial | musl | 4 | 17.494946 | 17.563755 | 487496 | 1.18 | 1.19 |
| llvm-clang | unchanged | musl | 4 | 11.264600 | 11.212141 | 476916 | 1.19 | 1.16 |
| llvm-clang | cmakelists-edit | musl | 4 | 11.880470 | 11.538138 | 476968 | 1.16 | 1.12 |
| llvm-clang | option-change | musl | 4 | 11.695797 | 11.549456 | 476760 | 1.26 | 1.22 |
| llvm-clang | initial | kitware | 4 | 16.102541 | 16.158294 | 516000 | 1.20 | 1.16 |
| llvm-clang | unchanged | kitware | 4 | 10.692153 | 10.567562 | 506812 | 1.16 | 1.13 |
| llvm-clang | cmakelists-edit | kitware | 4 | 10.737691 | 10.539966 | 506808 | 1.13 | 1.11 |
| llvm-clang | option-change | kitware | 4 | 10.829425 | 10.600060 | 506800 | 1.09 | 1.07 |
| llvm-clang | initial | musl | 5 | 16.928865 | 16.995978 | 487492 | 1.07 | 1.19 |
| llvm-clang | unchanged | musl | 5 | 11.504553 | 11.354163 | 476916 | 1.19 | 1.22 |
| llvm-clang | cmakelists-edit | musl | 5 | 11.716704 | 11.385243 | 477024 | 1.22 | 1.34 |
| llvm-clang | option-change | musl | 5 | 11.278450 | 11.223380 | 476840 | 1.29 | 1.22 |
| llvm-clang | initial | kitware | 5 | 16.165127 | 16.214773 | 515876 | 1.22 | 1.24 |
| llvm-clang | unchanged | kitware | 5 | 10.670857 | 10.594788 | 506928 | 1.24 | 1.20 |
| llvm-clang | cmakelists-edit | kitware | 5 | 10.603724 | 10.460799 | 506796 | 1.20 | 1.17 |
| llvm-clang | option-change | kitware | 5 | 11.042208 | 10.741457 | 506808 | 1.21 | 1.18 |
| llvm-clang | initial | product | 5 | 17.760798 | 17.836198 | 489864 | 1.18 | 1.13 |
| llvm-clang | unchanged | product | 5 | 11.429943 | 11.434962 | 479292 | 1.13 | 1.26 |
| llvm-clang | cmakelists-edit | product | 5 | 11.756784 | 11.702310 | 479380 | 1.26 | 1.22 |
| llvm-clang | option-change | product | 5 | 11.913287 | 11.638653 | 479492 | 1.17 | 1.15 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 19.71    0.001300         650         2           wait4
 18.73    0.001235           4       283        42 faccessat
 17.74    0.001170           4       257        14 newfstatat
 14.97    0.000987           8       110         4 openat
  7.79    0.000514          10        50        39 unlinkat
  5.38    0.000355           1       179       175 readlinkat
  5.13    0.000338         112         3           execve
  4.66    0.000307         153         2           clone
  3.43    0.000226          32         7         2 renameat
  1.46    0.000096          13         7         6 mkdirat
  0.79    0.000052           8         6           fchmodat
  0.12    0.000008           8         1           chdir
  0.11    0.000007           7         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.006595           7       908       282 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 22.53    0.001436           5       257        14 newfstatat
 21.60    0.001377           4       283        42 faccessat
 17.57    0.001120          10       110         4 openat
 11.06    0.000705         352         2           wait4
  9.30    0.000593          11        50        39 unlinkat
  6.79    0.000433          61         7         2 renameat
  5.33    0.000340         170         2           clone
  3.48    0.000222           1       179       175 readlinkat
  1.51    0.000096          13         7         6 mkdirat
  0.82    0.000052           8         6           fchmodat
  0.00    0.000000           0         1           getcwd
  0.00    0.000000           0         1           chdir
  0.00    0.000000           0         3           execve
------ ----------- ----------- --------- --------- ----------------
100.00    0.006374           7       908       282 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 31.97    0.002646        1323         2           wait4
 13.33    0.001103           4       257        14 newfstatat
 12.26    0.001015           3       284        41 faccessat
 11.82    0.000978           8       121         7 openat
 10.91    0.000903         301         3           execve
  5.69    0.000471          67         7         2 renameat
  5.12    0.000424           8        50        39 unlinkat
  4.69    0.000388         194         2           clone
  2.37    0.000196           1       179       175 readlinkat
  1.18    0.000098          14         7         6 mkdirat
  0.46    0.000038           6         6           fchmodat
  0.12    0.000010          10         1           getcwd
  0.08    0.000007           7         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.008277           8       920       284 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 23.06    0.003091           4       684       211 faccessat
 20.24    0.002714        1357         2           wait4
 19.12    0.002563           5       446        37 newfstatat
 11.73    0.001572           9       161         4 openat
  8.26    0.001107           3       369       361 readlinkat
  5.72    0.000767           8        95        85 unlinkat
  4.88    0.000654         218         3           execve
  3.42    0.000459          51         9         2 renameat
  2.50    0.000335         167         2           clone
  0.59    0.000079          11         7         6 mkdirat
  0.43    0.000058          11         5           fchmodat
  0.06    0.000008           8         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.013407           7      1785       706 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 25.40    0.003227           4       684       211 faccessat
 21.79    0.002768           6       446        37 newfstatat
 13.27    0.001686           4       369       361 readlinkat
 12.81    0.001627          10       161         4 openat
  9.56    0.001215         607         2           wait4
  6.59    0.000837           8        95        85 unlinkat
  5.16    0.000656          72         9         2 renameat
  2.12    0.000269          89         3           execve
  2.10    0.000267         133         2           clone
  0.70    0.000089          12         7         6 mkdirat
  0.49    0.000062          12         5           fchmodat
  0.00    0.000000           0         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.012703           7      1785       706 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 26.68    0.003145           4       685       210 faccessat
 19.04    0.002244        1122         2           wait4
 14.93    0.001760           3       446        37 newfstatat
 13.11    0.001545           8       172         7 openat
  6.07    0.000716           7        95        85 unlinkat
  5.62    0.000662          73         9         2 renameat
  5.28    0.000622         207         3           execve
  5.15    0.000607           1       362       354 readlinkat
  2.99    0.000352         176         2           clone
  0.46    0.000054           7         7         6 mkdirat
  0.29    0.000034           4         7           faccessat2
  0.24    0.000028           5         5           fchmodat
  0.09    0.000011          11         1           getcwd
  0.06    0.000007           7         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.011787           6      1797       701 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 72.01    0.062431        4459        14         2 wait4
  7.09    0.006147           4      1380       112 newfstatat
  6.06    0.005256           3      1632      1580 readlinkat
  3.78    0.003276           3      1040       451 faccessat
  3.67    0.003179          10       312        18 openat
  2.49    0.002158         166        13           execve
  1.78    0.001546           7       204       155 unlinkat
  1.70    0.001478          92        16           clone
  0.70    0.000606          28        21         5 renameat
  0.42    0.000367          14        25        21 mkdirat
  0.20    0.000172           6        27           fchmodat
  0.07    0.000063           9         7           chdir
  0.02    0.000016           5         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.086695          18      4694      2344 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 74.67    0.072372        5169        14         2 wait4
  6.30    0.006109           4      1380       112 newfstatat
  5.74    0.005561           3      1632      1580 readlinkat
  4.14    0.004013           3      1040       451 faccessat
  3.39    0.003284          10       312        18 openat
  1.77    0.001712           8       204       155 unlinkat
  1.77    0.001712         107        16           clone
  0.89    0.000860          66        13           execve
  0.85    0.000822          39        21         5 renameat
  0.23    0.000227           9        25        21 mkdirat
  0.19    0.000182           6        27           fchmodat
  0.05    0.000052           7         7           chdir
  0.02    0.000016           5         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.096922          20      4694      2344 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 73.46    0.081762        5840        14         2 wait4
  6.06    0.006741           4      1380       112 newfstatat
  5.35    0.005955           3      1632      1580 readlinkat
  4.21    0.004688           4      1041       450 faccessat
  3.36    0.003735          11       323        21 openat
  1.94    0.002156         165        13           execve
  1.93    0.002148          10       204       155 unlinkat
  1.80    0.002003         125        16           clone
  1.23    0.001373          65        21         5 renameat
  0.35    0.000392          56         7           chdir
  0.17    0.000190           7        27           fchmodat
  0.13    0.000143           5        25        21 mkdirat
  0.02    0.000017           5         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.111303          23      4706      2346 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 51.10    1.935478           5    358424      3525 newfstatat
 16.08    0.609016        9822        62         9 wait4
 13.37    0.506593           3    147712    145843 readlinkat
  6.39    0.241930           3     70814     42341 faccessat
  3.63    0.137587        2697        51           execve
  2.84    0.107442        1884        57           clone
  2.58    0.097626           7     13815       219 openat
  2.35    0.088870           4     19693     19585 unlinkat
  1.63    0.061925          90       682         5 renameat
  0.02    0.000773           7       109           fchmodat
  0.01    0.000250           3        80           getcwd
  0.00    0.000189           7        25        21 mkdirat
  0.00    0.000121           8        15           chdir
  0.00    0.000022          11         2         2 statfs
  0.00    0.000005           1         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    3.787827           6    611546    211550 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 50.23    1.953478           5    358424      3525 newfstatat
 16.13    0.627300       10117        62         9 wait4
 12.82    0.498443           3    147712    145843 readlinkat
  6.39    0.248468           3     70814     42341 faccessat
  3.98    0.154910        3037        51           execve
  3.28    0.127446        2235        57           clone
  2.74    0.106617           7     13815       219 openat
  2.48    0.096630           4     19693     19585 unlinkat
  1.91    0.074118         108       682         5 renameat
  0.02    0.000824           7       109           fchmodat
  0.01    0.000380           4        80           getcwd
  0.01    0.000327          13        25        21 mkdirat
  0.00    0.000100           6        15           chdir
  0.00    0.000042           8         5           utimensat
  0.00    0.000022          11         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    3.889105           6    611546    211550 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 51.70    2.038334           5    358424      3525 newfstatat
 16.21    0.639142       10308        62         9 wait4
 12.18    0.480103           3    147688    145819 readlinkat
  6.13    0.241843           3     70817     42338 faccessat
  3.99    0.157431        3086        51           execve
  2.97    0.117237        2056        57           clone
  2.76    0.108915           7     13848       228 openat
  2.33    0.092034           4     19693     19585 unlinkat
  1.68    0.066136          96       682         5 renameat
  0.02    0.000895           8       109           fchmodat
  0.01    0.000431           5        80           getcwd
  0.01    0.000275          11        25        21 mkdirat
  0.00    0.000119           7        15           chdir
  0.00    0.000048           2        24           faccessat2
  0.00    0.000017           3         5           utimensat
  0.00    0.000000           0         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    3.942960           6    611582    211532 total
```
