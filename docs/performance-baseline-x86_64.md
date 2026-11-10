# x86-64 CMake memory baseline

This run measured the qualified `58313ac` archive to establish the memory
baseline. It does not measure the later section-garbage-collection candidate.

Target: `x86_64-unknown-linux-musl`. Runs per variant: 5.

All three binaries ran in the same native Debian container with the pinned musl toolchain.
Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource
differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with
OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those
product differences and does not isolate an individual compiler flag.
A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not
measured. Timings are not release gates.

Host: `Linux-7.0.0-1017-azure-x86_64-with-glibc2.39`. CPU: `AMD EPYC 7763 64-Core Processor`. Container: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
CPU affinity: `[0, 1, 2, 3]`. Product archive SHA-256: `b53ca751fd8c1f0c3b3918c7c9aed7f5a30a79b2bbf4f9289ec567ede5a0cc3e`.
Official archive SHA-256: `ed85135c5a5135b45e50423cb406dea04ca3338da0b8ef3c9ede963559680be0`. Baseline output digest: `9b4d95742a059af6af1225b7e943665f30434b043d386b2bcf95ddce71e7853e`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `c43f18f143cc17f49814b6c5dda8a1122d17b6bcdff9848b6f77e97b33026dfe`.
Tracer: `strace -- version 6.8`. Runner SHA-256: `f72a566ff6b678eaea8964ab0956e069201176cde3f0c61a008eb187a3f46e4b`.
Benchmark implementation SHA-256: `f6e566b3deabe25ebe2328aae2253e89fa6663a6d25cf93f481478d606f34282`.
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
| product | 41805976 | 54476668 | 10171144 |
| musl | 24404144 | 36026480 | not packaged |
| kitware | 21469504 | 190375166 | 64865573 |

## Measurements

RSS is CMake's image high-water mark, read before exit; it excludes child processes.
Configure timings include process-tracing overhead. Startup timings are untraced; their RSS
comes from a separate traced invocation. CPU time includes waited child processes.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.030679 | 0.030049–0.031519 | 0.028338 | 14832 |
| fmt | cmakelists-edit | musl | 0.054673 | 0.054053–0.056182 | 0.052749 | 13840 |
| fmt | cmakelists-edit | product | 0.055634 | 0.055143–0.056082 | 0.053785 | 15024 |
| fmt | initial | kitware | 0.220423 | 0.212751–0.228225 | 0.220409 | 16760 |
| fmt | initial | musl | 0.263274 | 0.258212–0.270563 | 0.263094 | 15552 |
| fmt | initial | product | 0.265225 | 0.262075–0.269014 | 0.266102 | 16704 |
| fmt | option-change | kitware | 0.030699 | 0.030025–0.030836 | 0.028848 | 14828 |
| fmt | option-change | musl | 0.055264 | 0.054555–0.055531 | 0.053524 | 13840 |
| fmt | option-change | product | 0.056522 | 0.056305–0.056577 | 0.054623 | 15024 |
| fmt | unchanged | kitware | 0.030308 | 0.029923–0.030818 | 0.028864 | 14816 |
| fmt | unchanged | musl | 0.054608 | 0.053418–0.055458 | 0.053000 | 13840 |
| fmt | unchanged | product | 0.055864 | 0.055811–0.056597 | 0.054378 | 15024 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.117560 | 0.114654–0.119992 | 0.115996 | 16360 |
| libjpeg-turbo | cmakelists-edit | musl | 0.144962 | 0.144482–0.146820 | 0.143866 | 15196 |
| libjpeg-turbo | cmakelists-edit | product | 0.146542 | 0.143118–0.148627 | 0.144110 | 16496 |
| libjpeg-turbo | initial | kitware | 0.734258 | 0.729335–0.743187 | 0.740901 | 17928 |
| libjpeg-turbo | initial | musl | 0.797501 | 0.790007–0.805067 | 0.803351 | 16996 |
| libjpeg-turbo | initial | product | 0.802285 | 0.799276–0.811612 | 0.808527 | 18308 |
| libjpeg-turbo | option-change | kitware | 0.122494 | 0.119265–0.125378 | 0.120025 | 16420 |
| libjpeg-turbo | option-change | musl | 0.158739 | 0.156768–0.160483 | 0.157426 | 15196 |
| libjpeg-turbo | option-change | product | 0.158297 | 0.157340–0.163394 | 0.157492 | 16496 |
| libjpeg-turbo | unchanged | kitware | 0.116955 | 0.115185–0.120305 | 0.114999 | 16356 |
| libjpeg-turbo | unchanged | musl | 0.144745 | 0.143080–0.149628 | 0.143004 | 15192 |
| libjpeg-turbo | unchanged | product | 0.146160 | 0.144257–0.149272 | 0.144314 | 16560 |
| llvm-clang | cmakelists-edit | kitware | 13.047671 | 12.980433–13.373516 | 12.986141 | 379244 |
| llvm-clang | cmakelists-edit | musl | 15.731718 | 15.583374–16.117363 | 15.615473 | 478676 |
| llvm-clang | cmakelists-edit | product | 15.924788 | 15.753488–16.242414 | 15.817933 | 480776 |
| llvm-clang | initial | kitware | 20.352711 | 20.198622–20.859883 | 20.395523 | 388520 |
| llvm-clang | initial | musl | 23.409204 | 23.021430–24.292984 | 23.424525 | 489256 |
| llvm-clang | initial | product | 23.562566 | 23.209319–24.100489 | 23.476759 | 491424 |
| llvm-clang | option-change | kitware | 13.072249 | 12.991884–13.312193 | 13.004504 | 379204 |
| llvm-clang | option-change | musl | 15.753474 | 15.611674–16.013228 | 15.651800 | 478664 |
| llvm-clang | option-change | product | 15.924224 | 15.637720–16.189822 | 15.808872 | 480824 |
| llvm-clang | unchanged | kitware | 12.982324 | 12.888124–13.051521 | 12.967407 | 379176 |
| llvm-clang | unchanged | musl | 15.931540 | 15.527311–16.055138 | 15.880018 | 478700 |
| llvm-clang | unchanged | product | 15.718002 | 15.651716–16.211318 | 15.663126 | 480768 |
| process | script | kitware | 0.002354 | 0.002273–0.002383 | 0.002022 | 10816 |
| process | script | musl | 0.002288 | 0.002268–0.002398 | 0.001975 | 11080 |
| process | script | product | 0.002936 | 0.002904–0.002945 | 0.002592 | 11864 |
| process | version | kitware | 0.002382 | 0.002310–0.002447 | 0.002059 | 10148 |
| process | version | musl | 0.002250 | 0.002178–0.002398 | 0.001920 | 10960 |
| process | version | product | 0.002928 | 0.002878–0.002981 | 0.002594 | 11704 |
| zstd | cmakelists-edit | kitware | 0.046977 | 0.046498–0.049389 | 0.044836 | 15452 |
| zstd | cmakelists-edit | musl | 0.072385 | 0.072101–0.073122 | 0.070262 | 14452 |
| zstd | cmakelists-edit | product | 0.073956 | 0.072850–0.077957 | 0.071949 | 15720 |
| zstd | initial | kitware | 1.209518 | 1.202886–1.218958 | 1.213955 | 18656 |
| zstd | initial | musl | 1.301030 | 1.291242–1.312723 | 1.309482 | 17544 |
| zstd | initial | product | 1.317728 | 1.313633–1.324794 | 1.327246 | 18960 |
| zstd | option-change | kitware | 0.048304 | 0.047676–0.049110 | 0.046143 | 15460 |
| zstd | option-change | musl | 0.075690 | 0.074857–0.076706 | 0.073603 | 14448 |
| zstd | option-change | product | 0.076907 | 0.075268–0.078411 | 0.074984 | 15720 |
| zstd | unchanged | kitware | 0.046618 | 0.045906–0.047038 | 0.045032 | 15480 |
| zstd | unchanged | musl | 0.072592 | 0.071584–0.076547 | 0.071031 | 14452 |
| zstd | unchanged | product | 0.074711 | 0.073034–0.075643 | 0.072486 | 15768 |

## Raw samples

Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.002957 | 0.002567 | 11704 | 1.29 | 1.29 |
| process | script | product | 1 | 0.002936 | 0.002602 | 11864 | 1.29 | 1.29 |
| process | version | musl | 1 | 0.002257 | 0.001934 | 10960 | 1.29 | 1.29 |
| process | script | musl | 1 | 0.002284 | 0.001965 | 11080 | 1.29 | 1.29 |
| process | version | kitware | 1 | 0.002382 | 0.002063 | 10064 | 1.29 | 1.29 |
| process | script | kitware | 1 | 0.002354 | 0.002023 | 10816 | 1.29 | 1.29 |
| process | version | musl | 2 | 0.002398 | 0.001980 | 10960 | 1.29 | 1.29 |
| process | script | musl | 2 | 0.002358 | 0.002000 | 11080 | 1.29 | 1.29 |
| process | version | kitware | 2 | 0.002310 | 0.001990 | 10128 | 1.29 | 1.29 |
| process | script | kitware | 2 | 0.002379 | 0.002022 | 10776 | 1.29 | 1.29 |
| process | version | product | 2 | 0.002981 | 0.002652 | 11704 | 1.29 | 1.29 |
| process | script | product | 2 | 0.002939 | 0.002572 | 11864 | 1.29 | 1.29 |
| process | version | kitware | 3 | 0.002375 | 0.002050 | 10064 | 1.29 | 1.29 |
| process | script | kitware | 3 | 0.002313 | 0.001972 | 10692 | 1.29 | 1.29 |
| process | version | product | 3 | 0.002922 | 0.002594 | 11704 | 1.29 | 1.29 |
| process | script | product | 3 | 0.002924 | 0.002592 | 11864 | 1.29 | 1.29 |
| process | version | musl | 3 | 0.002250 | 0.001920 | 10960 | 1.29 | 1.29 |
| process | script | musl | 3 | 0.002398 | 0.001980 | 11080 | 1.29 | 1.29 |
| process | version | product | 4 | 0.002928 | 0.002597 | 11704 | 1.29 | 1.29 |
| process | script | product | 4 | 0.002945 | 0.002596 | 11864 | 1.29 | 1.29 |
| process | version | musl | 4 | 0.002229 | 0.001895 | 10960 | 1.29 | 1.29 |
| process | script | musl | 4 | 0.002268 | 0.001964 | 11080 | 1.29 | 1.29 |
| process | version | kitware | 4 | 0.002392 | 0.002059 | 10064 | 1.29 | 1.29 |
| process | script | kitware | 4 | 0.002273 | 0.001968 | 10780 | 1.29 | 1.29 |
| process | version | musl | 5 | 0.002178 | 0.001822 | 10960 | 1.29 | 1.29 |
| process | script | musl | 5 | 0.002288 | 0.001975 | 11080 | 1.29 | 1.29 |
| process | version | kitware | 5 | 0.002447 | 0.002085 | 10148 | 1.29 | 1.29 |
| process | script | kitware | 5 | 0.002383 | 0.002058 | 10696 | 1.29 | 1.29 |
| process | version | product | 5 | 0.002878 | 0.002560 | 11704 | 1.29 | 1.29 |
| process | script | product | 5 | 0.002904 | 0.002588 | 11864 | 1.29 | 1.29 |
| fmt | initial | product | 1 | 0.262089 | 0.264017 | 16704 | 1.29 | 1.29 |
| fmt | unchanged | product | 1 | 0.056597 | 0.054987 | 15024 | 1.29 | 1.29 |
| fmt | cmakelists-edit | product | 1 | 0.055634 | 0.053785 | 15024 | 1.29 | 1.29 |
| fmt | option-change | product | 1 | 0.056522 | 0.054623 | 15024 | 1.29 | 1.29 |
| fmt | initial | musl | 1 | 0.259914 | 0.261198 | 15508 | 1.29 | 1.29 |
| fmt | unchanged | musl | 1 | 0.054342 | 0.052710 | 13840 | 1.29 | 1.29 |
| fmt | cmakelists-edit | musl | 1 | 0.056182 | 0.052749 | 13840 | 1.29 | 1.29 |
| fmt | option-change | musl | 1 | 0.054555 | 0.052766 | 13840 | 1.29 | 1.29 |
| fmt | initial | kitware | 1 | 0.228225 | 0.227716 | 16736 | 1.29 | 1.29 |
| fmt | unchanged | kitware | 1 | 0.030730 | 0.029171 | 14816 | 1.29 | 1.29 |
| fmt | cmakelists-edit | kitware | 1 | 0.030679 | 0.028894 | 14744 | 1.29 | 1.29 |
| fmt | option-change | kitware | 1 | 0.030493 | 0.028681 | 14828 | 1.29 | 1.29 |
| fmt | initial | musl | 2 | 0.265162 | 0.267254 | 15420 | 1.29 | 1.29 |
| fmt | unchanged | musl | 2 | 0.054608 | 0.053000 | 13840 | 1.29 | 1.29 |
| fmt | cmakelists-edit | musl | 2 | 0.054053 | 0.052211 | 13840 | 1.29 | 1.29 |
| fmt | option-change | musl | 2 | 0.055264 | 0.053524 | 13840 | 1.29 | 1.29 |
| fmt | initial | kitware | 2 | 0.220184 | 0.218365 | 16760 | 1.29 | 1.29 |
| fmt | unchanged | kitware | 2 | 0.029923 | 0.028414 | 14748 | 1.29 | 1.29 |
| fmt | cmakelists-edit | kitware | 2 | 0.030049 | 0.028338 | 14788 | 1.29 | 1.29 |
| fmt | option-change | kitware | 2 | 0.030795 | 0.028848 | 14824 | 1.29 | 1.29 |
| fmt | initial | product | 2 | 0.265741 | 0.266102 | 16704 | 1.29 | 1.29 |
| fmt | unchanged | product | 2 | 0.055858 | 0.054348 | 15024 | 1.29 | 1.34 |
| fmt | cmakelists-edit | product | 2 | 0.056082 | 0.054367 | 15024 | 1.34 | 1.34 |
| fmt | option-change | product | 2 | 0.056523 | 0.054645 | 15024 | 1.34 | 1.34 |
| fmt | initial | kitware | 3 | 0.220423 | 0.220465 | 16640 | 1.34 | 1.34 |
| fmt | unchanged | kitware | 3 | 0.030818 | 0.029385 | 14792 | 1.34 | 1.34 |
| fmt | cmakelists-edit | kitware | 3 | 0.031519 | 0.028322 | 14788 | 1.34 | 1.34 |
| fmt | option-change | kitware | 3 | 0.030836 | 0.028965 | 14740 | 1.34 | 1.34 |
| fmt | initial | product | 3 | 0.265225 | 0.266618 | 16704 | 1.34 | 1.34 |
| fmt | unchanged | product | 3 | 0.055811 | 0.054252 | 15024 | 1.34 | 1.34 |
| fmt | cmakelists-edit | product | 3 | 0.055143 | 0.053430 | 15024 | 1.34 | 1.34 |
| fmt | option-change | product | 3 | 0.056339 | 0.054431 | 15024 | 1.34 | 1.34 |
| fmt | initial | musl | 3 | 0.263274 | 0.263094 | 15444 | 1.34 | 1.34 |
| fmt | unchanged | musl | 3 | 0.054795 | 0.053006 | 13840 | 1.34 | 1.34 |
| fmt | cmakelists-edit | musl | 3 | 0.054323 | 0.052430 | 13716 | 1.34 | 1.34 |
| fmt | option-change | musl | 3 | 0.054940 | 0.053152 | 13840 | 1.34 | 1.34 |
| fmt | initial | product | 4 | 0.262075 | 0.264165 | 16684 | 1.34 | 1.34 |
| fmt | unchanged | product | 4 | 0.056297 | 0.054806 | 15024 | 1.34 | 1.34 |
| fmt | cmakelists-edit | product | 4 | 0.055957 | 0.054236 | 15024 | 1.34 | 1.34 |
| fmt | option-change | product | 4 | 0.056305 | 0.054559 | 15024 | 1.34 | 1.34 |
| fmt | initial | musl | 4 | 0.270563 | 0.272370 | 15508 | 1.34 | 1.34 |
| fmt | unchanged | musl | 4 | 0.055458 | 0.054004 | 13716 | 1.34 | 1.34 |
| fmt | cmakelists-edit | musl | 4 | 0.054942 | 0.052962 | 13840 | 1.34 | 1.34 |
| fmt | option-change | musl | 4 | 0.055447 | 0.053527 | 13840 | 1.34 | 1.34 |
| fmt | initial | kitware | 4 | 0.212751 | 0.214664 | 16728 | 1.34 | 1.34 |
| fmt | unchanged | kitware | 4 | 0.030022 | 0.028583 | 14712 | 1.34 | 1.34 |
| fmt | cmakelists-edit | kitware | 4 | 0.030084 | 0.028183 | 14824 | 1.34 | 1.34 |
| fmt | option-change | kitware | 4 | 0.030025 | 0.028305 | 14736 | 1.34 | 1.34 |
| fmt | initial | musl | 5 | 0.258212 | 0.258964 | 15552 | 1.34 | 1.34 |
| fmt | unchanged | musl | 5 | 0.053418 | 0.052006 | 13840 | 1.34 | 1.34 |
| fmt | cmakelists-edit | musl | 5 | 0.054673 | 0.052930 | 13716 | 1.34 | 1.34 |
| fmt | option-change | musl | 5 | 0.055531 | 0.053615 | 13840 | 1.34 | 1.34 |
| fmt | initial | kitware | 5 | 0.221665 | 0.220409 | 16740 | 1.34 | 1.34 |
| fmt | unchanged | kitware | 5 | 0.030308 | 0.028864 | 14792 | 1.34 | 1.34 |
| fmt | cmakelists-edit | kitware | 5 | 0.030716 | 0.028846 | 14832 | 1.34 | 1.34 |
| fmt | option-change | kitware | 5 | 0.030699 | 0.028899 | 14792 | 1.34 | 1.34 |
| fmt | initial | product | 5 | 0.269014 | 0.271225 | 16688 | 1.34 | 1.34 |
| fmt | unchanged | product | 5 | 0.055864 | 0.054378 | 15024 | 1.34 | 1.34 |
| fmt | cmakelists-edit | product | 5 | 0.055574 | 0.053690 | 15024 | 1.34 | 1.34 |
| fmt | option-change | product | 5 | 0.056577 | 0.054792 | 15024 | 1.34 | 1.34 |
| zstd | initial | product | 1 | 1.313633 | 1.325745 | 18960 | 1.66 | 1.66 |
| zstd | unchanged | product | 1 | 0.073496 | 0.072007 | 15764 | 1.66 | 1.66 |
| zstd | cmakelists-edit | product | 1 | 0.072850 | 0.070791 | 15716 | 1.66 | 1.66 |
| zstd | option-change | product | 1 | 0.077316 | 0.075302 | 15720 | 1.66 | 1.66 |
| zstd | initial | musl | 1 | 1.306097 | 1.318459 | 17544 | 1.66 | 1.68 |
| zstd | unchanged | musl | 1 | 0.076547 | 0.075071 | 14444 | 1.68 | 1.68 |
| zstd | cmakelists-edit | musl | 1 | 0.073122 | 0.071182 | 14328 | 1.68 | 1.68 |
| zstd | option-change | musl | 1 | 0.075735 | 0.073777 | 14448 | 1.68 | 1.68 |
| zstd | initial | kitware | 1 | 1.218958 | 1.220485 | 18616 | 1.68 | 1.68 |
| zstd | unchanged | kitware | 1 | 0.047038 | 0.045525 | 15336 | 1.68 | 1.68 |
| zstd | cmakelists-edit | kitware | 1 | 0.046977 | 0.044836 | 15432 | 1.68 | 1.68 |
| zstd | option-change | kitware | 1 | 0.048304 | 0.046265 | 15460 | 1.68 | 1.68 |
| zstd | initial | musl | 2 | 1.301030 | 1.309482 | 17540 | 1.68 | 1.68 |
| zstd | unchanged | musl | 2 | 0.072592 | 0.071031 | 14452 | 1.68 | 1.68 |
| zstd | cmakelists-edit | musl | 2 | 0.072101 | 0.069856 | 14448 | 1.68 | 1.68 |
| zstd | option-change | musl | 2 | 0.075507 | 0.073390 | 14324 | 1.68 | 1.68 |
| zstd | initial | kitware | 2 | 1.217066 | 1.225187 | 18592 | 1.68 | 1.68 |
| zstd | unchanged | kitware | 2 | 0.046197 | 0.044570 | 15480 | 1.68 | 1.68 |
| zstd | cmakelists-edit | kitware | 2 | 0.046498 | 0.044493 | 15452 | 1.68 | 1.63 |
| zstd | option-change | kitware | 2 | 0.047676 | 0.045693 | 15396 | 1.63 | 1.63 |
| zstd | initial | product | 2 | 1.317691 | 1.327246 | 18928 | 1.63 | 1.63 |
| zstd | unchanged | product | 2 | 0.074846 | 0.072851 | 15624 | 1.63 | 1.63 |
| zstd | cmakelists-edit | product | 2 | 0.073152 | 0.071133 | 15716 | 1.63 | 1.63 |
| zstd | option-change | product | 2 | 0.075268 | 0.072728 | 15720 | 1.63 | 1.63 |
| zstd | initial | kitware | 3 | 1.209518 | 1.213955 | 18608 | 1.63 | 1.63 |
| zstd | unchanged | kitware | 3 | 0.046660 | 0.045032 | 15392 | 1.63 | 1.63 |
| zstd | cmakelists-edit | kitware | 3 | 0.049389 | 0.044940 | 15392 | 1.63 | 1.63 |
| zstd | option-change | kitware | 3 | 0.048144 | 0.046143 | 15392 | 1.63 | 1.63 |
| zstd | initial | product | 3 | 1.321318 | 1.331307 | 18800 | 1.63 | 1.63 |
| zstd | unchanged | product | 3 | 0.073034 | 0.071578 | 15768 | 1.63 | 1.63 |
| zstd | cmakelists-edit | product | 3 | 0.074177 | 0.072272 | 15716 | 1.63 | 1.63 |
| zstd | option-change | product | 3 | 0.076790 | 0.074771 | 15712 | 1.63 | 1.63 |
| zstd | initial | musl | 3 | 1.294065 | 1.305447 | 17392 | 1.63 | 1.58 |
| zstd | unchanged | musl | 3 | 0.072393 | 0.070863 | 14444 | 1.58 | 1.58 |
| zstd | cmakelists-edit | musl | 3 | 0.072644 | 0.070354 | 14448 | 1.58 | 1.58 |
| zstd | option-change | musl | 3 | 0.074857 | 0.072803 | 14448 | 1.58 | 1.58 |
| zstd | initial | product | 4 | 1.317728 | 1.326276 | 18620 | 1.58 | 1.58 |
| zstd | unchanged | product | 4 | 0.075643 | 0.072486 | 15768 | 1.58 | 1.58 |
| zstd | cmakelists-edit | product | 4 | 0.077957 | 0.076056 | 15720 | 1.58 | 1.58 |
| zstd | option-change | product | 4 | 0.076907 | 0.074984 | 15716 | 1.58 | 1.58 |
| zstd | initial | musl | 4 | 1.312723 | 1.321397 | 17500 | 1.58 | 1.58 |
| zstd | unchanged | musl | 4 | 0.071584 | 0.070104 | 14448 | 1.58 | 1.58 |
| zstd | cmakelists-edit | musl | 4 | 0.072385 | 0.070229 | 14452 | 1.58 | 1.58 |
| zstd | option-change | musl | 4 | 0.075690 | 0.073603 | 14444 | 1.58 | 1.58 |
| zstd | initial | kitware | 4 | 1.203499 | 1.212718 | 18656 | 1.58 | 1.61 |
| zstd | unchanged | kitware | 4 | 0.045906 | 0.044319 | 15368 | 1.61 | 1.61 |
| zstd | cmakelists-edit | kitware | 4 | 0.046764 | 0.044720 | 15384 | 1.61 | 1.61 |
| zstd | option-change | kitware | 4 | 0.049110 | 0.046973 | 15376 | 1.61 | 1.61 |
| zstd | initial | musl | 5 | 1.291242 | 1.301446 | 17540 | 1.61 | 1.61 |
| zstd | unchanged | musl | 5 | 0.072910 | 0.071350 | 14448 | 1.61 | 1.61 |
| zstd | cmakelists-edit | musl | 5 | 0.072375 | 0.070262 | 14452 | 1.61 | 1.61 |
| zstd | option-change | musl | 5 | 0.076706 | 0.074404 | 14448 | 1.61 | 1.61 |
| zstd | initial | kitware | 5 | 1.202886 | 1.209517 | 18612 | 1.61 | 1.61 |
| zstd | unchanged | kitware | 5 | 0.046618 | 0.045082 | 15420 | 1.61 | 1.61 |
| zstd | cmakelists-edit | kitware | 5 | 0.047098 | 0.045045 | 15352 | 1.61 | 1.61 |
| zstd | option-change | kitware | 5 | 0.048401 | 0.045928 | 15460 | 1.61 | 1.61 |
| zstd | initial | product | 5 | 1.324794 | 1.332647 | 18920 | 1.61 | 1.64 |
| zstd | unchanged | product | 5 | 0.074711 | 0.073183 | 15768 | 1.64 | 1.64 |
| zstd | cmakelists-edit | product | 5 | 0.073956 | 0.071949 | 15716 | 1.64 | 1.64 |
| zstd | option-change | product | 5 | 0.078411 | 0.076413 | 15716 | 1.64 | 1.64 |
| libjpeg-turbo | initial | product | 1 | 0.802285 | 0.806183 | 18200 | 2.46 | 2.46 |
| libjpeg-turbo | unchanged | product | 1 | 0.144257 | 0.143931 | 16560 | 2.46 | 2.46 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.148627 | 0.144894 | 16468 | 2.46 | 2.46 |
| libjpeg-turbo | option-change | product | 1 | 0.157340 | 0.156129 | 16444 | 2.46 | 2.46 |
| libjpeg-turbo | initial | musl | 1 | 0.791424 | 0.797105 | 16972 | 2.46 | 2.46 |
| libjpeg-turbo | unchanged | musl | 1 | 0.149628 | 0.145558 | 15192 | 2.46 | 2.46 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.146716 | 0.145801 | 15196 | 2.46 | 2.46 |
| libjpeg-turbo | option-change | musl | 1 | 0.156768 | 0.155809 | 15196 | 2.34 | 2.34 |
| libjpeg-turbo | initial | kitware | 1 | 0.740347 | 0.743363 | 17824 | 2.34 | 2.34 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.118816 | 0.116711 | 16312 | 2.34 | 2.34 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.119992 | 0.118857 | 16280 | 2.34 | 2.34 |
| libjpeg-turbo | option-change | kitware | 1 | 0.121224 | 0.120025 | 16328 | 2.34 | 2.34 |
| libjpeg-turbo | initial | musl | 2 | 0.800944 | 0.804010 | 16656 | 2.34 | 2.34 |
| libjpeg-turbo | unchanged | musl | 2 | 0.143080 | 0.141236 | 15124 | 2.34 | 2.34 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.144482 | 0.142542 | 15068 | 2.34 | 2.34 |
| libjpeg-turbo | option-change | musl | 2 | 0.158739 | 0.156962 | 15040 | 2.34 | 2.34 |
| libjpeg-turbo | initial | kitware | 2 | 0.733972 | 0.737591 | 17840 | 2.34 | 2.34 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.116955 | 0.114906 | 16320 | 2.34 | 2.34 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.118480 | 0.117557 | 16272 | 2.34 | 2.34 |
| libjpeg-turbo | option-change | kitware | 2 | 0.125378 | 0.124211 | 16420 | 2.34 | 2.34 |
| libjpeg-turbo | initial | product | 2 | 0.805347 | 0.813522 | 18160 | 2.34 | 2.34 |
| libjpeg-turbo | unchanged | product | 2 | 0.149272 | 0.146321 | 16400 | 2.34 | 2.23 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.146542 | 0.144110 | 16468 | 2.23 | 2.23 |
| libjpeg-turbo | option-change | product | 2 | 0.158956 | 0.158044 | 16456 | 2.23 | 2.23 |
| libjpeg-turbo | initial | kitware | 3 | 0.743187 | 0.746743 | 17860 | 2.23 | 2.23 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.115185 | 0.114371 | 16288 | 2.23 | 2.23 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.117445 | 0.115853 | 16360 | 2.23 | 2.23 |
| libjpeg-turbo | option-change | kitware | 3 | 0.124674 | 0.119494 | 16312 | 2.23 | 2.23 |
| libjpeg-turbo | initial | product | 3 | 0.811612 | 0.815651 | 18212 | 2.23 | 2.23 |
| libjpeg-turbo | unchanged | product | 3 | 0.146526 | 0.144314 | 16400 | 2.23 | 2.23 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.143118 | 0.142350 | 16496 | 2.23 | 2.23 |
| libjpeg-turbo | option-change | product | 3 | 0.158297 | 0.157092 | 16444 | 2.23 | 2.23 |
| libjpeg-turbo | initial | musl | 3 | 0.797501 | 0.803351 | 16996 | 2.23 | 2.23 |
| libjpeg-turbo | unchanged | musl | 3 | 0.147959 | 0.146588 | 15124 | 2.23 | 2.23 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.146820 | 0.143071 | 15124 | 2.23 | 2.23 |
| libjpeg-turbo | option-change | musl | 3 | 0.160483 | 0.159752 | 15188 | 2.23 | 2.23 |
| libjpeg-turbo | initial | product | 4 | 0.801990 | 0.808527 | 18308 | 2.23 | 2.21 |
| libjpeg-turbo | unchanged | product | 4 | 0.146160 | 0.144250 | 16400 | 2.21 | 2.21 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.144773 | 0.143975 | 16372 | 2.21 | 2.21 |
| libjpeg-turbo | option-change | product | 4 | 0.158236 | 0.157492 | 16496 | 2.21 | 2.21 |
| libjpeg-turbo | initial | musl | 4 | 0.805067 | 0.806930 | 16808 | 2.21 | 2.21 |
| libjpeg-turbo | unchanged | musl | 4 | 0.144745 | 0.142550 | 15192 | 2.21 | 2.21 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.144959 | 0.143866 | 15124 | 2.21 | 2.21 |
| libjpeg-turbo | option-change | musl | 4 | 0.158746 | 0.157426 | 15196 | 2.21 | 2.21 |
| libjpeg-turbo | initial | kitware | 4 | 0.729335 | 0.735659 | 17840 | 2.21 | 2.21 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.120305 | 0.115516 | 16356 | 2.21 | 2.21 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.114654 | 0.113191 | 16304 | 2.21 | 2.21 |
| libjpeg-turbo | option-change | kitware | 4 | 0.122494 | 0.121526 | 16380 | 2.21 | 2.21 |
| libjpeg-turbo | initial | musl | 5 | 0.790007 | 0.796748 | 16720 | 2.21 | 2.21 |
| libjpeg-turbo | unchanged | musl | 5 | 0.144105 | 0.143004 | 15192 | 2.21 | 2.21 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.144962 | 0.144103 | 15124 | 2.21 | 2.21 |
| libjpeg-turbo | option-change | musl | 5 | 0.158294 | 0.157583 | 15196 | 2.12 | 2.12 |
| libjpeg-turbo | initial | kitware | 5 | 0.734258 | 0.740901 | 17928 | 2.12 | 2.12 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.115514 | 0.114999 | 16324 | 2.12 | 2.12 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.117560 | 0.115996 | 16276 | 2.12 | 2.12 |
| libjpeg-turbo | option-change | kitware | 5 | 0.119265 | 0.118393 | 16380 | 2.12 | 2.12 |
| libjpeg-turbo | initial | product | 5 | 0.799276 | 0.803368 | 18212 | 2.12 | 2.12 |
| libjpeg-turbo | unchanged | product | 5 | 0.145705 | 0.144729 | 16556 | 2.12 | 2.12 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.147426 | 0.145318 | 16468 | 2.12 | 2.12 |
| libjpeg-turbo | option-change | product | 5 | 0.163394 | 0.160592 | 16444 | 2.12 | 2.12 |
| llvm-clang | initial | product | 1 | 23.562566 | 23.476759 | 491424 | 1.66 | 1.60 |
| llvm-clang | unchanged | product | 1 | 15.651716 | 15.612901 | 480636 | 1.60 | 1.47 |
| llvm-clang | cmakelists-edit | product | 1 | 15.774965 | 15.680383 | 480732 | 1.47 | 1.51 |
| llvm-clang | option-change | product | 1 | 15.924224 | 15.808872 | 480604 | 1.39 | 1.28 |
| llvm-clang | initial | musl | 1 | 23.343716 | 23.367023 | 489196 | 1.28 | 1.20 |
| llvm-clang | unchanged | musl | 1 | 16.055138 | 16.020898 | 478524 | 1.18 | 1.14 |
| llvm-clang | cmakelists-edit | musl | 1 | 15.731718 | 15.613599 | 478676 | 1.14 | 1.11 |
| llvm-clang | option-change | musl | 1 | 16.013228 | 15.888423 | 478572 | 1.08 | 1.21 |
| llvm-clang | initial | kitware | 1 | 20.859883 | 20.901957 | 388448 | 1.19 | 1.21 |
| llvm-clang | unchanged | kitware | 1 | 12.982324 | 12.967407 | 379144 | 1.21 | 1.24 |
| llvm-clang | cmakelists-edit | kitware | 1 | 13.047671 | 12.986141 | 379120 | 1.24 | 1.20 |
| llvm-clang | option-change | kitware | 1 | 13.075326 | 13.004504 | 379164 | 1.15 | 1.12 |
| llvm-clang | initial | musl | 2 | 23.021430 | 23.032583 | 489144 | 1.12 | 1.08 |
| llvm-clang | unchanged | musl | 2 | 15.527311 | 15.478057 | 478516 | 1.16 | 1.26 |
| llvm-clang | cmakelists-edit | musl | 2 | 15.583374 | 15.487546 | 478576 | 1.26 | 1.21 |
| llvm-clang | option-change | musl | 2 | 15.753474 | 15.651800 | 478612 | 1.16 | 1.12 |
| llvm-clang | initial | kitware | 2 | 20.295095 | 20.339459 | 388424 | 1.12 | 1.14 |
| llvm-clang | unchanged | kitware | 2 | 12.996424 | 12.993888 | 379140 | 1.14 | 1.12 |
| llvm-clang | cmakelists-edit | kitware | 2 | 13.373516 | 13.306151 | 379244 | 1.12 | 1.09 |
| llvm-clang | option-change | kitware | 2 | 13.312193 | 13.254737 | 379120 | 1.29 | 1.25 |
| llvm-clang | initial | product | 2 | 24.100489 | 24.100471 | 491260 | 1.23 | 1.16 |
| llvm-clang | unchanged | product | 2 | 16.211318 | 16.178893 | 480576 | 1.15 | 1.11 |
| llvm-clang | cmakelists-edit | product | 2 | 16.242414 | 16.138571 | 480776 | 1.11 | 1.09 |
| llvm-clang | option-change | product | 2 | 16.189822 | 16.080008 | 480660 | 1.07 | 1.13 |
| llvm-clang | initial | kitware | 3 | 20.352711 | 20.395523 | 388520 | 1.13 | 1.16 |
| llvm-clang | unchanged | kitware | 3 | 13.051521 | 13.035016 | 379140 | 1.16 | 1.12 |
| llvm-clang | cmakelists-edit | kitware | 3 | 13.067482 | 13.014674 | 379104 | 1.12 | 1.10 |
| llvm-clang | option-change | kitware | 3 | 13.072249 | 13.005036 | 379204 | 1.08 | 1.06 |
| llvm-clang | initial | product | 3 | 23.209319 | 23.231306 | 491132 | 1.06 | 1.10 |
| llvm-clang | unchanged | product | 3 | 15.721499 | 15.664518 | 480556 | 1.10 | 1.16 |
| llvm-clang | cmakelists-edit | product | 3 | 15.924788 | 15.817933 | 480628 | 1.16 | 1.19 |
| llvm-clang | option-change | product | 3 | 15.660065 | 15.566581 | 480796 | 1.15 | 1.18 |
| llvm-clang | initial | musl | 3 | 23.409204 | 23.424525 | 488968 | 1.18 | 1.24 |
| llvm-clang | unchanged | musl | 3 | 15.712187 | 15.668945 | 478672 | 1.24 | 1.18 |
| llvm-clang | cmakelists-edit | musl | 3 | 15.702523 | 15.615473 | 478512 | 1.18 | 1.14 |
| llvm-clang | option-change | musl | 3 | 15.789036 | 15.687971 | 478664 | 1.27 | 1.21 |
| llvm-clang | initial | product | 4 | 23.677498 | 23.691209 | 491272 | 1.19 | 1.26 |
| llvm-clang | unchanged | product | 4 | 15.718002 | 15.663126 | 480768 | 1.24 | 1.25 |
| llvm-clang | cmakelists-edit | product | 4 | 15.936197 | 15.844328 | 480772 | 1.25 | 1.20 |
| llvm-clang | option-change | product | 4 | 15.960708 | 15.862984 | 480648 | 1.15 | 1.12 |
| llvm-clang | initial | musl | 4 | 24.292984 | 24.279496 | 489084 | 1.19 | 1.27 |
| llvm-clang | unchanged | musl | 4 | 15.931540 | 15.880018 | 478700 | 1.24 | 1.19 |
| llvm-clang | cmakelists-edit | musl | 4 | 15.777059 | 15.700625 | 478564 | 1.19 | 1.15 |
| llvm-clang | option-change | musl | 4 | 15.611674 | 15.506423 | 478624 | 1.11 | 1.09 |
| llvm-clang | initial | kitware | 4 | 20.373030 | 20.412925 | 388456 | 1.08 | 1.12 |
| llvm-clang | unchanged | kitware | 4 | 12.940711 | 12.939895 | 379168 | 1.12 | 1.31 |
| llvm-clang | cmakelists-edit | kitware | 4 | 12.980433 | 12.915835 | 379124 | 1.31 | 1.34 |
| llvm-clang | option-change | kitware | 4 | 12.991884 | 12.936253 | 379112 | 1.26 | 1.22 |
| llvm-clang | initial | musl | 5 | 23.435404 | 23.442085 | 489256 | 1.20 | 1.21 |
| llvm-clang | unchanged | musl | 5 | 16.025829 | 15.972136 | 478660 | 1.19 | 1.15 |
| llvm-clang | cmakelists-edit | musl | 5 | 16.117363 | 16.005578 | 478488 | 1.15 | 1.11 |
| llvm-clang | option-change | musl | 5 | 15.612529 | 15.506412 | 478492 | 1.24 | 1.26 |
| llvm-clang | initial | kitware | 5 | 20.198622 | 20.240064 | 388440 | 1.24 | 1.23 |
| llvm-clang | unchanged | kitware | 5 | 12.888124 | 12.874364 | 379176 | 1.23 | 1.20 |
| llvm-clang | cmakelists-edit | kitware | 5 | 12.984691 | 12.922544 | 379136 | 1.20 | 1.15 |
| llvm-clang | option-change | kitware | 5 | 13.023045 | 12.968350 | 379140 | 1.12 | 1.10 |
| llvm-clang | initial | product | 5 | 23.210633 | 23.224904 | 491328 | 1.10 | 1.35 |
| llvm-clang | unchanged | product | 5 | 15.666305 | 15.618954 | 480768 | 1.35 | 1.48 |
| llvm-clang | cmakelists-edit | product | 5 | 15.753488 | 15.639164 | 480512 | 1.48 | 1.34 |
| llvm-clang | option-change | product | 5 | 15.637720 | 15.550383 | 480824 | 1.26 | 1.21 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 23.04    0.002403           8       283        42 access
 17.84    0.001861           9       204        13 stat
 15.27    0.001593         796         2           wait4
 14.88    0.001552          14       110         4 open
 10.48    0.001093           5       187       179 readlink
  5.83    0.000608          12        49        39 unlink
  5.30    0.000553          10        53         1 lstat
  4.29    0.000447          63         7         2 rename
  2.12    0.000221         110         2           fork
  0.75    0.000078          13         6           chmod
  0.12    0.000013          13         1           chdir
  0.08    0.000008           8         1           getcwd
  0.00    0.000000           0         3           execve
  0.00    0.000000           0         7         6 mkdir
  0.00    0.000000           0         1           rmdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.010430          11       916       286 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 24.95    0.002536           8       283        42 access
 20.22    0.002055          10       204        13 stat
 16.09    0.001635          14       110         4 open
 12.04    0.001224           6       187       179 readlink
  7.29    0.000741          15        49        39 unlink
  5.28    0.000537         268         2           wait4
  5.07    0.000515           9        53         1 lstat
  4.68    0.000476          68         7         2 rename
  1.97    0.000200         100         2           fork
  1.01    0.000103          14         7         6 mkdir
  0.79    0.000080          13         6           chmod
  0.49    0.000050          50         1           rmdir
  0.12    0.000012          12         1           getcwd
  0.00    0.000000           0         3           execve
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.010164          11       916       286 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 37.79    0.003727        1863         2           wait4
 12.59    0.001242           4       284        40 access
 11.46    0.001130           5       204        13 stat
 11.12    0.001097           9       114         6 openat
  5.50    0.000542         180         3           execve
  5.03    0.000496          10        49        39 unlink
  4.44    0.000438          62         7         2 rename
  3.89    0.000384         192         2           clone
  2.91    0.000287           1       187       179 readlink
  2.11    0.000208           3        53         1 lstat
  1.58    0.000156          22         7         1 open
  1.07    0.000106          15         7         6 mkdir
  0.23    0.000023           3         6           chmod
  0.14    0.000014          14         1           getcwd
  0.13    0.000013          13         1           chdir
  0.00    0.000000           0         1           rmdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.009863          10       928       287 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 30.38    0.006468           9       685       211 access
 15.25    0.003248           9       339        28 stat
 13.62    0.002901        1450         2           wait4
 12.23    0.002604           6       385       369 readlink
 10.42    0.002218          13       161         4 open
  5.71    0.001215          12        94        85 unlink
  4.81    0.001024           9       109         9 lstat
  2.49    0.000530          58         9         2 rename
  2.30    0.000490         163         3           execve
  1.86    0.000397         198         2           fork
  0.38    0.000080          11         7         6 mkdir
  0.34    0.000072          14         5           chmod
  0.18    0.000038          38         1           rmdir
  0.04    0.000008           8         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.021293          11      1804       714 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 24.95    0.005043           7       685       211 access
 16.82    0.003401          10       339        28 stat
 15.64    0.003162        1581         2           wait4
 12.26    0.002478           6       385       369 readlink
 11.02    0.002228          13       161         4 open
  5.91    0.001195          10       109         9 lstat
  5.31    0.001073          11        94        85 unlink
  3.22    0.000651         217         3           execve
  2.23    0.000450          50         9         2 rename
  1.45    0.000294         147         2           fork
  0.45    0.000090          12         7         6 mkdir
  0.40    0.000081          16         5           chmod
  0.25    0.000050          50         1           rmdir
  0.05    0.000011          11         1           getcwd
  0.04    0.000009           9         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.020216          11      1804       714 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 26.19    0.003357           4       686       209 access
 15.40    0.001974           5       339        28 stat
 13.23    0.001696         848         2           wait4
 12.49    0.001601           4       378       362 readlink
 11.77    0.001508           9       165         6 openat
  5.91    0.000758           8        94        85 unlink
  5.12    0.000656           6       109         9 lstat
  3.26    0.000418         209         2           clone
  1.90    0.000244          27         9         2 rename
  1.58    0.000203          67         3           execve
  0.94    0.000121          17         7         1 open
  0.75    0.000096          13         7         6 mkdir
  0.47    0.000060          12         5           chmod
  0.41    0.000052          52         1           rmdir
  0.24    0.000031           4         7           faccessat2
  0.23    0.000030          30         1           chdir
  0.09    0.000012          12         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.012817           7      1816       708 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 72.76    0.122184        8727        14         2 wait4
  8.05    0.013519           7      1718      1623 readlink
  5.02    0.008422           9       927       121 stat
  4.07    0.006841           6      1040       451 access
  2.94    0.004944          10       473         7 lstat
  2.53    0.004245          13       308        18 open
  1.37    0.002303          11       200       155 unlink
  1.28    0.002149         165        13           execve
  0.76    0.001284         183         7           fork
  0.48    0.000800          38        21         5 rename
  0.21    0.000347          49         7           clone
  0.20    0.000334          12        27           chmod
  0.10    0.000166           6        25        21 mkdir
  0.08    0.000135          33         4           rmdir
  0.06    0.000097          48         2           vfork
  0.04    0.000073          18         4           openat
  0.04    0.000062           8         7           chdir
  0.02    0.000030          10         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.167935          34      4800      2403 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 76.93    0.118479        8462        14         2 wait4
  5.17    0.007964           4      1718      1623 readlink
  4.38    0.006749           6      1040       451 access
  4.30    0.006621           7       927       121 stat
  2.55    0.003925          12       308        18 open
  2.50    0.003850           8       473         7 lstat
  1.36    0.002099          10       200       155 unlink
  1.05    0.001621         124        13           execve
  0.56    0.000857         122         7           fork
  0.29    0.000444          21        21         5 rename
  0.26    0.000399          57         7           clone
  0.20    0.000308          11        27           chmod
  0.15    0.000236           9        25        21 mkdir
  0.11    0.000166          41         4           rmdir
  0.08    0.000129          64         2           vfork
  0.05    0.000077          19         4           openat
  0.04    0.000064           9         7           chdir
  0.02    0.000030          10         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.154018          32      4800      2403 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 74.96    0.113843        8131        14         2 wait4
  6.64    0.010090           5      1718      1623 readlink
  4.50    0.006829           6      1041       449 access
  4.16    0.006311           6       927       121 stat
  2.31    0.003507           7       473         7 lstat
  1.69    0.002567           9       259        11 openat
  1.38    0.002089          10       200       155 unlink
  1.24    0.001886         145        13           execve
  1.18    0.001798         128        14           clone
  0.75    0.001141          54        21         5 rename
  0.72    0.001098          17        64        10 open
  0.18    0.000270          10        25        21 mkdir
  0.13    0.000204           7        27           chmod
  0.07    0.000104          26         4           rmdir
  0.05    0.000078          11         7           chdir
  0.03    0.000043          21         2           vfork
  0.01    0.000021           7         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.151879          31      4812      2404 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 35.51    2.072922           8    241126      3506 stat
 19.05    1.112020           9    117306        25 lstat
 15.87    0.926469           6    150759    147465 readlink
 12.70    0.741186       11954        62         9 wait4
  6.81    0.397779           5     70886     42409 access
  2.46    0.143339           7     19689     19585 unlink
  2.33    0.136067           9     13777       219 open
  2.19    0.127897        2507        51           execve
  1.96    0.114307        2857        40           fork
  1.05    0.061163          89       682         5 rename
  0.02    0.001152          10       109           chmod
  0.01    0.000860          57        15           clone
  0.01    0.000439           5        80           getcwd
  0.01    0.000404           6        64        54 newfstatat
  0.00    0.000260          10        25        21 mkdir
  0.00    0.000225           5        38           openat
  0.00    0.000165          41         4           rmdir
  0.00    0.000122           8        15           chdir
  0.00    0.000054          10         5           utimensat
  0.00    0.000046          23         2           vfork
  0.00    0.000000           0         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    5.836876           9    614737    213300 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 35.43    2.096789           8    241126      3506 stat
 19.08    1.128984           9    117306        25 lstat
 15.15    0.896461           5    150759    147465 readlink
 13.76    0.814563       13138        62         9 wait4
  6.49    0.383910           5     70886     42409 access
  2.59    0.153427           7     19689     19585 unlink
  2.29    0.135765           9     13777       219 open
  2.18    0.129045        2530        51           execve
  1.94    0.115055        2876        40           fork
  1.02    0.060156          88       682         5 rename
  0.02    0.001183          10       109           chmod
  0.02    0.000901          60        15           clone
  0.01    0.000447           5        80           getcwd
  0.01    0.000418           6        64        54 newfstatat
  0.00    0.000294          11        25        21 mkdir
  0.00    0.000286           7        38           openat
  0.00    0.000167          41         4           rmdir
  0.00    0.000144           9        15           chdir
  0.00    0.000044          22         2           vfork
  0.00    0.000030           6         5           utimensat
  0.00    0.000024          12         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    5.918093           9    614737    213300 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 35.94    2.039461           8    241126      3506 stat
 19.96    1.132671           9    117306        25 lstat
 15.36    0.871615           5    150735    147441 readlink
 13.68    0.776307       12521        62         9 wait4
  6.00    0.340432           4     70889     42403 access
  2.20    0.124859           6     19689     19585 unlink
  2.15    0.121900           9     12763        72 openat
  1.82    0.103064        2020        51           execve
  1.68    0.095136        1729        55           clone
  1.03    0.058272          85       682         5 rename
  0.14    0.008025           7      1085       156 open
  0.02    0.001189          10       109           chmod
  0.01    0.000404           5        80           getcwd
  0.01    0.000386           6        64        54 newfstatat
  0.01    0.000344          13        25        21 mkdir
  0.00    0.000147          36         4           rmdir
  0.00    0.000126           5        24           faccessat2
  0.00    0.000125           8        15           chdir
  0.00    0.000076          38         2           vfork
  0.00    0.000032           6         5           utimensat
  0.00    0.000024          12         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    5.674595           9    614773    213279 total
```
