# ARM64 CMake memory baseline

This run measured the qualified `58313ac` archive to establish the memory
baseline. It does not measure the later section-garbage-collection candidate.

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
Official archive SHA-256: `301d5063ab259577c1b57ce5490b1aab9ea5c56dc4c822f73499553dab94925f`. Baseline output digest: `02bf1ae7092c58fa4398dc6452c605050b7cd27aadc3b11841c3afa76fc22082`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `fe0a382993c36a04a505157b59503a7294db97e2ac9923e5630f8b393b78f118`.
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
| product | 40748528 | 53419267 | 9377384 |
| musl | 23719224 | 35341561 | not packaged |
| kitware | 18976896 | 121223111 | 52041209 |

## Measurements

RSS is CMake's image high-water mark, read before exit; it excludes child processes.
Configure timings include process-tracing overhead. Startup timings are untraced; their RSS
comes from a separate traced invocation. CPU time includes waited child processes.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.026455 | 0.026329–0.027347 | 0.024675 | 13216 |
| fmt | cmakelists-edit | musl | 0.041113 | 0.040273–0.042301 | 0.039260 | 12004 |
| fmt | cmakelists-edit | product | 0.041999 | 0.041675–0.042297 | 0.040099 | 13448 |
| fmt | initial | kitware | 0.176684 | 0.172975–0.178674 | 0.177954 | 14984 |
| fmt | initial | musl | 0.202378 | 0.200014–0.205817 | 0.204376 | 13916 |
| fmt | initial | product | 0.204528 | 0.203431–0.207976 | 0.206272 | 15172 |
| fmt | option-change | kitware | 0.027005 | 0.026698–0.027317 | 0.025016 | 13216 |
| fmt | option-change | musl | 0.041580 | 0.040747–0.042065 | 0.039496 | 12004 |
| fmt | option-change | product | 0.042942 | 0.042290–0.044937 | 0.040776 | 13448 |
| fmt | unchanged | kitware | 0.025966 | 0.025605–0.026189 | 0.024370 | 13264 |
| fmt | unchanged | musl | 0.041037 | 0.040586–0.042159 | 0.039528 | 12004 |
| fmt | unchanged | product | 0.042270 | 0.041531–0.043062 | 0.040626 | 13444 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.093129 | 0.092225–0.095440 | 0.091783 | 14844 |
| libjpeg-turbo | cmakelists-edit | musl | 0.109290 | 0.108132–0.110648 | 0.107972 | 13496 |
| libjpeg-turbo | cmakelists-edit | product | 0.110390 | 0.109971–0.113308 | 0.108835 | 14960 |
| libjpeg-turbo | initial | kitware | 0.606768 | 0.598092–0.615382 | 0.606974 | 16360 |
| libjpeg-turbo | initial | musl | 0.628027 | 0.624833–0.635442 | 0.629527 | 15188 |
| libjpeg-turbo | initial | product | 0.645071 | 0.632843–0.688011 | 0.643938 | 16716 |
| libjpeg-turbo | option-change | kitware | 0.097650 | 0.096137–0.098665 | 0.095468 | 14860 |
| libjpeg-turbo | option-change | musl | 0.117062 | 0.115329–0.118464 | 0.114378 | 13492 |
| libjpeg-turbo | option-change | product | 0.118919 | 0.117790–0.120336 | 0.117053 | 14812 |
| libjpeg-turbo | unchanged | kitware | 0.095091 | 0.093638–0.097745 | 0.092218 | 14844 |
| libjpeg-turbo | unchanged | musl | 0.107929 | 0.107422–0.109237 | 0.107091 | 13612 |
| libjpeg-turbo | unchanged | product | 0.112933 | 0.109194–0.117362 | 0.110178 | 14940 |
| llvm-clang | cmakelists-edit | kitware | 11.044041 | 10.968766–11.303608 | 10.742873 | 505756 |
| llvm-clang | cmakelists-edit | musl | 11.894287 | 11.687262–11.973380 | 11.733694 | 477032 |
| llvm-clang | cmakelists-edit | product | 12.075391 | 11.976254–12.400640 | 11.905563 | 478352 |
| llvm-clang | initial | kitware | 16.974875 | 16.726027–17.429486 | 16.922089 | 514900 |
| llvm-clang | initial | musl | 18.030244 | 17.457400–18.391150 | 17.996161 | 487772 |
| llvm-clang | initial | product | 18.204443 | 17.854463–18.904147 | 18.172372 | 488660 |
| llvm-clang | option-change | kitware | 11.082831 | 10.899352–11.222476 | 10.830812 | 505740 |
| llvm-clang | option-change | musl | 11.748242 | 11.513699–12.364810 | 11.687297 | 476960 |
| llvm-clang | option-change | product | 12.101408 | 11.887872–12.550568 | 11.877807 | 478156 |
| llvm-clang | unchanged | kitware | 10.742300 | 10.718246–11.154346 | 10.737493 | 505744 |
| llvm-clang | unchanged | musl | 11.617274 | 11.529408–12.054405 | 11.608268 | 476932 |
| llvm-clang | unchanged | product | 11.907248 | 11.732730–12.406060 | 11.885639 | 478224 |
| process | script | kitware | 0.002508 | 0.002259–0.002558 | 0.002090 | 9440 |
| process | script | musl | 0.002427 | 0.002221–0.002505 | 0.002009 | 9308 |
| process | script | product | 0.003020 | 0.002923–0.003065 | 0.002566 | 10504 |
| process | version | kitware | 0.002413 | 0.002386–0.002480 | 0.001948 | 8780 |
| process | version | musl | 0.002319 | 0.002231–0.002388 | 0.001920 | 9180 |
| process | version | product | 0.002813 | 0.002722–0.002856 | 0.002384 | 10376 |
| zstd | cmakelists-edit | kitware | 0.039688 | 0.039002–0.043426 | 0.037284 | 13984 |
| zstd | cmakelists-edit | musl | 0.056618 | 0.055253–0.057229 | 0.054329 | 12596 |
| zstd | cmakelists-edit | product | 0.058182 | 0.055668–0.059936 | 0.055140 | 14088 |
| zstd | initial | kitware | 1.020753 | 1.014227–1.027753 | 1.025762 | 16972 |
| zstd | initial | musl | 1.061750 | 1.060941–1.071869 | 1.068430 | 15852 |
| zstd | initial | product | 1.092394 | 1.083089–1.093606 | 1.092853 | 17320 |
| zstd | option-change | kitware | 0.041139 | 0.040225–0.041631 | 0.038540 | 13996 |
| zstd | option-change | musl | 0.057258 | 0.056845–0.059113 | 0.054857 | 12596 |
| zstd | option-change | product | 0.059987 | 0.059143–0.070289 | 0.057737 | 14088 |
| zstd | unchanged | kitware | 0.039297 | 0.038132–0.039670 | 0.037583 | 13988 |
| zstd | unchanged | musl | 0.056638 | 0.055065–0.057453 | 0.055052 | 12596 |
| zstd | unchanged | product | 0.056393 | 0.056179–0.058044 | 0.054759 | 14088 |

## Raw samples

Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.002722 | 0.002256 | 10376 | 1.06 | 1.06 |
| process | script | product | 1 | 0.002942 | 0.002434 | 10504 | 1.06 | 1.06 |
| process | version | musl | 1 | 0.002231 | 0.001756 | 9180 | 1.06 | 1.06 |
| process | script | musl | 1 | 0.002221 | 0.001825 | 9308 | 1.06 | 1.06 |
| process | version | kitware | 1 | 0.002413 | 0.001934 | 8768 | 1.06 | 1.06 |
| process | script | kitware | 1 | 0.002259 | 0.001874 | 9440 | 1.06 | 1.06 |
| process | version | musl | 2 | 0.002319 | 0.001920 | 9180 | 1.06 | 1.06 |
| process | script | musl | 2 | 0.002336 | 0.001949 | 9308 | 1.06 | 1.06 |
| process | version | kitware | 2 | 0.002480 | 0.002046 | 8780 | 1.06 | 1.06 |
| process | script | kitware | 2 | 0.002419 | 0.002005 | 9400 | 1.06 | 1.06 |
| process | version | product | 2 | 0.002856 | 0.002393 | 10376 | 1.06 | 1.06 |
| process | script | product | 2 | 0.002923 | 0.002481 | 10504 | 1.06 | 1.06 |
| process | version | kitware | 3 | 0.002417 | 0.001974 | 8780 | 1.06 | 1.06 |
| process | script | kitware | 3 | 0.002558 | 0.002112 | 9392 | 1.06 | 1.06 |
| process | version | product | 3 | 0.002813 | 0.002377 | 10376 | 1.06 | 1.06 |
| process | script | product | 3 | 0.003065 | 0.002566 | 10504 | 1.06 | 1.06 |
| process | version | musl | 3 | 0.002302 | 0.001872 | 9180 | 1.06 | 1.06 |
| process | script | musl | 3 | 0.002441 | 0.002009 | 9308 | 1.06 | 1.06 |
| process | version | product | 4 | 0.002822 | 0.002384 | 10376 | 1.06 | 1.06 |
| process | script | product | 4 | 0.003038 | 0.002626 | 10504 | 1.06 | 1.06 |
| process | version | musl | 4 | 0.002378 | 0.001922 | 9180 | 1.06 | 1.06 |
| process | script | musl | 4 | 0.002427 | 0.002028 | 9308 | 1.06 | 1.06 |
| process | version | kitware | 4 | 0.002413 | 0.001948 | 8780 | 1.06 | 1.06 |
| process | script | kitware | 4 | 0.002508 | 0.002094 | 9392 | 1.06 | 1.06 |
| process | version | musl | 5 | 0.002388 | 0.001942 | 9180 | 1.06 | 1.06 |
| process | script | musl | 5 | 0.002505 | 0.002028 | 9308 | 1.06 | 1.06 |
| process | version | kitware | 5 | 0.002386 | 0.001944 | 8780 | 1.06 | 1.06 |
| process | script | kitware | 5 | 0.002509 | 0.002090 | 9384 | 1.06 | 1.06 |
| process | version | product | 5 | 0.002808 | 0.002388 | 10376 | 1.06 | 1.06 |
| process | script | product | 5 | 0.003020 | 0.002590 | 10504 | 1.06 | 1.06 |
| fmt | initial | product | 1 | 0.203431 | 0.205263 | 15112 | 1.13 | 1.13 |
| fmt | unchanged | product | 1 | 0.042092 | 0.040577 | 13444 | 1.13 | 1.13 |
| fmt | cmakelists-edit | product | 1 | 0.041801 | 0.039850 | 13440 | 1.13 | 1.13 |
| fmt | option-change | product | 1 | 0.042942 | 0.040776 | 13444 | 1.13 | 1.13 |
| fmt | initial | musl | 1 | 0.205804 | 0.207066 | 13668 | 1.13 | 1.13 |
| fmt | unchanged | musl | 1 | 0.042159 | 0.040427 | 12004 | 1.13 | 1.13 |
| fmt | cmakelists-edit | musl | 1 | 0.042301 | 0.040196 | 11876 | 1.13 | 1.13 |
| fmt | option-change | musl | 1 | 0.042065 | 0.039989 | 12004 | 1.13 | 1.13 |
| fmt | initial | kitware | 1 | 0.172975 | 0.174971 | 14984 | 1.13 | 1.13 |
| fmt | unchanged | kitware | 1 | 0.025605 | 0.024077 | 13240 | 1.13 | 1.13 |
| fmt | cmakelists-edit | kitware | 1 | 0.026393 | 0.024572 | 13216 | 1.13 | 1.13 |
| fmt | option-change | kitware | 1 | 0.027317 | 0.025219 | 13196 | 1.13 | 1.13 |
| fmt | initial | musl | 2 | 0.205817 | 0.205348 | 13796 | 1.13 | 1.13 |
| fmt | unchanged | musl | 2 | 0.041037 | 0.039528 | 12004 | 1.13 | 1.13 |
| fmt | cmakelists-edit | musl | 2 | 0.041082 | 0.039260 | 12004 | 1.13 | 1.13 |
| fmt | option-change | musl | 2 | 0.040747 | 0.038762 | 12004 | 1.13 | 1.13 |
| fmt | initial | kitware | 2 | 0.176164 | 0.177571 | 14980 | 1.13 | 1.13 |
| fmt | unchanged | kitware | 2 | 0.025771 | 0.024327 | 13240 | 1.13 | 1.13 |
| fmt | cmakelists-edit | kitware | 2 | 0.026455 | 0.024675 | 13216 | 1.13 | 1.13 |
| fmt | option-change | kitware | 2 | 0.027005 | 0.025016 | 13200 | 1.13 | 1.13 |
| fmt | initial | product | 2 | 0.207976 | 0.206481 | 15072 | 1.13 | 1.13 |
| fmt | unchanged | product | 2 | 0.043062 | 0.041694 | 13444 | 1.13 | 1.13 |
| fmt | cmakelists-edit | product | 2 | 0.042079 | 0.040150 | 13440 | 1.13 | 1.13 |
| fmt | option-change | product | 2 | 0.042290 | 0.040108 | 13448 | 1.13 | 1.13 |
| fmt | initial | kitware | 3 | 0.176684 | 0.177954 | 14980 | 1.13 | 1.13 |
| fmt | unchanged | kitware | 3 | 0.026145 | 0.024526 | 13264 | 1.13 | 1.13 |
| fmt | cmakelists-edit | kitware | 3 | 0.027347 | 0.025239 | 13196 | 1.13 | 1.13 |
| fmt | option-change | kitware | 3 | 0.027100 | 0.025238 | 13204 | 1.13 | 1.13 |
| fmt | initial | product | 3 | 0.204841 | 0.207736 | 15172 | 1.13 | 1.13 |
| fmt | unchanged | product | 3 | 0.041531 | 0.040035 | 13444 | 1.13 | 1.13 |
| fmt | cmakelists-edit | product | 3 | 0.041675 | 0.039696 | 13448 | 1.13 | 1.13 |
| fmt | option-change | product | 3 | 0.042761 | 0.040579 | 13448 | 1.13 | 1.13 |
| fmt | initial | musl | 3 | 0.201980 | 0.204376 | 13792 | 1.13 | 1.13 |
| fmt | unchanged | musl | 3 | 0.041270 | 0.039801 | 12004 | 1.13 | 1.13 |
| fmt | cmakelists-edit | musl | 3 | 0.042268 | 0.040133 | 12004 | 1.13 | 1.13 |
| fmt | option-change | musl | 3 | 0.041609 | 0.039603 | 12004 | 1.13 | 1.13 |
| fmt | initial | product | 4 | 0.204528 | 0.205328 | 14976 | 1.13 | 1.13 |
| fmt | unchanged | product | 4 | 0.042270 | 0.040626 | 13444 | 1.13 | 1.13 |
| fmt | cmakelists-edit | product | 4 | 0.041999 | 0.040099 | 13440 | 1.13 | 1.13 |
| fmt | option-change | product | 4 | 0.044937 | 0.042637 | 13448 | 1.13 | 1.13 |
| fmt | initial | musl | 4 | 0.200014 | 0.202113 | 13792 | 1.13 | 1.13 |
| fmt | unchanged | musl | 4 | 0.040586 | 0.039048 | 12004 | 1.13 | 1.13 |
| fmt | cmakelists-edit | musl | 4 | 0.040273 | 0.038272 | 12004 | 1.13 | 1.13 |
| fmt | option-change | musl | 4 | 0.040832 | 0.038892 | 12004 | 1.13 | 1.13 |
| fmt | initial | kitware | 4 | 0.177499 | 0.178340 | 14964 | 1.13 | 1.13 |
| fmt | unchanged | kitware | 4 | 0.025966 | 0.024370 | 13264 | 1.13 | 1.13 |
| fmt | cmakelists-edit | kitware | 4 | 0.026745 | 0.024817 | 13200 | 1.13 | 1.13 |
| fmt | option-change | kitware | 4 | 0.026876 | 0.024878 | 13216 | 1.13 | 1.13 |
| fmt | initial | musl | 5 | 0.202378 | 0.204015 | 13916 | 1.13 | 1.13 |
| fmt | unchanged | musl | 5 | 0.040608 | 0.038956 | 12004 | 1.13 | 1.13 |
| fmt | cmakelists-edit | musl | 5 | 0.041113 | 0.039132 | 12004 | 1.13 | 1.13 |
| fmt | option-change | musl | 5 | 0.041580 | 0.039496 | 12004 | 1.13 | 1.13 |
| fmt | initial | kitware | 5 | 0.178674 | 0.178494 | 14964 | 1.13 | 1.13 |
| fmt | unchanged | kitware | 5 | 0.026189 | 0.024631 | 13236 | 1.13 | 1.13 |
| fmt | cmakelists-edit | kitware | 5 | 0.026329 | 0.024512 | 13204 | 1.13 | 1.13 |
| fmt | option-change | kitware | 5 | 0.026698 | 0.024859 | 13216 | 1.13 | 1.13 |
| fmt | initial | product | 5 | 0.204151 | 0.206272 | 15084 | 1.13 | 1.28 |
| fmt | unchanged | product | 5 | 0.042398 | 0.040742 | 13440 | 1.28 | 1.28 |
| fmt | cmakelists-edit | product | 5 | 0.042297 | 0.040167 | 13440 | 1.28 | 1.28 |
| fmt | option-change | product | 5 | 0.043396 | 0.041278 | 13444 | 1.28 | 1.28 |
| zstd | initial | product | 1 | 1.092394 | 1.095794 | 17228 | 1.63 | 1.63 |
| zstd | unchanged | product | 1 | 0.056212 | 0.054490 | 14088 | 1.63 | 1.63 |
| zstd | cmakelists-edit | product | 1 | 0.058924 | 0.056626 | 14068 | 1.63 | 1.63 |
| zstd | option-change | product | 1 | 0.060550 | 0.058177 | 14088 | 1.63 | 1.63 |
| zstd | initial | musl | 1 | 1.060941 | 1.072153 | 15852 | 1.63 | 1.63 |
| zstd | unchanged | musl | 1 | 0.056638 | 0.055125 | 12584 | 1.63 | 1.63 |
| zstd | cmakelists-edit | musl | 1 | 0.056851 | 0.054329 | 12592 | 1.63 | 1.63 |
| zstd | option-change | musl | 1 | 0.059113 | 0.056598 | 12596 | 1.63 | 1.63 |
| zstd | initial | kitware | 1 | 1.026635 | 1.025762 | 16972 | 1.63 | 1.63 |
| zstd | unchanged | kitware | 1 | 0.039041 | 0.037480 | 13988 | 1.63 | 1.63 |
| zstd | cmakelists-edit | kitware | 1 | 0.039002 | 0.036849 | 13984 | 1.63 | 1.63 |
| zstd | option-change | kitware | 1 | 0.040225 | 0.038005 | 13992 | 1.63 | 1.63 |
| zstd | initial | musl | 2 | 1.061189 | 1.068430 | 15792 | 1.63 | 1.66 |
| zstd | unchanged | musl | 2 | 0.056753 | 0.055052 | 12592 | 1.66 | 1.66 |
| zstd | cmakelists-edit | musl | 2 | 0.056618 | 0.054330 | 12596 | 1.66 | 1.66 |
| zstd | option-change | musl | 2 | 0.056929 | 0.054596 | 12596 | 1.66 | 1.66 |
| zstd | initial | kitware | 2 | 1.014227 | 1.019455 | 16968 | 1.66 | 1.66 |
| zstd | unchanged | kitware | 2 | 0.038132 | 0.036554 | 13988 | 1.66 | 1.66 |
| zstd | cmakelists-edit | kitware | 2 | 0.039619 | 0.037284 | 13984 | 1.66 | 1.66 |
| zstd | option-change | kitware | 2 | 0.041139 | 0.038664 | 13992 | 1.66 | 1.66 |
| zstd | initial | product | 2 | 1.083089 | 1.088903 | 17276 | 1.66 | 1.66 |
| zstd | unchanged | product | 2 | 0.057074 | 0.055658 | 14072 | 1.66 | 1.66 |
| zstd | cmakelists-edit | product | 2 | 0.055668 | 0.053289 | 14088 | 1.66 | 1.66 |
| zstd | option-change | product | 2 | 0.059143 | 0.056808 | 14080 | 1.66 | 1.66 |
| zstd | initial | kitware | 3 | 1.019699 | 1.027111 | 16956 | 1.66 | 1.66 |
| zstd | unchanged | kitware | 3 | 0.039670 | 0.038048 | 13988 | 1.66 | 1.66 |
| zstd | cmakelists-edit | kitware | 3 | 0.039688 | 0.037395 | 13984 | 1.66 | 1.66 |
| zstd | option-change | kitware | 3 | 0.041631 | 0.039323 | 13996 | 1.66 | 1.66 |
| zstd | initial | product | 3 | 1.092500 | 1.095652 | 17100 | 1.66 | 1.69 |
| zstd | unchanged | product | 3 | 0.056179 | 0.054638 | 14088 | 1.69 | 1.69 |
| zstd | cmakelists-edit | product | 3 | 0.057576 | 0.055140 | 14088 | 1.69 | 1.69 |
| zstd | option-change | product | 3 | 0.059987 | 0.057652 | 14084 | 1.69 | 1.69 |
| zstd | initial | musl | 3 | 1.061750 | 1.060996 | 15712 | 1.69 | 1.69 |
| zstd | unchanged | musl | 3 | 0.056528 | 0.054948 | 12596 | 1.69 | 1.69 |
| zstd | cmakelists-edit | musl | 3 | 0.057229 | 0.055102 | 12596 | 1.69 | 1.69 |
| zstd | option-change | musl | 3 | 0.058242 | 0.055906 | 12596 | 1.69 | 1.69 |
| zstd | initial | product | 4 | 1.093606 | 1.092853 | 17320 | 1.69 | 1.69 |
| zstd | unchanged | product | 4 | 0.058044 | 0.056356 | 14084 | 1.69 | 1.69 |
| zstd | cmakelists-edit | product | 4 | 0.058182 | 0.056100 | 14088 | 1.69 | 1.69 |
| zstd | option-change | product | 4 | 0.059979 | 0.057737 | 14080 | 1.69 | 1.69 |
| zstd | initial | musl | 4 | 1.071869 | 1.068380 | 15680 | 1.69 | 1.69 |
| zstd | unchanged | musl | 4 | 0.057453 | 0.055282 | 12596 | 1.69 | 1.69 |
| zstd | cmakelists-edit | musl | 4 | 0.056290 | 0.054147 | 12596 | 1.69 | 1.69 |
| zstd | option-change | musl | 4 | 0.057258 | 0.054857 | 12596 | 1.69 | 1.69 |
| zstd | initial | kitware | 4 | 1.027753 | 1.035335 | 16952 | 1.69 | 1.63 |
| zstd | unchanged | kitware | 4 | 0.039297 | 0.037583 | 13972 | 1.63 | 1.63 |
| zstd | cmakelists-edit | kitware | 4 | 0.043426 | 0.037012 | 13984 | 1.63 | 1.63 |
| zstd | option-change | kitware | 4 | 0.040319 | 0.038198 | 13996 | 1.63 | 1.63 |
| zstd | initial | musl | 5 | 1.070739 | 1.074737 | 15704 | 1.63 | 1.63 |
| zstd | unchanged | musl | 5 | 0.055065 | 0.053618 | 12592 | 1.63 | 1.63 |
| zstd | cmakelists-edit | musl | 5 | 0.055253 | 0.052829 | 12580 | 1.63 | 1.63 |
| zstd | option-change | musl | 5 | 0.056845 | 0.054594 | 12580 | 1.63 | 1.63 |
| zstd | initial | kitware | 5 | 1.020753 | 1.025001 | 16960 | 1.63 | 1.63 |
| zstd | unchanged | kitware | 5 | 0.039586 | 0.037978 | 13972 | 1.63 | 1.63 |
| zstd | cmakelists-edit | kitware | 5 | 0.039781 | 0.037463 | 13964 | 1.63 | 1.63 |
| zstd | option-change | kitware | 5 | 0.041139 | 0.038540 | 13992 | 1.63 | 1.63 |
| zstd | initial | product | 5 | 1.089994 | 1.091440 | 17224 | 1.63 | 1.63 |
| zstd | unchanged | product | 5 | 0.056393 | 0.054759 | 14084 | 1.63 | 1.63 |
| zstd | cmakelists-edit | product | 5 | 0.059936 | 0.055098 | 14088 | 1.63 | 1.63 |
| zstd | option-change | product | 5 | 0.070289 | 0.057862 | 14088 | 1.63 | 1.63 |
| libjpeg-turbo | initial | product | 1 | 0.688011 | 0.673371 | 16664 | 2.12 | 2.12 |
| libjpeg-turbo | unchanged | product | 1 | 0.117362 | 0.114898 | 14828 | 2.12 | 2.03 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.112795 | 0.109647 | 14944 | 2.03 | 2.03 |
| libjpeg-turbo | option-change | product | 1 | 0.120336 | 0.116609 | 14812 | 2.03 | 2.03 |
| libjpeg-turbo | initial | musl | 1 | 0.628027 | 0.629527 | 15000 | 2.03 | 2.03 |
| libjpeg-turbo | unchanged | musl | 1 | 0.109237 | 0.107913 | 13612 | 2.03 | 2.03 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.108132 | 0.106732 | 13408 | 2.03 | 2.03 |
| libjpeg-turbo | option-change | musl | 1 | 0.115557 | 0.114268 | 13492 | 2.03 | 2.03 |
| libjpeg-turbo | initial | kitware | 1 | 0.605731 | 0.601985 | 16320 | 2.03 | 2.03 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.095575 | 0.092079 | 14828 | 2.03 | 2.03 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.094097 | 0.091833 | 14840 | 2.03 | 2.03 |
| libjpeg-turbo | option-change | kitware | 1 | 0.096137 | 0.094738 | 14860 | 2.03 | 2.03 |
| libjpeg-turbo | initial | musl | 2 | 0.627877 | 0.628393 | 15188 | 2.03 | 2.03 |
| libjpeg-turbo | unchanged | musl | 2 | 0.107929 | 0.106929 | 13484 | 2.03 | 2.03 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.109151 | 0.106832 | 13488 | 2.03 | 2.03 |
| libjpeg-turbo | option-change | musl | 2 | 0.117601 | 0.114379 | 13492 | 2.03 | 2.03 |
| libjpeg-turbo | initial | kitware | 2 | 0.615382 | 0.606974 | 16304 | 2.03 | 2.03 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.095091 | 0.092630 | 14828 | 2.03 | 2.03 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.092749 | 0.091446 | 14840 | 2.03 | 2.03 |
| libjpeg-turbo | option-change | kitware | 2 | 0.096658 | 0.094746 | 14860 | 2.03 | 2.03 |
| libjpeg-turbo | initial | product | 2 | 0.632843 | 0.637940 | 16644 | 2.03 | 1.95 |
| libjpeg-turbo | unchanged | product | 2 | 0.112933 | 0.110178 | 14940 | 1.95 | 1.95 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.110390 | 0.108835 | 14960 | 1.95 | 1.95 |
| libjpeg-turbo | option-change | product | 2 | 0.120256 | 0.118824 | 14812 | 1.95 | 1.95 |
| libjpeg-turbo | initial | kitware | 3 | 0.606768 | 0.608604 | 16308 | 1.95 | 1.95 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.097745 | 0.093116 | 14844 | 1.95 | 1.95 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.092225 | 0.091174 | 14824 | 1.95 | 1.95 |
| libjpeg-turbo | option-change | kitware | 3 | 0.097898 | 0.095691 | 14840 | 1.95 | 1.95 |
| libjpeg-turbo | initial | product | 3 | 0.633917 | 0.636377 | 16716 | 1.95 | 1.95 |
| libjpeg-turbo | unchanged | product | 3 | 0.109194 | 0.108553 | 14828 | 1.95 | 1.95 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.109971 | 0.107258 | 14944 | 1.95 | 1.95 |
| libjpeg-turbo | option-change | product | 3 | 0.118919 | 0.117053 | 14812 | 1.95 | 1.95 |
| libjpeg-turbo | initial | musl | 3 | 0.624833 | 0.625825 | 15032 | 1.95 | 1.95 |
| libjpeg-turbo | unchanged | musl | 3 | 0.108631 | 0.107164 | 13484 | 1.95 | 1.95 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.110648 | 0.108331 | 13496 | 1.95 | 1.95 |
| libjpeg-turbo | option-change | musl | 3 | 0.115329 | 0.114080 | 13408 | 1.95 | 1.95 |
| libjpeg-turbo | initial | product | 4 | 0.645071 | 0.643938 | 16456 | 1.95 | 1.95 |
| libjpeg-turbo | unchanged | product | 4 | 0.112330 | 0.109857 | 14828 | 1.95 | 1.95 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.110386 | 0.108459 | 14832 | 1.95 | 1.95 |
| libjpeg-turbo | option-change | product | 4 | 0.118436 | 0.117166 | 14812 | 1.87 | 1.87 |
| libjpeg-turbo | initial | musl | 4 | 0.633757 | 0.637114 | 15100 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | musl | 4 | 0.107422 | 0.106492 | 13484 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.109290 | 0.108306 | 13492 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | musl | 4 | 0.118464 | 0.115933 | 13408 | 1.87 | 1.87 |
| libjpeg-turbo | initial | kitware | 4 | 0.598092 | 0.600481 | 16360 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.093638 | 0.092067 | 14844 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.095440 | 0.092048 | 14844 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | kitware | 4 | 0.097650 | 0.095468 | 14860 | 1.87 | 1.87 |
| libjpeg-turbo | initial | musl | 5 | 0.635442 | 0.635480 | 15124 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | musl | 5 | 0.107627 | 0.107091 | 13488 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.109983 | 0.107972 | 13412 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | musl | 5 | 0.117062 | 0.114378 | 13488 | 1.87 | 1.87 |
| libjpeg-turbo | initial | kitware | 5 | 0.615184 | 0.612723 | 16316 | 1.87 | 1.87 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.095003 | 0.092218 | 14840 | 1.87 | 1.87 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.093129 | 0.091783 | 14840 | 1.87 | 1.87 |
| libjpeg-turbo | option-change | kitware | 5 | 0.098665 | 0.096338 | 14860 | 1.87 | 1.87 |
| libjpeg-turbo | initial | product | 5 | 0.646665 | 0.644250 | 16512 | 1.87 | 1.80 |
| libjpeg-turbo | unchanged | product | 5 | 0.114227 | 0.111766 | 14828 | 1.80 | 1.80 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.113308 | 0.112002 | 14948 | 1.80 | 1.80 |
| libjpeg-turbo | option-change | product | 5 | 0.117790 | 0.116487 | 14812 | 1.80 | 1.80 |
| llvm-clang | initial | product | 1 | 18.904147 | 18.206301 | 488240 | 1.96 | 1.69 |
| llvm-clang | unchanged | product | 1 | 12.406060 | 12.117131 | 478224 | 1.69 | 1.58 |
| llvm-clang | cmakelists-edit | product | 1 | 12.400640 | 12.258487 | 478352 | 1.58 | 1.60 |
| llvm-clang | option-change | product | 1 | 12.550568 | 12.159857 | 477944 | 1.51 | 1.47 |
| llvm-clang | initial | musl | 1 | 18.359992 | 18.320297 | 487760 | 1.47 | 1.40 |
| llvm-clang | unchanged | musl | 1 | 12.054405 | 11.916420 | 476792 | 1.40 | 1.33 |
| llvm-clang | cmakelists-edit | musl | 1 | 11.973380 | 11.733694 | 476908 | 1.33 | 1.46 |
| llvm-clang | option-change | musl | 1 | 12.364810 | 12.028210 | 476960 | 1.39 | 1.30 |
| llvm-clang | initial | kitware | 1 | 17.429486 | 17.417262 | 514884 | 1.30 | 1.39 |
| llvm-clang | unchanged | kitware | 1 | 11.154346 | 11.122428 | 505712 | 1.44 | 1.37 |
| llvm-clang | cmakelists-edit | kitware | 1 | 11.303608 | 10.934638 | 505756 | 1.37 | 1.39 |
| llvm-clang | option-change | kitware | 1 | 11.000259 | 10.830812 | 505720 | 1.33 | 1.26 |
| llvm-clang | initial | musl | 2 | 18.391150 | 18.341541 | 487664 | 1.26 | 1.47 |
| llvm-clang | unchanged | musl | 2 | 11.668929 | 11.627950 | 476912 | 1.43 | 1.37 |
| llvm-clang | cmakelists-edit | musl | 2 | 11.921867 | 11.816706 | 477012 | 1.37 | 1.31 |
| llvm-clang | option-change | musl | 2 | 11.904700 | 11.764909 | 476772 | 1.24 | 1.36 |
| llvm-clang | initial | kitware | 2 | 16.977542 | 16.991840 | 514888 | 1.36 | 1.32 |
| llvm-clang | unchanged | kitware | 2 | 10.739181 | 10.737493 | 505744 | 1.32 | 1.27 |
| llvm-clang | cmakelists-edit | kitware | 2 | 10.968766 | 10.673668 | 505740 | 1.27 | 1.23 |
| llvm-clang | option-change | kitware | 2 | 10.899352 | 10.677208 | 505712 | 1.19 | 1.22 |
| llvm-clang | initial | product | 2 | 17.854463 | 17.852327 | 488608 | 1.22 | 1.24 |
| llvm-clang | unchanged | product | 2 | 11.732730 | 11.725661 | 477956 | 1.22 | 1.19 |
| llvm-clang | cmakelists-edit | product | 2 | 12.213030 | 11.834012 | 477984 | 1.19 | 1.16 |
| llvm-clang | option-change | product | 2 | 12.101936 | 11.759817 | 478128 | 1.28 | 1.23 |
| llvm-clang | initial | kitware | 3 | 16.974875 | 16.922089 | 514876 | 1.23 | 1.23 |
| llvm-clang | unchanged | kitware | 3 | 10.764384 | 10.689381 | 505720 | 1.23 | 1.27 |
| llvm-clang | cmakelists-edit | kitware | 3 | 10.999707 | 10.694287 | 505756 | 1.27 | 1.23 |
| llvm-clang | option-change | kitware | 3 | 11.082831 | 10.747676 | 505684 | 1.19 | 1.15 |
| llvm-clang | initial | product | 3 | 18.204443 | 18.172372 | 488660 | 1.15 | 1.10 |
| llvm-clang | unchanged | product | 3 | 11.907248 | 11.885639 | 477952 | 1.10 | 1.09 |
| llvm-clang | cmakelists-edit | product | 3 | 12.002470 | 11.905563 | 477864 | 1.09 | 1.29 |
| llvm-clang | option-change | product | 3 | 12.101408 | 11.877807 | 477984 | 1.25 | 1.21 |
| llvm-clang | initial | musl | 3 | 18.001176 | 17.855090 | 487772 | 1.19 | 1.15 |
| llvm-clang | unchanged | musl | 3 | 11.617274 | 11.608268 | 476772 | 1.15 | 1.11 |
| llvm-clang | cmakelists-edit | musl | 3 | 11.687262 | 11.591228 | 476860 | 1.11 | 1.10 |
| llvm-clang | option-change | musl | 3 | 11.745029 | 11.632051 | 476872 | 1.08 | 1.06 |
| llvm-clang | initial | product | 4 | 18.268633 | 18.253394 | 488652 | 1.06 | 1.20 |
| llvm-clang | unchanged | product | 4 | 11.936825 | 11.898572 | 478096 | 1.20 | 1.24 |
| llvm-clang | cmakelists-edit | product | 4 | 12.075391 | 11.993629 | 478020 | 1.24 | 1.19 |
| llvm-clang | option-change | product | 4 | 11.887872 | 11.782164 | 478156 | 1.16 | 1.13 |
| llvm-clang | initial | musl | 4 | 17.457400 | 17.469670 | 487652 | 1.12 | 1.09 |
| llvm-clang | unchanged | musl | 4 | 11.529408 | 11.486596 | 476900 | 1.09 | 1.07 |
| llvm-clang | cmakelists-edit | musl | 4 | 11.730438 | 11.578148 | 476920 | 1.07 | 1.06 |
| llvm-clang | option-change | musl | 4 | 11.513699 | 11.452433 | 476884 | 1.13 | 1.25 |
| llvm-clang | initial | kitware | 4 | 16.963629 | 16.899133 | 514848 | 1.25 | 1.40 |
| llvm-clang | unchanged | kitware | 4 | 10.742300 | 10.744717 | 505728 | 1.40 | 1.34 |
| llvm-clang | cmakelists-edit | kitware | 4 | 11.208790 | 10.869433 | 505728 | 1.34 | 1.26 |
| llvm-clang | option-change | kitware | 4 | 11.222476 | 10.840919 | 505732 | 1.22 | 1.19 |
| llvm-clang | initial | musl | 5 | 18.030244 | 17.996161 | 487692 | 1.19 | 1.27 |
| llvm-clang | unchanged | musl | 5 | 11.577494 | 11.551879 | 476932 | 1.27 | 1.23 |
| llvm-clang | cmakelists-edit | musl | 5 | 11.894287 | 11.752645 | 477032 | 1.23 | 1.18 |
| llvm-clang | option-change | musl | 5 | 11.748242 | 11.687297 | 476780 | 1.30 | 1.24 |
| llvm-clang | initial | kitware | 5 | 16.726027 | 16.716026 | 514900 | 1.24 | 1.25 |
| llvm-clang | unchanged | kitware | 5 | 10.718246 | 10.716636 | 505716 | 1.25 | 1.21 |
| llvm-clang | cmakelists-edit | kitware | 5 | 11.044041 | 10.742873 | 505744 | 1.21 | 1.25 |
| llvm-clang | option-change | kitware | 5 | 11.100269 | 10.949033 | 505740 | 1.21 | 1.17 |
| llvm-clang | initial | product | 5 | 17.896404 | 17.939205 | 488260 | 1.17 | 1.20 |
| llvm-clang | unchanged | product | 5 | 11.799787 | 11.706849 | 478092 | 1.20 | 1.17 |
| llvm-clang | cmakelists-edit | product | 5 | 11.976254 | 11.865967 | 477868 | 1.17 | 1.27 |
| llvm-clang | option-change | product | 5 | 11.960841 | 11.893232 | 478024 | 1.23 | 1.18 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 20.65    0.001587           6       257        14 newfstatat
 18.81    0.001445           5       283        42 faccessat
 14.97    0.001150         575         2           wait4
 14.76    0.001134          10       110         4 openat
  8.90    0.000684          13        50        39 unlinkat
  6.88    0.000529           2       179       175 readlinkat
  6.05    0.000465          66         7         2 renameat
  3.62    0.000278          92         3           execve
  2.88    0.000221         110         2           clone
  1.42    0.000109          15         7         6 mkdirat
  0.95    0.000073          12         6           fchmodat
  0.12    0.000009           9         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.007684           8       908       282 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 29.77    0.002616        1308         2           wait4
 15.90    0.001397           4       283        42 faccessat
 14.77    0.001298           5       257        14 newfstatat
 13.00    0.001142          10       110         4 openat
  6.76    0.000594         198         3           execve
  6.52    0.000573          11        50        39 unlinkat
  4.46    0.000392          56         7         2 renameat
  3.87    0.000340         170         2           clone
  3.27    0.000287           1       179       175 readlinkat
  1.07    0.000094          13         7         6 mkdirat
  0.52    0.000046           7         6           fchmodat
  0.09    0.000008           8         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.008787           9       908       282 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 29.24    0.002791        1395         2           wait4
 15.53    0.001482           5       284        41 faccessat
 15.09    0.001440           5       257        14 newfstatat
 13.83    0.001320          10       121         7 openat
  7.56    0.000722           4       179       175 readlinkat
  6.57    0.000627          12        50        39 unlinkat
  4.96    0.000473         236         2           clone
  3.30    0.000315         105         3           execve
  2.01    0.000192          27         7         2 renameat
  1.10    0.000105          15         7         6 mkdirat
  0.64    0.000061          10         6           fchmodat
  0.09    0.000009           9         1           getcwd
  0.07    0.000007           7         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.009544          10       920       284 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 24.12    0.003140           4       684       211 faccessat
 20.92    0.002723        1361         2           wait4
 19.25    0.002506           5       446        37 newfstatat
 10.78    0.001403           8       161         4 openat
  7.01    0.000913           2       369       361 readlinkat
  5.27    0.000686           7        95        85 unlinkat
  4.66    0.000606         202         3           execve
  4.61    0.000600          66         9         2 renameat
  3.04    0.000396         198         2           clone
  0.22    0.000028           5         5           fchmodat
  0.07    0.000009           9         1           getcwd
  0.05    0.000007           7         1           chdir
  0.00    0.000000           0         7         6 mkdirat
------ ----------- ----------- --------- --------- ----------------
100.00    0.013017           7      1785       706 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 28.66    0.003684           5       684       211 faccessat
 20.43    0.002626           5       446        37 newfstatat
 13.34    0.001715          10       161         4 openat
 11.19    0.001438           3       369       361 readlinkat
  9.04    0.001162         581         2           wait4
  5.94    0.000763           8        95        85 unlinkat
  4.81    0.000618          68         9         2 renameat
  2.72    0.000350         175         2           clone
  2.62    0.000337         112         3           execve
  0.69    0.000089          12         7         6 mkdirat
  0.49    0.000063          12         5           fchmodat
  0.05    0.000007           7         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.012852           7      1785       706 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 25.93    0.003414        1707         2           wait4
 18.02    0.002372           3       685       210 faccessat
 13.96    0.001838           4       446        37 newfstatat
 10.41    0.001371           7       172         7 openat
  7.57    0.000997           2       362       354 readlinkat
  7.18    0.000945         315         3           execve
  7.09    0.000933         103         9         2 renameat
  6.71    0.000883           9        95        85 unlinkat
  2.07    0.000273         136         2           clone
  0.46    0.000061           8         7         6 mkdirat
  0.24    0.000031           6         5           fchmodat
  0.24    0.000031           4         7           faccessat2
  0.08    0.000010          10         1           getcwd
  0.05    0.000007           7         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.013166           7      1797       701 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 73.88    0.073333        5238        14         2 wait4
  6.43    0.006381           4      1380       112 newfstatat
  5.68    0.005636           3      1632      1580 readlinkat
  4.02    0.003989           3      1040       451 faccessat
  3.10    0.003075           9       312        18 openat
  2.07    0.002059         158        13           execve
  1.85    0.001835         114        16           clone
  1.68    0.001663           8       204       155 unlinkat
  0.78    0.000776          36        21         5 renameat
  0.27    0.000265          10        25        21 mkdirat
  0.15    0.000152           5        27           fchmodat
  0.07    0.000069           9         7           chdir
  0.02    0.000023           7         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.099256          21      4694      2344 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 71.90    0.078616        5615        14         2 wait4
  7.08    0.007746           5      1380       112 newfstatat
  6.21    0.006793           4      1632      1580 readlinkat
  3.74    0.004094           3      1040       451 faccessat
  3.51    0.003841          12       312        18 openat
  2.30    0.002517         193        13           execve
  2.09    0.002286          11       204       155 unlinkat
  1.61    0.001756         109        16           clone
  0.97    0.001063          50        21         5 renameat
  0.28    0.000302          12        25        21 mkdirat
  0.21    0.000230           8        27           fchmodat
  0.06    0.000066           9         7           chdir
  0.02    0.000025           8         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.109335          23      4694      2344 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 76.29    0.078322        5594        14         2 wait4
  5.88    0.006034           4      1380       112 newfstatat
  4.97    0.005098           3      1632      1580 readlinkat
  3.07    0.003150           9       323        21 openat
  2.80    0.002879           2      1041       450 faccessat
  2.17    0.002227         171        13           execve
  1.77    0.001815         113        16           clone
  1.64    0.001685           8       204       155 unlinkat
  0.86    0.000886          42        21         5 renameat
  0.33    0.000343          13        25        21 mkdirat
  0.12    0.000126           4        27           fchmodat
  0.06    0.000061           8         7           chdir
  0.03    0.000031          10         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.102657          21      4706      2346 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 49.31    1.952576           5    358424      3525 newfstatat
 16.89    0.668848       10787        62         9 wait4
 12.44    0.492826           3    147712    145843 readlinkat
  6.59    0.260923           3     70814     42341 faccessat
  4.44    0.175981        3450        51           execve
  3.36    0.133169        2336        57           clone
  2.75    0.108771           7     13815       219 openat
  2.28    0.090200           4     19693     19585 unlinkat
  1.90    0.075350         110       682         5 renameat
  0.02    0.000680           6       109           fchmodat
  0.01    0.000313          12        25        21 mkdirat
  0.01    0.000266           3        80           getcwd
  0.00    0.000099           6        15           chdir
  0.00    0.000024          12         2         2 statfs
  0.00    0.000023           4         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    3.960049           6    611546    211550 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 48.11    1.946520           5    358424      3525 newfstatat
 17.58    0.711372       11473        62         9 wait4
 12.35    0.499622           3    147712    145843 readlinkat
  6.22    0.251454           3     70814     42341 faccessat
  4.76    0.192391        3772        51           execve
  3.56    0.144216        2530        57           clone
  2.89    0.116720           8     13815       219 openat
  2.45    0.099076           5     19693     19585 unlinkat
  2.01    0.081478         119       682         5 renameat
  0.04    0.001683          21        80           getcwd
  0.02    0.000821           7       109           fchmodat
  0.00    0.000139           9        15           chdir
  0.00    0.000108           4        25        21 mkdirat
  0.00    0.000024          12         2         2 statfs
  0.00    0.000020           4         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.045644           6    611546    211550 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 50.21    2.082935           5    358424      3525 newfstatat
 17.30    0.717848       11578        62         9 wait4
 11.19    0.464292           3    147688    145819 readlinkat
  6.43    0.266876           3     70817     42338 faccessat
  4.70    0.195121        3825        51           execve
  3.53    0.146547        2571        57           clone
  2.71    0.112536           8     13848       228 openat
  2.09    0.086893           4     19693     19585 unlinkat
  1.77    0.073375         107       682         5 renameat
  0.02    0.000790           7       109           fchmodat
  0.01    0.000566           7        80           getcwd
  0.01    0.000220           8        25        21 mkdirat
  0.00    0.000163          10        15           chdir
  0.00    0.000063           2        24           faccessat2
  0.00    0.000026          13         2         2 statfs
  0.00    0.000022           4         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    4.148273           6    611582    211532 total
```
