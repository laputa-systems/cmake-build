# CMake executable performance

Target: `x86_64-unknown-linux-musl`. Runs per variant: 5.

All three binaries ran in the same native Debian container with the pinned musl toolchain.
Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource
differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with
OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those
product differences and does not isolate an individual compiler flag.
A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not
measured. Timings are not release gates.

Host: `Linux-7.0.0-1017-azure-x86_64-with-glibc2.39`. CPU: `AMD EPYC 9V45 96-Core Processor`. Container: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
CPU affinity: `[0, 1, 2, 3]`. Product archive SHA-256: `cbab9ea823b0e1b609b7b3b273e6a9a8c89d3bfdb7aa382d380f880bf7f78e7c`.
Official archive SHA-256: `ed85135c5a5135b45e50423cb406dea04ca3338da0b8ef3c9ede963559680be0`. Baseline output digest: `a8944b410bafcac98e1648fe38fb3da440844b454601c9b3d9784a63a65e1eed`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `c43f18f143cc17f49814b6c5dda8a1122d17b6bcdff9848b6f77e97b33026dfe`.
Tracer: `strace -- version 6.8`. Runner SHA-256: `f72a566ff6b678eaea8964ab0956e069201176cde3f0c61a008eb187a3f46e4b`.
Benchmark implementation SHA-256: `b8fec53c7c563475d6ef676783d394c85a71160f7bc75c2f0b8985cad4362bff`.
RSS measurement implementation SHA-256: `59a101c92ad845d9d454cd03089291ef8803bea02a1a8e0e3450672c37d8e4de`.
See the [baseline analysis](performance-analysis.md) for the interpretation and limits of the initial run.

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
| product | 27627504 | 40298196 | 8125188 |
| musl | 24404144 | 36026480 | not packaged |
| kitware | 21469504 | 190375166 | 64865573 |

## Measurements

RSS is CMake's image high-water mark, read before exit; it excludes child processes.
Configure timings include process-tracing overhead. Startup timings are untraced; their RSS
comes from a separate traced invocation. CPU time includes waited child processes.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.021703 | 0.019975–0.027626 | 0.019645 | 14928 |
| fmt | cmakelists-edit | musl | 0.040485 | 0.038926–0.041067 | 0.038274 | 13840 |
| fmt | cmakelists-edit | product | 0.041877 | 0.038260–0.043464 | 0.039531 | 12824 |
| fmt | initial | kitware | 0.169296 | 0.159628–0.174573 | 0.168981 | 16880 |
| fmt | initial | musl | 0.200503 | 0.196501–0.203061 | 0.202338 | 15564 |
| fmt | initial | product | 0.201353 | 0.189659–0.203414 | 0.203124 | 14616 |
| fmt | option-change | kitware | 0.022140 | 0.019939–0.023174 | 0.020066 | 14924 |
| fmt | option-change | musl | 0.040676 | 0.039522–0.042201 | 0.038388 | 13840 |
| fmt | option-change | product | 0.041450 | 0.040633–0.042208 | 0.039288 | 12824 |
| fmt | unchanged | kitware | 0.021269 | 0.020258–0.022436 | 0.019864 | 14856 |
| fmt | unchanged | musl | 0.040290 | 0.038660–0.043915 | 0.038853 | 13840 |
| fmt | unchanged | product | 0.041585 | 0.040852–0.042965 | 0.040162 | 12824 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.086763 | 0.080850–0.087878 | 0.083598 | 16456 |
| libjpeg-turbo | cmakelists-edit | musl | 0.111244 | 0.108524–0.115932 | 0.107638 | 15204 |
| libjpeg-turbo | cmakelists-edit | product | 0.108352 | 0.106279–0.111832 | 0.106779 | 14452 |
| libjpeg-turbo | initial | kitware | 0.592599 | 0.589481–0.619019 | 0.592689 | 17944 |
| libjpeg-turbo | initial | musl | 0.636136 | 0.627769–0.653032 | 0.639503 | 16844 |
| libjpeg-turbo | initial | product | 0.641290 | 0.623317–0.671774 | 0.642503 | 16260 |
| libjpeg-turbo | option-change | kitware | 0.088085 | 0.086663–0.094105 | 0.085640 | 16464 |
| libjpeg-turbo | option-change | musl | 0.116216 | 0.111017–0.119261 | 0.112930 | 15204 |
| libjpeg-turbo | option-change | product | 0.115981 | 0.113140–0.117609 | 0.113348 | 14504 |
| libjpeg-turbo | unchanged | kitware | 0.085400 | 0.083194–0.086508 | 0.083601 | 16420 |
| libjpeg-turbo | unchanged | musl | 0.108841 | 0.104691–0.111508 | 0.107615 | 15248 |
| libjpeg-turbo | unchanged | product | 0.107599 | 0.104912–0.108961 | 0.105732 | 14448 |
| llvm-clang | cmakelists-edit | kitware | 8.610212 | 8.427804–9.377170 | 8.267454 | 379292 |
| llvm-clang | cmakelists-edit | musl | 11.017820 | 10.826925–12.113846 | 10.444940 | 478664 |
| llvm-clang | cmakelists-edit | product | 11.105454 | 10.721940–12.063118 | 10.513529 | 478696 |
| llvm-clang | initial | kitware | 14.508999 | 13.784785–14.732250 | 14.494628 | 388620 |
| llvm-clang | initial | musl | 16.624149 | 16.392066–18.468791 | 16.579651 | 489292 |
| llvm-clang | initial | product | 16.117232 | 15.803985–18.979766 | 16.144875 | 489252 |
| llvm-clang | option-change | kitware | 8.561455 | 8.328965–8.664874 | 8.204551 | 379300 |
| llvm-clang | option-change | musl | 10.994782 | 10.820375–12.101223 | 10.602536 | 478652 |
| llvm-clang | option-change | product | 10.634232 | 10.539950–12.025624 | 10.251705 | 478600 |
| llvm-clang | unchanged | kitware | 8.385663 | 8.225896–9.027473 | 8.215787 | 379268 |
| llvm-clang | unchanged | musl | 10.853879 | 10.711402–11.957631 | 10.551826 | 478764 |
| llvm-clang | unchanged | product | 10.764011 | 10.485165–12.253106 | 10.489829 | 478620 |
| process | script | kitware | 0.001805 | 0.001790–0.001846 | 0.001519 | 10840 |
| process | script | musl | 0.001734 | 0.001679–0.004855 | 0.001421 | 11080 |
| process | script | product | 0.001855 | 0.001831–0.001886 | 0.001584 | 9932 |
| process | version | kitware | 0.001655 | 0.001594–0.001693 | 0.001374 | 10148 |
| process | version | musl | 0.001577 | 0.001553–0.001599 | 0.001300 | 10960 |
| process | version | product | 0.001775 | 0.001730–0.001784 | 0.001478 | 9884 |
| zstd | cmakelists-edit | kitware | 0.033249 | 0.029954–0.062915 | 0.029409 | 15512 |
| zstd | cmakelists-edit | musl | 0.052923 | 0.050699–0.057609 | 0.050519 | 14444 |
| zstd | cmakelists-edit | product | 0.052439 | 0.051079–0.053590 | 0.049807 | 13664 |
| zstd | initial | kitware | 0.954302 | 0.931601–1.021334 | 0.951144 | 18724 |
| zstd | initial | musl | 1.016077 | 0.972572–1.057101 | 1.023066 | 17680 |
| zstd | initial | product | 1.020376 | 0.983286–1.061995 | 1.024035 | 16876 |
| zstd | option-change | kitware | 0.032966 | 0.031575–0.034541 | 0.030392 | 15604 |
| zstd | option-change | musl | 0.054834 | 0.052621–0.058348 | 0.052038 | 14444 |
| zstd | option-change | product | 0.054180 | 0.050863–0.061011 | 0.051698 | 13668 |
| zstd | unchanged | kitware | 0.031152 | 0.030096–0.032196 | 0.029714 | 15508 |
| zstd | unchanged | musl | 0.052679 | 0.050578–0.054723 | 0.051067 | 14444 |
| zstd | unchanged | product | 0.053261 | 0.051741–0.056405 | 0.051620 | 13664 |

## Raw samples

Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.001774 | 0.001453 | 9884 | 1.22 | 1.22 |
| process | script | product | 1 | 0.001863 | 0.001561 | 9932 | 1.22 | 1.22 |
| process | version | musl | 1 | 0.001599 | 0.001308 | 10960 | 1.22 | 1.22 |
| process | script | musl | 1 | 0.001742 | 0.001421 | 11080 | 1.22 | 1.22 |
| process | version | kitware | 1 | 0.001664 | 0.001376 | 10068 | 1.22 | 1.22 |
| process | script | kitware | 1 | 0.001790 | 0.001518 | 10732 | 1.22 | 1.22 |
| process | version | musl | 2 | 0.001565 | 0.001261 | 10960 | 1.22 | 1.22 |
| process | script | musl | 2 | 0.001679 | 0.001406 | 11080 | 1.22 | 1.22 |
| process | version | kitware | 2 | 0.001655 | 0.001374 | 10088 | 1.22 | 1.22 |
| process | script | kitware | 2 | 0.001846 | 0.001519 | 10744 | 1.22 | 1.22 |
| process | version | product | 2 | 0.001777 | 0.001488 | 9884 | 1.22 | 1.22 |
| process | script | product | 2 | 0.001886 | 0.001584 | 9932 | 1.22 | 1.22 |
| process | version | kitware | 3 | 0.001639 | 0.001359 | 10120 | 1.22 | 1.22 |
| process | script | kitware | 3 | 0.001814 | 0.001533 | 10840 | 1.22 | 1.22 |
| process | version | product | 3 | 0.001730 | 0.001460 | 9884 | 1.22 | 1.22 |
| process | script | product | 3 | 0.001846 | 0.001585 | 9932 | 1.22 | 1.22 |
| process | version | musl | 3 | 0.001577 | 0.001305 | 10960 | 1.22 | 1.22 |
| process | script | musl | 3 | 0.001734 | 0.001460 | 11080 | 1.22 | 1.22 |
| process | version | product | 4 | 0.001775 | 0.001493 | 9884 | 1.22 | 1.22 |
| process | script | product | 4 | 0.001855 | 0.001588 | 9932 | 1.22 | 1.22 |
| process | version | musl | 4 | 0.001584 | 0.001300 | 10960 | 1.22 | 1.22 |
| process | script | musl | 4 | 0.004855 | 0.001455 | 11080 | 1.22 | 1.22 |
| process | version | kitware | 4 | 0.001693 | 0.001403 | 10148 | 1.22 | 1.22 |
| process | script | kitware | 4 | 0.001805 | 0.001511 | 10736 | 1.22 | 1.22 |
| process | version | musl | 5 | 0.001553 | 0.001290 | 10960 | 1.22 | 1.22 |
| process | script | musl | 5 | 0.001687 | 0.001400 | 11080 | 1.22 | 1.22 |
| process | version | kitware | 5 | 0.001594 | 0.001334 | 10112 | 1.22 | 1.22 |
| process | script | kitware | 5 | 0.001791 | 0.001528 | 10768 | 1.22 | 1.22 |
| process | version | product | 5 | 0.001784 | 0.001478 | 9884 | 1.22 | 1.22 |
| process | script | product | 5 | 0.001831 | 0.001561 | 9932 | 1.22 | 1.22 |
| fmt | initial | product | 1 | 0.189659 | 0.189647 | 14588 | 1.22 | 1.22 |
| fmt | unchanged | product | 1 | 0.040909 | 0.037558 | 12824 | 1.22 | 1.22 |
| fmt | cmakelists-edit | product | 1 | 0.038260 | 0.036563 | 12824 | 1.22 | 1.22 |
| fmt | option-change | product | 1 | 0.040633 | 0.038640 | 12824 | 1.22 | 1.22 |
| fmt | initial | musl | 1 | 0.200147 | 0.198251 | 15504 | 1.22 | 1.22 |
| fmt | unchanged | musl | 1 | 0.038660 | 0.037328 | 13840 | 1.22 | 1.22 |
| fmt | cmakelists-edit | musl | 1 | 0.038926 | 0.037141 | 13836 | 1.22 | 1.22 |
| fmt | option-change | musl | 1 | 0.039522 | 0.037677 | 13836 | 1.22 | 1.22 |
| fmt | initial | kitware | 1 | 0.159628 | 0.159594 | 16804 | 1.22 | 1.22 |
| fmt | unchanged | kitware | 1 | 0.020258 | 0.018805 | 14832 | 1.22 | 1.22 |
| fmt | cmakelists-edit | kitware | 1 | 0.019975 | 0.018130 | 14812 | 1.22 | 1.22 |
| fmt | option-change | kitware | 1 | 0.019939 | 0.018173 | 14808 | 1.22 | 1.22 |
| fmt | initial | musl | 2 | 0.196501 | 0.196562 | 15476 | 1.22 | 1.20 |
| fmt | unchanged | musl | 2 | 0.039330 | 0.037934 | 13840 | 1.20 | 1.20 |
| fmt | cmakelists-edit | musl | 2 | 0.039253 | 0.037415 | 13836 | 1.20 | 1.20 |
| fmt | option-change | musl | 2 | 0.039979 | 0.037933 | 13836 | 1.20 | 1.20 |
| fmt | initial | kitware | 2 | 0.174573 | 0.173400 | 16756 | 1.20 | 1.20 |
| fmt | unchanged | kitware | 2 | 0.022436 | 0.020852 | 14856 | 1.20 | 1.20 |
| fmt | cmakelists-edit | kitware | 2 | 0.023637 | 0.020566 | 14824 | 1.20 | 1.20 |
| fmt | option-change | kitware | 2 | 0.022752 | 0.020643 | 14856 | 1.20 | 1.20 |
| fmt | initial | product | 2 | 0.202404 | 0.203124 | 14612 | 1.20 | 1.20 |
| fmt | unchanged | product | 2 | 0.041585 | 0.040162 | 12824 | 1.20 | 1.20 |
| fmt | cmakelists-edit | product | 2 | 0.043464 | 0.041326 | 12824 | 1.20 | 1.20 |
| fmt | option-change | product | 2 | 0.042208 | 0.039994 | 12824 | 1.20 | 1.20 |
| fmt | initial | kitware | 3 | 0.169296 | 0.168981 | 16880 | 1.20 | 1.20 |
| fmt | unchanged | kitware | 3 | 0.021269 | 0.019864 | 14812 | 1.20 | 1.20 |
| fmt | cmakelists-edit | kitware | 3 | 0.021244 | 0.019384 | 14884 | 1.20 | 1.20 |
| fmt | option-change | kitware | 3 | 0.022140 | 0.020066 | 14784 | 1.20 | 1.20 |
| fmt | initial | product | 3 | 0.203414 | 0.203680 | 14608 | 1.20 | 1.20 |
| fmt | unchanged | product | 3 | 0.042965 | 0.041479 | 12824 | 1.20 | 1.20 |
| fmt | cmakelists-edit | product | 3 | 0.042547 | 0.040427 | 12824 | 1.20 | 1.20 |
| fmt | option-change | product | 3 | 0.041762 | 0.039639 | 12824 | 1.20 | 1.20 |
| fmt | initial | musl | 3 | 0.200503 | 0.202338 | 15436 | 1.20 | 1.20 |
| fmt | unchanged | musl | 3 | 0.043915 | 0.040049 | 13840 | 1.20 | 1.20 |
| fmt | cmakelists-edit | musl | 3 | 0.040906 | 0.038909 | 13840 | 1.20 | 1.20 |
| fmt | option-change | musl | 3 | 0.041269 | 0.039115 | 13840 | 1.20 | 1.20 |
| fmt | initial | product | 4 | 0.201004 | 0.199934 | 14616 | 1.20 | 1.20 |
| fmt | unchanged | product | 4 | 0.040852 | 0.039436 | 12824 | 1.20 | 1.20 |
| fmt | cmakelists-edit | product | 4 | 0.041423 | 0.039245 | 12824 | 1.20 | 1.20 |
| fmt | option-change | product | 4 | 0.041450 | 0.039288 | 12824 | 1.20 | 1.20 |
| fmt | initial | musl | 4 | 0.203061 | 0.203068 | 15564 | 1.20 | 1.20 |
| fmt | unchanged | musl | 4 | 0.040290 | 0.038853 | 13840 | 1.20 | 1.20 |
| fmt | cmakelists-edit | musl | 4 | 0.040485 | 0.038274 | 13836 | 1.20 | 1.20 |
| fmt | option-change | musl | 4 | 0.042201 | 0.040041 | 13836 | 1.20 | 1.20 |
| fmt | initial | kitware | 4 | 0.167524 | 0.165595 | 16784 | 1.20 | 1.20 |
| fmt | unchanged | kitware | 4 | 0.022144 | 0.020598 | 14816 | 1.20 | 1.20 |
| fmt | cmakelists-edit | kitware | 4 | 0.027626 | 0.019737 | 14928 | 1.20 | 1.20 |
| fmt | option-change | kitware | 4 | 0.023174 | 0.021178 | 14924 | 1.20 | 1.20 |
| fmt | initial | musl | 5 | 0.200532 | 0.202340 | 15520 | 1.20 | 1.20 |
| fmt | unchanged | musl | 5 | 0.041043 | 0.039598 | 13836 | 1.20 | 1.20 |
| fmt | cmakelists-edit | musl | 5 | 0.041067 | 0.038906 | 13836 | 1.20 | 1.20 |
| fmt | option-change | musl | 5 | 0.040676 | 0.038388 | 13836 | 1.20 | 1.20 |
| fmt | initial | kitware | 5 | 0.169821 | 0.168983 | 16748 | 1.20 | 1.20 |
| fmt | unchanged | kitware | 5 | 0.020889 | 0.019487 | 14816 | 1.20 | 1.20 |
| fmt | cmakelists-edit | kitware | 5 | 0.021703 | 0.019645 | 14828 | 1.20 | 1.20 |
| fmt | option-change | kitware | 5 | 0.021294 | 0.019158 | 14840 | 1.20 | 1.20 |
| fmt | initial | product | 5 | 0.201353 | 0.203689 | 14592 | 1.20 | 1.20 |
| fmt | unchanged | product | 5 | 0.042753 | 0.041225 | 12824 | 1.20 | 1.20 |
| fmt | cmakelists-edit | product | 5 | 0.041877 | 0.039531 | 12824 | 1.20 | 1.20 |
| fmt | option-change | product | 5 | 0.041390 | 0.039280 | 12824 | 1.20 | 1.20 |
| zstd | initial | product | 1 | 1.020376 | 1.024035 | 16700 | 1.25 | 1.25 |
| zstd | unchanged | product | 1 | 0.052655 | 0.051285 | 13660 | 1.25 | 1.25 |
| zstd | cmakelists-edit | product | 1 | 0.052439 | 0.050335 | 13664 | 1.25 | 1.25 |
| zstd | option-change | product | 1 | 0.056126 | 0.053863 | 13668 | 1.25 | 1.25 |
| zstd | initial | musl | 1 | 1.016077 | 1.026031 | 17680 | 1.25 | 1.25 |
| zstd | unchanged | musl | 1 | 0.054723 | 0.053210 | 14444 | 1.25 | 1.25 |
| zstd | cmakelists-edit | musl | 1 | 0.052818 | 0.050519 | 14440 | 1.25 | 1.25 |
| zstd | option-change | musl | 1 | 0.054441 | 0.052038 | 14444 | 1.25 | 1.25 |
| zstd | initial | kitware | 1 | 1.021334 | 1.017246 | 18704 | 1.25 | 1.23 |
| zstd | unchanged | kitware | 1 | 0.031152 | 0.029714 | 15496 | 1.23 | 1.23 |
| zstd | cmakelists-edit | kitware | 1 | 0.032023 | 0.029409 | 15440 | 1.23 | 1.23 |
| zstd | option-change | kitware | 1 | 0.032966 | 0.030392 | 15524 | 1.23 | 1.23 |
| zstd | initial | musl | 2 | 1.016756 | 1.023066 | 17380 | 1.23 | 1.23 |
| zstd | unchanged | musl | 2 | 0.051915 | 0.050504 | 14444 | 1.23 | 1.23 |
| zstd | cmakelists-edit | musl | 2 | 0.056291 | 0.049830 | 14440 | 1.23 | 1.23 |
| zstd | option-change | musl | 2 | 0.054834 | 0.052369 | 14440 | 1.23 | 1.23 |
| zstd | initial | kitware | 2 | 0.942014 | 0.946492 | 18668 | 1.23 | 1.23 |
| zstd | unchanged | kitware | 2 | 0.030367 | 0.028960 | 15484 | 1.23 | 1.23 |
| zstd | cmakelists-edit | kitware | 2 | 0.033249 | 0.029302 | 15492 | 1.23 | 1.23 |
| zstd | option-change | kitware | 2 | 0.034343 | 0.031919 | 15512 | 1.23 | 1.23 |
| zstd | initial | product | 2 | 1.011667 | 1.019344 | 16576 | 1.23 | 1.23 |
| zstd | unchanged | product | 2 | 0.051741 | 0.050270 | 13664 | 1.23 | 1.23 |
| zstd | cmakelists-edit | product | 2 | 0.051987 | 0.049668 | 13664 | 1.23 | 1.23 |
| zstd | option-change | product | 2 | 0.061011 | 0.053676 | 13664 | 1.23 | 1.23 |
| zstd | initial | kitware | 3 | 0.982873 | 0.985959 | 18688 | 1.23 | 1.29 |
| zstd | unchanged | kitware | 3 | 0.030096 | 0.028615 | 15496 | 1.29 | 1.29 |
| zstd | cmakelists-edit | kitware | 3 | 0.029954 | 0.027821 | 15448 | 1.29 | 1.29 |
| zstd | option-change | kitware | 3 | 0.031575 | 0.029343 | 15524 | 1.29 | 1.29 |
| zstd | initial | product | 3 | 0.983286 | 0.978611 | 16764 | 1.29 | 1.29 |
| zstd | unchanged | product | 3 | 0.053922 | 0.052338 | 13620 | 1.29 | 1.29 |
| zstd | cmakelists-edit | product | 3 | 0.052441 | 0.049807 | 13616 | 1.29 | 1.29 |
| zstd | option-change | product | 3 | 0.050863 | 0.048536 | 13664 | 1.29 | 1.29 |
| zstd | initial | musl | 3 | 0.972572 | 0.977276 | 17524 | 1.29 | 1.29 |
| zstd | unchanged | musl | 3 | 0.050578 | 0.049061 | 14444 | 1.29 | 1.29 |
| zstd | cmakelists-edit | musl | 3 | 0.050699 | 0.048519 | 14436 | 1.29 | 1.29 |
| zstd | option-change | musl | 3 | 0.058348 | 0.051573 | 14192 | 1.29 | 1.29 |
| zstd | initial | product | 4 | 1.061995 | 1.050569 | 16876 | 1.29 | 1.29 |
| zstd | unchanged | product | 4 | 0.056405 | 0.055053 | 13616 | 1.29 | 1.29 |
| zstd | cmakelists-edit | product | 4 | 0.051079 | 0.048761 | 13664 | 1.29 | 1.29 |
| zstd | option-change | product | 4 | 0.051887 | 0.049625 | 13664 | 1.29 | 1.29 |
| zstd | initial | musl | 4 | 1.057101 | 1.072247 | 17624 | 1.29 | 1.43 |
| zstd | unchanged | musl | 4 | 0.054406 | 0.052726 | 14440 | 1.43 | 1.43 |
| zstd | cmakelists-edit | musl | 4 | 0.057609 | 0.051994 | 14444 | 1.43 | 1.43 |
| zstd | option-change | musl | 4 | 0.056151 | 0.053458 | 14440 | 1.43 | 1.43 |
| zstd | initial | kitware | 4 | 0.931601 | 0.941218 | 18716 | 1.43 | 1.43 |
| zstd | unchanged | kitware | 4 | 0.032196 | 0.030635 | 15500 | 1.43 | 1.43 |
| zstd | cmakelists-edit | kitware | 4 | 0.037108 | 0.030768 | 15512 | 1.43 | 1.43 |
| zstd | option-change | kitware | 4 | 0.034541 | 0.032113 | 15496 | 1.43 | 1.43 |
| zstd | initial | musl | 5 | 1.009683 | 1.019758 | 17452 | 1.43 | 1.43 |
| zstd | unchanged | musl | 5 | 0.052679 | 0.051067 | 14316 | 1.43 | 1.43 |
| zstd | cmakelists-edit | musl | 5 | 0.052923 | 0.050640 | 14440 | 1.43 | 1.43 |
| zstd | option-change | musl | 5 | 0.052621 | 0.050214 | 14440 | 1.43 | 1.43 |
| zstd | initial | kitware | 5 | 0.954302 | 0.951144 | 18724 | 1.43 | 1.43 |
| zstd | unchanged | kitware | 5 | 0.032087 | 0.030564 | 15508 | 1.43 | 1.43 |
| zstd | cmakelists-edit | kitware | 5 | 0.062915 | 0.032217 | 15440 | 1.43 | 1.43 |
| zstd | option-change | kitware | 5 | 0.032269 | 0.029949 | 15604 | 1.43 | 1.43 |
| zstd | initial | product | 5 | 1.037341 | 1.039363 | 16684 | 1.43 | 1.47 |
| zstd | unchanged | product | 5 | 0.053261 | 0.051620 | 13664 | 1.47 | 1.47 |
| zstd | cmakelists-edit | product | 5 | 0.053590 | 0.051113 | 13620 | 1.47 | 1.47 |
| zstd | option-change | product | 5 | 0.054180 | 0.051698 | 13668 | 1.47 | 1.47 |
| libjpeg-turbo | initial | product | 1 | 0.641290 | 0.642503 | 16112 | 2.10 | 2.10 |
| libjpeg-turbo | unchanged | product | 1 | 0.108961 | 0.107759 | 14448 | 2.10 | 2.10 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.108291 | 0.106445 | 14452 | 2.10 | 2.10 |
| libjpeg-turbo | option-change | product | 1 | 0.117609 | 0.113348 | 14364 | 2.10 | 2.10 |
| libjpeg-turbo | initial | musl | 1 | 0.644115 | 0.648538 | 16836 | 2.10 | 1.93 |
| libjpeg-turbo | unchanged | musl | 1 | 0.111508 | 0.110811 | 15248 | 1.93 | 1.93 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.115932 | 0.113001 | 15204 | 1.93 | 1.93 |
| libjpeg-turbo | option-change | musl | 1 | 0.119261 | 0.117588 | 15204 | 1.93 | 1.93 |
| libjpeg-turbo | initial | kitware | 1 | 0.592599 | 0.589529 | 17936 | 1.93 | 1.93 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.085400 | 0.083601 | 16420 | 1.93 | 1.93 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.086763 | 0.084870 | 16408 | 1.93 | 1.93 |
| libjpeg-turbo | option-change | kitware | 1 | 0.087448 | 0.085640 | 16388 | 1.93 | 1.93 |
| libjpeg-turbo | initial | musl | 2 | 0.636136 | 0.637106 | 16712 | 1.93 | 1.93 |
| libjpeg-turbo | unchanged | musl | 2 | 0.108841 | 0.108179 | 15056 | 1.93 | 1.93 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.111614 | 0.108108 | 15120 | 1.93 | 1.93 |
| libjpeg-turbo | option-change | musl | 2 | 0.116217 | 0.112930 | 15132 | 1.93 | 1.93 |
| libjpeg-turbo | initial | kitware | 2 | 0.591543 | 0.584513 | 17928 | 1.93 | 1.93 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.085798 | 0.085287 | 16380 | 1.93 | 1.93 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.087698 | 0.082888 | 16384 | 1.93 | 1.93 |
| libjpeg-turbo | option-change | kitware | 2 | 0.088085 | 0.085498 | 16392 | 1.93 | 1.93 |
| libjpeg-turbo | initial | product | 2 | 0.623317 | 0.629777 | 15864 | 1.93 | 1.93 |
| libjpeg-turbo | unchanged | product | 2 | 0.107599 | 0.105732 | 14332 | 1.93 | 1.93 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.108352 | 0.106779 | 14332 | 1.93 | 1.93 |
| libjpeg-turbo | option-change | product | 2 | 0.115956 | 0.113423 | 14504 | 1.86 | 1.86 |
| libjpeg-turbo | initial | kitware | 3 | 0.589481 | 0.592689 | 17912 | 1.86 | 1.86 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.083194 | 0.082412 | 16408 | 1.86 | 1.86 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.085339 | 0.083598 | 16456 | 1.86 | 1.86 |
| libjpeg-turbo | option-change | kitware | 3 | 0.086663 | 0.084777 | 16396 | 1.86 | 1.86 |
| libjpeg-turbo | initial | product | 3 | 0.671774 | 0.666289 | 16124 | 1.86 | 1.86 |
| libjpeg-turbo | unchanged | product | 3 | 0.108915 | 0.105270 | 14336 | 1.86 | 1.86 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.109790 | 0.107148 | 14336 | 1.86 | 1.86 |
| libjpeg-turbo | option-change | product | 3 | 0.113140 | 0.111256 | 14504 | 1.86 | 1.86 |
| libjpeg-turbo | initial | musl | 3 | 0.627769 | 0.626724 | 16844 | 1.86 | 1.86 |
| libjpeg-turbo | unchanged | musl | 3 | 0.104691 | 0.103981 | 15248 | 1.86 | 1.86 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.110298 | 0.105609 | 15204 | 1.86 | 1.86 |
| libjpeg-turbo | option-change | musl | 3 | 0.116216 | 0.111338 | 15076 | 1.86 | 1.86 |
| libjpeg-turbo | initial | product | 4 | 0.624712 | 0.621014 | 16028 | 1.86 | 1.86 |
| libjpeg-turbo | unchanged | product | 4 | 0.104912 | 0.103356 | 14332 | 1.86 | 1.86 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.111832 | 0.107372 | 14332 | 1.86 | 1.86 |
| libjpeg-turbo | option-change | product | 4 | 0.116084 | 0.110814 | 14460 | 1.86 | 1.86 |
| libjpeg-turbo | initial | musl | 4 | 0.653032 | 0.650554 | 16780 | 1.86 | 1.87 |
| libjpeg-turbo | unchanged | musl | 4 | 0.109124 | 0.107615 | 15200 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.111244 | 0.107638 | 15120 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | musl | 4 | 0.116025 | 0.113588 | 15124 | 1.87 | 1.87 |
| libjpeg-turbo | initial | kitware | 4 | 0.593214 | 0.597035 | 17912 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.086508 | 0.085787 | 16380 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.087878 | 0.085429 | 16408 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | kitware | 4 | 0.094105 | 0.090269 | 16412 | 1.87 | 1.87 |
| libjpeg-turbo | initial | musl | 5 | 0.635756 | 0.639503 | 16712 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | musl | 5 | 0.108605 | 0.107602 | 15200 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.108524 | 0.105407 | 15204 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | musl | 5 | 0.111017 | 0.108066 | 15204 | 1.87 | 1.87 |
| libjpeg-turbo | initial | kitware | 5 | 0.619019 | 0.620800 | 17944 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.083622 | 0.081567 | 16412 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.080850 | 0.079008 | 16396 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | kitware | 5 | 0.089467 | 0.086940 | 16464 | 1.87 | 1.87 |
| libjpeg-turbo | initial | product | 5 | 0.665648 | 0.663289 | 16260 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | product | 5 | 0.107111 | 0.106313 | 14328 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.106279 | 0.103706 | 14332 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | product | 5 | 0.115981 | 0.113581 | 14312 | 1.87 | 1.87 |
| llvm-clang | initial | product | 1 | 18.979766 | 18.402800 | 489096 | 1.76 | 1.67 |
| llvm-clang | unchanged | product | 1 | 12.253106 | 11.512736 | 478600 | 1.67 | 1.52 |
| llvm-clang | cmakelists-edit | product | 1 | 12.063118 | 11.605962 | 478568 | 1.52 | 1.44 |
| llvm-clang | option-change | product | 1 | 12.025624 | 11.572641 | 478600 | 1.34 | 1.29 |
| llvm-clang | initial | musl | 1 | 18.468791 | 18.425662 | 489092 | 1.29 | 1.34 |
| llvm-clang | unchanged | musl | 1 | 11.957631 | 11.636645 | 478636 | 1.34 | 1.29 |
| llvm-clang | cmakelists-edit | musl | 1 | 12.113846 | 11.649809 | 478492 | 1.29 | 1.38 |
| llvm-clang | option-change | musl | 1 | 12.101223 | 11.619063 | 478548 | 1.32 | 1.25 |
| llvm-clang | initial | kitware | 1 | 14.732250 | 14.752593 | 388568 | 1.25 | 1.19 |
| llvm-clang | unchanged | kitware | 1 | 9.027473 | 8.768005 | 379252 | 1.19 | 1.16 |
| llvm-clang | cmakelists-edit | kitware | 1 | 9.377170 | 9.060423 | 379240 | 1.16 | 1.14 |
| llvm-clang | option-change | kitware | 1 | 8.664874 | 8.319817 | 379216 | 1.12 | 1.11 |
| llvm-clang | initial | musl | 2 | 16.689243 | 16.687785 | 489292 | 1.10 | 1.22 |
| llvm-clang | unchanged | musl | 2 | 10.857490 | 10.626758 | 478636 | 1.22 | 1.19 |
| llvm-clang | cmakelists-edit | musl | 2 | 10.953395 | 10.503779 | 478664 | 1.19 | 1.31 |
| llvm-clang | option-change | musl | 2 | 10.934046 | 10.565509 | 478536 | 1.39 | 1.33 |
| llvm-clang | initial | kitware | 2 | 13.784785 | 13.801661 | 388576 | 1.33 | 1.32 |
| llvm-clang | unchanged | kitware | 2 | 8.225896 | 8.067277 | 379212 | 1.32 | 1.27 |
| llvm-clang | cmakelists-edit | kitware | 2 | 8.427804 | 8.016252 | 379228 | 1.27 | 1.25 |
| llvm-clang | option-change | kitware | 2 | 8.328965 | 8.035633 | 379196 | 1.21 | 1.18 |
| llvm-clang | initial | product | 2 | 16.117232 | 16.149949 | 489164 | 1.18 | 1.21 |
| llvm-clang | unchanged | product | 2 | 10.764011 | 10.532361 | 478580 | 1.21 | 1.17 |
| llvm-clang | cmakelists-edit | product | 2 | 11.105454 | 10.436696 | 478600 | 1.17 | 1.29 |
| llvm-clang | option-change | product | 2 | 10.577069 | 10.242694 | 478528 | 1.40 | 1.34 |
| llvm-clang | initial | kitware | 3 | 13.841993 | 13.874794 | 388620 | 1.34 | 1.26 |
| llvm-clang | unchanged | kitware | 3 | 8.297313 | 8.123282 | 379268 | 1.26 | 1.22 |
| llvm-clang | cmakelists-edit | kitware | 3 | 8.454108 | 8.142522 | 379252 | 1.22 | 1.20 |
| llvm-clang | option-change | kitware | 3 | 8.509965 | 8.064409 | 379280 | 1.17 | 1.14 |
| llvm-clang | initial | product | 3 | 16.082981 | 16.109484 | 488952 | 1.14 | 1.11 |
| llvm-clang | unchanged | product | 3 | 10.571265 | 10.281264 | 478536 | 1.11 | 1.09 |
| llvm-clang | cmakelists-edit | product | 3 | 10.919820 | 10.513529 | 478500 | 1.09 | 1.07 |
| llvm-clang | option-change | product | 3 | 10.634232 | 10.191406 | 478600 | 1.22 | 1.18 |
| llvm-clang | initial | musl | 3 | 16.392066 | 16.429845 | 489116 | 1.18 | 1.21 |
| llvm-clang | unchanged | musl | 3 | 10.853879 | 10.547650 | 478724 | 1.19 | 1.16 |
| llvm-clang | cmakelists-edit | musl | 3 | 11.017820 | 10.436136 | 478588 | 1.16 | 1.14 |
| llvm-clang | option-change | musl | 3 | 10.820375 | 10.315755 | 478608 | 1.20 | 1.17 |
| llvm-clang | initial | product | 4 | 15.803985 | 15.834924 | 489252 | 1.17 | 1.34 |
| llvm-clang | unchanged | product | 4 | 10.485165 | 10.213908 | 478400 | 1.34 | 1.29 |
| llvm-clang | cmakelists-edit | product | 4 | 10.721940 | 10.284184 | 478640 | 1.29 | 1.32 |
| llvm-clang | option-change | product | 4 | 10.841381 | 10.389147 | 478592 | 1.35 | 1.29 |
| llvm-clang | initial | musl | 4 | 16.423065 | 16.417528 | 489132 | 1.27 | 1.28 |
| llvm-clang | unchanged | musl | 4 | 10.711402 | 10.505616 | 478564 | 1.28 | 1.24 |
| llvm-clang | cmakelists-edit | musl | 4 | 10.826925 | 10.444940 | 478580 | 1.24 | 1.20 |
| llvm-clang | option-change | musl | 4 | 10.994782 | 10.602536 | 478652 | 1.17 | 1.13 |
| llvm-clang | initial | kitware | 4 | 14.508999 | 14.494628 | 388468 | 1.13 | 1.10 |
| llvm-clang | unchanged | kitware | 4 | 8.560115 | 8.266882 | 379248 | 1.10 | 1.09 |
| llvm-clang | cmakelists-edit | kitware | 4 | 8.610212 | 8.267454 | 379264 | 1.09 | 1.16 |
| llvm-clang | option-change | kitware | 4 | 8.561455 | 8.204551 | 379300 | 1.21 | 1.18 |
| llvm-clang | initial | musl | 5 | 16.624149 | 16.579651 | 489092 | 1.18 | 1.20 |
| llvm-clang | unchanged | musl | 5 | 10.753856 | 10.551826 | 478764 | 1.19 | 1.16 |
| llvm-clang | cmakelists-edit | musl | 5 | 11.226720 | 10.444463 | 478408 | 1.16 | 1.13 |
| llvm-clang | option-change | musl | 5 | 11.085824 | 10.725784 | 478604 | 1.11 | 1.10 |
| llvm-clang | initial | kitware | 5 | 14.516797 | 14.544235 | 388552 | 1.09 | 1.15 |
| llvm-clang | unchanged | kitware | 5 | 8.385663 | 8.215787 | 379228 | 1.14 | 1.13 |
| llvm-clang | cmakelists-edit | kitware | 5 | 8.802173 | 8.378924 | 379292 | 1.13 | 1.19 |
| llvm-clang | option-change | kitware | 5 | 8.585852 | 8.261194 | 379268 | 1.23 | 1.21 |
| llvm-clang | initial | product | 5 | 16.169452 | 16.144875 | 488964 | 1.20 | 1.15 |
| llvm-clang | unchanged | product | 5 | 10.819857 | 10.489829 | 478620 | 1.15 | 1.13 |
| llvm-clang | cmakelists-edit | product | 5 | 11.307310 | 10.871679 | 478696 | 1.13 | 1.11 |
| llvm-clang | option-change | product | 5 | 10.539950 | 10.251705 | 478420 | 1.08 | 1.07 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 20.35    0.001589           5       283        42 access
 17.61    0.001375           6       204        13 stat
 16.02    0.001251         625         2           wait4
 14.46    0.001129           6       187       179 readlink
 13.27    0.001036           9       110         4 open
  5.66    0.000442           9        49        39 unlink
  4.37    0.000341           6        53         1 lstat
  2.83    0.000221         110         2           fork
  1.84    0.000144          20         7         2 rename
  1.61    0.000126          42         3           execve
  0.87    0.000068           9         7         6 mkdir
  0.69    0.000054           9         6           chmod
  0.44    0.000034          34         1           rmdir
  0.00    0.000000           0         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.007810           8       916       286 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 29.68    0.002632        1316         2           wait4
 13.42    0.001190           5       204        13 stat
 12.65    0.001122           6       187       179 readlink
 12.07    0.001070           3       283        42 access
 11.93    0.001058           9       110         4 open
  4.87    0.000432           8        49        39 unlink
  3.88    0.000344         114         3           execve
  3.85    0.000341           6        53         1 lstat
  2.68    0.000238         119         2           fork
  2.58    0.000229          32         7         2 rename
  1.00    0.000089          12         7         6 mkdir
  0.73    0.000065          10         6           chmod
  0.52    0.000046          46         1           rmdir
  0.07    0.000006           6         1           getcwd
  0.07    0.000006           6         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.008868           9       916       286 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 32.07    0.002580        1290         2           wait4
 14.10    0.001134           3       284        40 access
 11.79    0.000948           4       204        13 stat
  9.95    0.000800           4       187       179 readlink
  8.29    0.000667           5       114         6 openat
  5.32    0.000428         142         3           execve
  4.49    0.000361           7        49        39 unlink
  4.15    0.000334         167         2           clone
  3.97    0.000319           6        53         1 lstat
  2.96    0.000238          34         7         2 rename
  1.33    0.000107          15         7         1 open
  0.56    0.000045           6         7         6 mkdir
  0.55    0.000044           7         6           chmod
  0.31    0.000025          25         1           rmdir
  0.09    0.000007           7         1           getcwd
  0.09    0.000007           7         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.008044           8       928       287 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 24.02    0.002988           4       685       211 access
 17.88    0.002224           5       385       369 readlink
 15.74    0.001958           5       339        28 stat
 10.68    0.001328         664         2           wait4
 10.17    0.001265           7       161         4 open
  6.13    0.000762           8        94        85 unlink
  5.62    0.000699           6       109         9 lstat
  4.65    0.000579          64         9         2 rename
  2.19    0.000272         136         2           fork
  1.70    0.000212          70         3           execve
  0.55    0.000068           9         7         6 mkdir
  0.31    0.000038           7         5           chmod
  0.27    0.000034          34         1           rmdir
  0.05    0.000006           6         1           getcwd
  0.05    0.000006           6         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.012439           6      1804       714 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 32.03    0.003338           4       685       211 access
 16.05    0.001673           4       385       369 readlink
 15.67    0.001633           4       339        28 stat
 11.17    0.001164           7       161         4 open
  8.97    0.000935         467         2           wait4
  5.79    0.000603           6        94        85 unlink
  5.15    0.000537           4       109         9 lstat
  2.31    0.000241          26         9         2 rename
  1.18    0.000123          61         2           fork
  0.74    0.000077          11         7         6 mkdir
  0.47    0.000049          49         1           rmdir
  0.40    0.000042           8         5           chmod
  0.07    0.000007           7         1           chdir
  0.00    0.000000           0         3           execve
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.010422           5      1804       714 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 19.61    0.002266           3       686       209 access
 19.13    0.002211        1105         2           wait4
 14.05    0.001624           4       378       362 readlink
 13.86    0.001602           4       339        28 stat
  9.38    0.001084           6       165         6 openat
  6.43    0.000743           6       109         9 lstat
  6.19    0.000715           7        94        85 unlink
  3.79    0.000438          48         9         2 rename
  3.02    0.000349         174         2           clone
  1.77    0.000205          68         3           execve
  0.91    0.000105          15         7         1 open
  0.68    0.000079          11         7         6 mkdir
  0.50    0.000058          58         1           rmdir
  0.35    0.000041           8         5           chmod
  0.21    0.000024           3         7           faccessat2
  0.06    0.000007           7         1           chdir
  0.05    0.000006           6         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.011557           6      1816       708 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 74.16    0.070177        5012        14         2 wait4
  7.71    0.007295           4      1718      1623 readlink
  4.66    0.004413           4       927       121 stat
  3.65    0.003452           3      1040       451 access
  2.59    0.002452           5       473         7 lstat
  2.58    0.002441           7       308        18 open
  1.78    0.001689           8       200       155 unlink
  1.05    0.000991         141         7           fork
  0.64    0.000604          28        21         5 rename
  0.31    0.000297          22        13           execve
  0.28    0.000267          10        25        21 mkdir
  0.19    0.000180          25         7           clone
  0.19    0.000180           6        27           chmod
  0.13    0.000124          31         4           rmdir
  0.05    0.000045           6         7           chdir
  0.02    0.000019           9         2           vfork
  0.00    0.000000           0         3           getcwd
  0.00    0.000000           0         4           openat
------ ----------- ----------- --------- --------- ----------------
100.00    0.094626          19      4800      2403 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 70.57    0.073258        5232        14         2 wait4
  9.43    0.009787           5      1718      1623 readlink
  5.18    0.005377           5       927       121 stat
  4.06    0.004211           4      1040       451 access
  2.82    0.002927           6       473         7 lstat
  2.66    0.002765           8       308        18 open
  1.89    0.001964           9       200       155 unlink
  0.87    0.000907         129         7           fork
  0.75    0.000776          36        21         5 rename
  0.73    0.000761          58        13           execve
  0.34    0.000348          49         7           clone
  0.29    0.000305          12        25        21 mkdir
  0.20    0.000210           7        27           chmod
  0.12    0.000122          30         4           rmdir
  0.05    0.000048           6         7           chdir
  0.03    0.000032          16         2           vfork
  0.01    0.000014           4         3           getcwd
  0.00    0.000000           0         4           openat
------ ----------- ----------- --------- --------- ----------------
100.00    0.103812          21      4800      2403 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 72.26    0.076745        5481        14         2 wait4
  8.07    0.008574           4      1718      1623 readlink
  4.67    0.004955           5       927       121 stat
  4.05    0.004305           4      1041       449 access
  2.47    0.002625           5       473         7 lstat
  1.82    0.001937           9       200       155 unlink
  1.81    0.001918           7       259        11 openat
  1.40    0.001483         114        13           execve
  1.32    0.001399          99        14           clone
  0.73    0.000780          37        21         5 rename
  0.73    0.000779          12        64        10 open
  0.23    0.000240           9        25        21 mkdir
  0.21    0.000220           8        27           chmod
  0.11    0.000118          29         4           rmdir
  0.06    0.000068          34         2           vfork
  0.04    0.000046           6         7           chdir
  0.01    0.000013           4         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.106205          22      4812      2404 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 35.07    1.564395           6    241126      3506 stat
 19.08    0.850905           7    117306        25 lstat
 14.90    0.664504           4    150759    147465 readlink
 13.53    0.603737        9737        62         9 wait4
  6.43    0.286638           4     70886     42409 access
  2.74    0.122358        2399        51           execve
  2.57    0.114423        2860        40           fork
  2.45    0.109198           5     19689     19585 unlink
  2.12    0.094411           6     13777       219 open
  1.06    0.047264          69       682         5 rename
  0.02    0.000870           7       109           chmod
  0.02    0.000688          45        15           clone
  0.01    0.000355           4        80           getcwd
  0.01    0.000301           4        64        54 newfstatat
  0.01    0.000253          10        25        21 mkdir
  0.01    0.000237           6        38           openat
  0.00    0.000126          31         4           rmdir
  0.00    0.000088           5        15           chdir
  0.00    0.000045          22         2           vfork
  0.00    0.000018           9         2         2 statfs
  0.00    0.000014           2         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.460828           7    614737    213300 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 35.32    1.645843           6    241126      3506 stat
 19.33    0.900512           7    117306        25 lstat
 15.24    0.710023           4    150759    147465 readlink
 13.20    0.615094        9920        62         9 wait4
  6.13    0.285759           4     70886     42409 access
  2.69    0.125310        2457        51           execve
  2.48    0.115738        2893        40           fork
  2.35    0.109563           5     19689     19585 unlink
  2.14    0.099673           7     13777       219 open
  1.05    0.048831          71       682         5 rename
  0.02    0.000954           8       109           chmod
  0.02    0.000721          48        15           clone
  0.01    0.000298           3        80           getcwd
  0.01    0.000264           4        64        54 newfstatat
  0.01    0.000246           9        25        21 mkdir
  0.00    0.000208           5        38           openat
  0.00    0.000114          28         4           rmdir
  0.00    0.000093           6        15           chdir
  0.00    0.000063          31         2           vfork
  0.00    0.000026          13         2         2 statfs
  0.00    0.000014           2         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.659347           7    614737    213300 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 36.25    1.608855           6    241126      3506 stat
 19.29    0.856218           7    117306        25 lstat
 15.10    0.669959           4    150735    147441 readlink
 13.56    0.601703        9704        62         9 wait4
  5.98    0.265361           3     70889     42403 access
  2.30    0.102175        2003        51           execve
  2.29    0.101543           5     19689     19585 unlink
  2.06    0.091578        1665        55           clone
  1.91    0.084748           6     12763        72 openat
  1.07    0.047396          69       682         5 rename
  0.14    0.006285           5      1085       156 open
  0.02    0.000777           7       109           chmod
  0.01    0.000282          11        25        21 mkdir
  0.01    0.000272           3        80           getcwd
  0.01    0.000250           3        64        54 newfstatat
  0.00    0.000129          32         4           rmdir
  0.00    0.000106           7        15           chdir
  0.00    0.000098           4        24           faccessat2
  0.00    0.000016           8         2           vfork
  0.00    0.000000           0         2         2 statfs
  0.00    0.000000           0         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.437751           7    614773    213279 total
```
