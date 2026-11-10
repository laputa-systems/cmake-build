# CMake executable performance

Target: `aarch64-unknown-linux-musl`. Runs per variant: 5.

All three binaries ran in the same native Debian container with the pinned musl toolchain.
Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource
differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with
OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those
product differences and does not isolate an individual compiler flag.
A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not
measured. Timings are not release gates.

Host: `Linux-7.0.0-1017-azure-aarch64-with-glibc2.39`. CPU: `not reported`. Container: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
CPU affinity: `[0, 1, 2, 3]`. Product archive SHA-256: `66ec96c09705c67adfa83494bf512dc4b7eb5f6cb0f9d706d8499bb460a1c3a8`.
Official archive SHA-256: `301d5063ab259577c1b57ce5490b1aab9ea5c56dc4c822f73499553dab94925f`. Baseline output digest: `27a0f9a7910ee600553796a5b4d5abc8490021c6bdd9195bb202fadc75328728`.
CMake source SHA-256: `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`. Toolchain SHA-256: `fe0a382993c36a04a505157b59503a7294db97e2ac9923e5630f8b393b78f118`.
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
| product | 26534112 | 39204851 | 7571476 |
| musl | 23719224 | 35341561 | not packaged |
| kitware | 18976896 | 121223111 | 52041209 |

## Measurements

RSS is CMake's image high-water mark, read before exit; it excludes child processes.
Configure timings include process-tracing overhead. Startup timings are untraced; their RSS
comes from a separate traced invocation. CPU time includes waited child processes.

| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| fmt | cmakelists-edit | kitware | 0.026845 | 0.026374–0.027581 | 0.025084 | 13216 |
| fmt | cmakelists-edit | musl | 0.041771 | 0.041751–0.043141 | 0.040060 | 12004 |
| fmt | cmakelists-edit | product | 0.041919 | 0.041496–0.043103 | 0.040203 | 11884 |
| fmt | initial | kitware | 0.179899 | 0.177334–0.189704 | 0.179940 | 14984 |
| fmt | initial | musl | 0.204548 | 0.201196–0.213372 | 0.203826 | 13796 |
| fmt | initial | product | 0.206509 | 0.203966–0.207460 | 0.207059 | 13792 |
| fmt | option-change | kitware | 0.027156 | 0.026727–0.027891 | 0.025403 | 13216 |
| fmt | option-change | musl | 0.041828 | 0.041632–0.044170 | 0.040196 | 12004 |
| fmt | option-change | product | 0.042712 | 0.041888–0.044563 | 0.040886 | 11884 |
| fmt | unchanged | kitware | 0.026344 | 0.026044–0.027057 | 0.024929 | 13240 |
| fmt | unchanged | musl | 0.041846 | 0.041592–0.043563 | 0.040481 | 12004 |
| fmt | unchanged | product | 0.042104 | 0.041813–0.043562 | 0.040678 | 11884 |
| libjpeg-turbo | cmakelists-edit | kitware | 0.097180 | 0.094867–0.099066 | 0.094793 | 14840 |
| libjpeg-turbo | cmakelists-edit | musl | 0.113378 | 0.110149–0.115656 | 0.110808 | 13624 |
| libjpeg-turbo | cmakelists-edit | product | 0.115557 | 0.113374–0.116469 | 0.111405 | 13424 |
| libjpeg-turbo | initial | kitware | 0.629569 | 0.619513–0.634884 | 0.627861 | 16320 |
| libjpeg-turbo | initial | musl | 0.643791 | 0.623090–0.676734 | 0.648258 | 15236 |
| libjpeg-turbo | initial | product | 0.657272 | 0.633135–0.663813 | 0.656769 | 15164 |
| libjpeg-turbo | option-change | kitware | 0.099663 | 0.096938–0.102484 | 0.097038 | 14900 |
| libjpeg-turbo | option-change | musl | 0.119347 | 0.117388–0.124130 | 0.116456 | 13508 |
| libjpeg-turbo | option-change | product | 0.121312 | 0.119276–0.125408 | 0.119164 | 13504 |
| libjpeg-turbo | unchanged | kitware | 0.095477 | 0.091658–0.096594 | 0.093615 | 14844 |
| libjpeg-turbo | unchanged | musl | 0.110162 | 0.108597–0.112227 | 0.109824 | 13612 |
| libjpeg-turbo | unchanged | product | 0.113442 | 0.109823–0.114229 | 0.112186 | 13424 |
| llvm-clang | cmakelists-edit | kitware | 10.914878 | 10.632886–11.465229 | 10.864627 | 507188 |
| llvm-clang | cmakelists-edit | musl | 12.057891 | 11.822663–12.405908 | 11.763901 | 477120 |
| llvm-clang | cmakelists-edit | product | 12.097286 | 11.638524–12.389537 | 11.979976 | 477900 |
| llvm-clang | initial | kitware | 17.112790 | 16.484104–17.794604 | 17.148385 | 516284 |
| llvm-clang | initial | musl | 18.092562 | 17.262955–18.578283 | 18.073160 | 487700 |
| llvm-clang | initial | product | 18.305196 | 17.247247–18.780144 | 18.342007 | 488488 |
| llvm-clang | option-change | kitware | 10.792588 | 10.695725–10.960924 | 10.742069 | 507192 |
| llvm-clang | option-change | musl | 11.798747 | 11.452119–12.423752 | 11.732647 | 476996 |
| llvm-clang | option-change | product | 12.052499 | 11.986047–12.237058 | 11.996808 | 477884 |
| llvm-clang | unchanged | kitware | 10.858204 | 10.588241–11.250242 | 10.858556 | 507168 |
| llvm-clang | unchanged | musl | 11.600862 | 11.391049–11.890103 | 11.590891 | 477124 |
| llvm-clang | unchanged | product | 11.926048 | 11.677922–12.298006 | 11.923682 | 477904 |
| process | script | kitware | 0.002419 | 0.002266–0.002517 | 0.002031 | 9400 |
| process | script | musl | 0.002329 | 0.002170–0.002409 | 0.001911 | 9308 |
| process | script | product | 0.002626 | 0.002560–0.002738 | 0.002198 | 9452 |
| process | version | kitware | 0.002382 | 0.002165–0.002518 | 0.001979 | 8784 |
| process | version | musl | 0.002228 | 0.002149–0.002320 | 0.001803 | 9180 |
| process | version | product | 0.002453 | 0.002248–0.002542 | 0.002051 | 9452 |
| zstd | cmakelists-edit | kitware | 0.039516 | 0.038501–0.040298 | 0.037534 | 14024 |
| zstd | cmakelists-edit | musl | 0.055135 | 0.053871–0.056732 | 0.053221 | 12596 |
| zstd | cmakelists-edit | product | 0.056150 | 0.054696–0.059685 | 0.054279 | 12628 |
| zstd | initial | kitware | 1.004032 | 0.986033–1.019832 | 1.004050 | 16972 |
| zstd | initial | musl | 1.047344 | 1.029890–1.100731 | 1.048860 | 15888 |
| zstd | initial | product | 1.075382 | 1.057259–1.082994 | 1.082385 | 15844 |
| zstd | option-change | kitware | 0.040773 | 0.039370–0.041430 | 0.038560 | 13996 |
| zstd | option-change | musl | 0.056481 | 0.055633–0.057983 | 0.054380 | 12596 |
| zstd | option-change | product | 0.057595 | 0.057291–0.059817 | 0.055574 | 12628 |
| zstd | unchanged | kitware | 0.039113 | 0.037698–0.039258 | 0.037694 | 14012 |
| zstd | unchanged | musl | 0.055954 | 0.053897–0.056989 | 0.054516 | 12596 |
| zstd | unchanged | product | 0.057012 | 0.056590–0.057604 | 0.055562 | 12684 |

## Raw samples

Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.

| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| process | version | product | 1 | 0.002248 | 0.001922 | 9452 | 1.05 | 1.05 |
| process | script | product | 1 | 0.002626 | 0.002198 | 9452 | 1.05 | 1.05 |
| process | version | musl | 1 | 0.002275 | 0.001858 | 9180 | 1.05 | 1.05 |
| process | script | musl | 1 | 0.002329 | 0.001911 | 9308 | 1.05 | 1.05 |
| process | version | kitware | 1 | 0.002382 | 0.001972 | 8780 | 1.05 | 1.05 |
| process | script | kitware | 1 | 0.002389 | 0.001969 | 9384 | 1.05 | 1.05 |
| process | version | musl | 2 | 0.002228 | 0.001803 | 9180 | 1.05 | 1.05 |
| process | script | musl | 2 | 0.002209 | 0.001815 | 9308 | 1.05 | 1.05 |
| process | version | kitware | 2 | 0.002399 | 0.001979 | 8780 | 1.05 | 1.05 |
| process | script | kitware | 2 | 0.002451 | 0.002031 | 9400 | 1.05 | 1.05 |
| process | version | product | 2 | 0.002542 | 0.002130 | 9452 | 1.05 | 1.05 |
| process | script | product | 2 | 0.002738 | 0.002299 | 9452 | 1.05 | 1.05 |
| process | version | kitware | 3 | 0.002518 | 0.002058 | 8780 | 1.05 | 1.05 |
| process | script | kitware | 3 | 0.002517 | 0.002115 | 9400 | 1.05 | 1.05 |
| process | version | product | 3 | 0.002532 | 0.002102 | 9452 | 1.05 | 1.05 |
| process | script | product | 3 | 0.002679 | 0.002276 | 9452 | 1.05 | 1.05 |
| process | version | musl | 3 | 0.002320 | 0.001914 | 9180 | 1.05 | 1.05 |
| process | script | musl | 3 | 0.002409 | 0.001968 | 9308 | 1.05 | 1.05 |
| process | version | product | 4 | 0.002453 | 0.002051 | 9452 | 1.05 | 1.05 |
| process | script | product | 4 | 0.002560 | 0.002140 | 9452 | 1.05 | 1.05 |
| process | version | musl | 4 | 0.002197 | 0.001800 | 9180 | 1.05 | 1.05 |
| process | script | musl | 4 | 0.002345 | 0.001941 | 9308 | 1.05 | 1.05 |
| process | version | kitware | 4 | 0.002365 | 0.002003 | 8780 | 1.05 | 1.05 |
| process | script | kitware | 4 | 0.002419 | 0.002036 | 9400 | 1.05 | 1.05 |
| process | version | musl | 5 | 0.002149 | 0.001764 | 9180 | 1.05 | 1.05 |
| process | script | musl | 5 | 0.002170 | 0.001772 | 9308 | 1.05 | 1.05 |
| process | version | kitware | 5 | 0.002165 | 0.001816 | 8784 | 1.05 | 1.05 |
| process | script | kitware | 5 | 0.002266 | 0.001919 | 9400 | 1.05 | 1.05 |
| process | version | product | 5 | 0.002435 | 0.002035 | 9452 | 1.05 | 1.05 |
| process | script | product | 5 | 0.002576 | 0.002160 | 9452 | 1.05 | 1.05 |
| fmt | initial | product | 1 | 0.203966 | 0.204784 | 13664 | 1.05 | 1.05 |
| fmt | unchanged | product | 1 | 0.043562 | 0.042190 | 11884 | 1.05 | 1.05 |
| fmt | cmakelists-edit | product | 1 | 0.042381 | 0.040631 | 11884 | 1.05 | 1.05 |
| fmt | option-change | product | 1 | 0.042295 | 0.040645 | 11884 | 1.05 | 1.05 |
| fmt | initial | musl | 1 | 0.204548 | 0.203826 | 13796 | 1.05 | 1.05 |
| fmt | unchanged | musl | 1 | 0.041891 | 0.040481 | 11876 | 1.05 | 1.05 |
| fmt | cmakelists-edit | musl | 1 | 0.042154 | 0.040177 | 12004 | 1.05 | 1.05 |
| fmt | option-change | musl | 1 | 0.044170 | 0.042376 | 12004 | 1.05 | 1.05 |
| fmt | initial | kitware | 1 | 0.189704 | 0.189901 | 14976 | 1.05 | 1.05 |
| fmt | unchanged | kitware | 1 | 0.027057 | 0.025584 | 13236 | 1.05 | 1.05 |
| fmt | cmakelists-edit | kitware | 1 | 0.027581 | 0.025907 | 13208 | 1.05 | 1.05 |
| fmt | option-change | kitware | 1 | 0.027891 | 0.025979 | 13216 | 1.05 | 1.05 |
| fmt | initial | musl | 2 | 0.213372 | 0.212771 | 13752 | 1.05 | 1.05 |
| fmt | unchanged | musl | 2 | 0.043563 | 0.042026 | 12004 | 1.05 | 1.05 |
| fmt | cmakelists-edit | musl | 2 | 0.043141 | 0.041358 | 12004 | 1.05 | 1.05 |
| fmt | option-change | musl | 2 | 0.043124 | 0.041124 | 12004 | 1.05 | 1.05 |
| fmt | initial | kitware | 2 | 0.186509 | 0.185593 | 14964 | 1.05 | 1.05 |
| fmt | unchanged | kitware | 2 | 0.026044 | 0.024666 | 13236 | 1.05 | 1.05 |
| fmt | cmakelists-edit | kitware | 2 | 0.026845 | 0.025084 | 13212 | 1.05 | 1.05 |
| fmt | option-change | kitware | 2 | 0.027156 | 0.025403 | 13200 | 1.05 | 1.05 |
| fmt | initial | product | 2 | 0.206509 | 0.207059 | 13672 | 1.05 | 1.05 |
| fmt | unchanged | product | 2 | 0.042104 | 0.040678 | 11884 | 1.05 | 1.05 |
| fmt | cmakelists-edit | product | 2 | 0.041496 | 0.039682 | 11884 | 1.05 | 1.05 |
| fmt | option-change | product | 2 | 0.043246 | 0.041455 | 11884 | 1.05 | 1.05 |
| fmt | initial | kitware | 3 | 0.179899 | 0.179940 | 14960 | 1.05 | 1.05 |
| fmt | unchanged | kitware | 3 | 0.026344 | 0.024929 | 13240 | 1.05 | 1.05 |
| fmt | cmakelists-edit | kitware | 3 | 0.026374 | 0.024815 | 13200 | 1.05 | 1.05 |
| fmt | option-change | kitware | 3 | 0.027081 | 0.025184 | 13196 | 1.05 | 1.05 |
| fmt | initial | product | 3 | 0.204867 | 0.205027 | 13528 | 1.05 | 1.05 |
| fmt | unchanged | product | 3 | 0.041920 | 0.040578 | 11884 | 1.05 | 1.05 |
| fmt | cmakelists-edit | product | 3 | 0.041919 | 0.040203 | 11884 | 1.05 | 1.05 |
| fmt | option-change | product | 3 | 0.044563 | 0.042499 | 11884 | 1.05 | 1.05 |
| fmt | initial | musl | 3 | 0.210831 | 0.211058 | 13752 | 1.05 | 1.05 |
| fmt | unchanged | musl | 3 | 0.041785 | 0.040288 | 12004 | 1.05 | 1.05 |
| fmt | cmakelists-edit | musl | 3 | 0.041771 | 0.040060 | 12004 | 1.05 | 1.05 |
| fmt | option-change | musl | 3 | 0.041828 | 0.040196 | 12004 | 1.05 | 1.05 |
| fmt | initial | product | 4 | 0.206819 | 0.207223 | 13792 | 1.05 | 1.05 |
| fmt | unchanged | product | 4 | 0.042777 | 0.041291 | 11884 | 1.05 | 1.05 |
| fmt | cmakelists-edit | product | 4 | 0.043103 | 0.041425 | 11884 | 1.05 | 1.05 |
| fmt | option-change | product | 4 | 0.041888 | 0.040085 | 11884 | 1.05 | 1.05 |
| fmt | initial | musl | 4 | 0.204267 | 0.203749 | 13788 | 1.05 | 1.05 |
| fmt | unchanged | musl | 4 | 0.041846 | 0.040503 | 12004 | 1.05 | 1.05 |
| fmt | cmakelists-edit | musl | 4 | 0.041757 | 0.039984 | 12004 | 1.05 | 1.05 |
| fmt | option-change | musl | 4 | 0.041632 | 0.039979 | 12004 | 1.05 | 1.05 |
| fmt | initial | kitware | 4 | 0.177354 | 0.177454 | 14984 | 1.05 | 1.05 |
| fmt | unchanged | kitware | 4 | 0.026298 | 0.024836 | 13240 | 1.05 | 1.05 |
| fmt | cmakelists-edit | kitware | 4 | 0.026727 | 0.025021 | 13212 | 1.05 | 1.05 |
| fmt | option-change | kitware | 4 | 0.026727 | 0.025006 | 13216 | 1.05 | 1.05 |
| fmt | initial | musl | 5 | 0.201196 | 0.202141 | 13728 | 1.05 | 1.05 |
| fmt | unchanged | musl | 5 | 0.041592 | 0.040238 | 12004 | 1.05 | 1.05 |
| fmt | cmakelists-edit | musl | 5 | 0.041751 | 0.040017 | 11876 | 1.05 | 1.05 |
| fmt | option-change | musl | 5 | 0.041793 | 0.039973 | 11876 | 1.05 | 1.05 |
| fmt | initial | kitware | 5 | 0.177334 | 0.176931 | 14972 | 1.05 | 1.05 |
| fmt | unchanged | kitware | 5 | 0.026427 | 0.024968 | 13240 | 1.05 | 1.05 |
| fmt | cmakelists-edit | kitware | 5 | 0.027042 | 0.025381 | 13216 | 1.05 | 1.05 |
| fmt | option-change | kitware | 5 | 0.027391 | 0.025667 | 13216 | 1.05 | 1.05 |
| fmt | initial | product | 5 | 0.207460 | 0.207733 | 13676 | 1.05 | 1.05 |
| fmt | unchanged | product | 5 | 0.041813 | 0.040385 | 11884 | 1.05 | 1.05 |
| fmt | cmakelists-edit | product | 5 | 0.041530 | 0.039814 | 11884 | 1.05 | 1.05 |
| fmt | option-change | product | 5 | 0.042712 | 0.040886 | 11884 | 1.05 | 1.05 |
| zstd | initial | product | 1 | 1.082994 | 1.082385 | 15724 | 1.11 | 1.11 |
| zstd | unchanged | product | 1 | 0.057027 | 0.055644 | 12684 | 1.11 | 1.11 |
| zstd | cmakelists-edit | product | 1 | 0.055919 | 0.054011 | 12628 | 1.11 | 1.11 |
| zstd | option-change | product | 1 | 0.057595 | 0.055433 | 12628 | 1.11 | 1.11 |
| zstd | initial | musl | 1 | 1.047344 | 1.048860 | 15716 | 1.11 | 1.11 |
| zstd | unchanged | musl | 1 | 0.054993 | 0.053636 | 12592 | 1.11 | 1.11 |
| zstd | cmakelists-edit | musl | 1 | 0.055135 | 0.053221 | 12592 | 1.11 | 1.11 |
| zstd | option-change | musl | 1 | 0.055633 | 0.053597 | 12596 | 1.11 | 1.10 |
| zstd | initial | kitware | 1 | 1.017555 | 1.017775 | 16972 | 1.10 | 1.10 |
| zstd | unchanged | kitware | 1 | 0.039208 | 0.037694 | 13984 | 1.10 | 1.10 |
| zstd | cmakelists-edit | kitware | 1 | 0.039734 | 0.037794 | 14024 | 1.10 | 1.10 |
| zstd | option-change | kitware | 1 | 0.040773 | 0.038560 | 13996 | 1.10 | 1.10 |
| zstd | initial | musl | 2 | 1.057000 | 1.061353 | 15828 | 1.10 | 1.10 |
| zstd | unchanged | musl | 2 | 0.055954 | 0.054516 | 12592 | 1.10 | 1.10 |
| zstd | cmakelists-edit | musl | 2 | 0.055976 | 0.053907 | 12592 | 1.10 | 1.10 |
| zstd | option-change | musl | 2 | 0.056481 | 0.054380 | 12596 | 1.10 | 1.10 |
| zstd | initial | kitware | 2 | 1.004032 | 1.004050 | 16972 | 1.10 | 1.10 |
| zstd | unchanged | kitware | 2 | 0.039113 | 0.037696 | 13988 | 1.10 | 1.10 |
| zstd | cmakelists-edit | kitware | 2 | 0.039516 | 0.037534 | 13980 | 1.10 | 1.10 |
| zstd | option-change | kitware | 2 | 0.040187 | 0.038189 | 13980 | 1.10 | 1.10 |
| zstd | initial | product | 2 | 1.079061 | 1.086171 | 15844 | 1.10 | 1.10 |
| zstd | unchanged | product | 2 | 0.057012 | 0.055562 | 12628 | 1.10 | 1.10 |
| zstd | cmakelists-edit | product | 2 | 0.056757 | 0.054575 | 12624 | 1.10 | 1.10 |
| zstd | option-change | product | 2 | 0.057535 | 0.055574 | 12612 | 1.10 | 1.09 |
| zstd | initial | kitware | 3 | 1.019832 | 1.014948 | 16968 | 1.09 | 1.09 |
| zstd | unchanged | kitware | 3 | 0.039258 | 0.037889 | 13976 | 1.09 | 1.09 |
| zstd | cmakelists-edit | kitware | 3 | 0.039254 | 0.037474 | 13968 | 1.09 | 1.09 |
| zstd | option-change | kitware | 3 | 0.041084 | 0.038906 | 13996 | 1.09 | 1.09 |
| zstd | initial | product | 3 | 1.067541 | 1.072380 | 15832 | 1.09 | 1.09 |
| zstd | unchanged | product | 3 | 0.056793 | 0.055311 | 12628 | 1.09 | 1.09 |
| zstd | cmakelists-edit | product | 3 | 0.056150 | 0.054279 | 12628 | 1.09 | 1.09 |
| zstd | option-change | product | 3 | 0.057291 | 0.055345 | 12628 | 1.09 | 1.09 |
| zstd | initial | musl | 3 | 1.100731 | 1.107197 | 15888 | 1.09 | 1.09 |
| zstd | unchanged | musl | 3 | 0.056596 | 0.055188 | 12584 | 1.09 | 1.09 |
| zstd | cmakelists-edit | musl | 3 | 0.056732 | 0.054784 | 12584 | 1.09 | 1.09 |
| zstd | option-change | musl | 3 | 0.057181 | 0.055120 | 12596 | 1.09 | 1.09 |
| zstd | initial | product | 4 | 1.057259 | 1.061801 | 15644 | 1.09 | 1.09 |
| zstd | unchanged | product | 4 | 0.056590 | 0.055244 | 12628 | 1.09 | 1.09 |
| zstd | cmakelists-edit | product | 4 | 0.054696 | 0.052922 | 12628 | 1.09 | 1.09 |
| zstd | option-change | product | 4 | 0.057879 | 0.055977 | 12628 | 1.09 | 1.09 |
| zstd | initial | musl | 4 | 1.029890 | 1.034871 | 15688 | 1.09 | 1.09 |
| zstd | unchanged | musl | 4 | 0.053897 | 0.052507 | 12596 | 1.09 | 1.09 |
| zstd | cmakelists-edit | musl | 4 | 0.053871 | 0.051945 | 12580 | 1.09 | 1.09 |
| zstd | option-change | musl | 4 | 0.057983 | 0.056062 | 12584 | 1.09 | 1.09 |
| zstd | initial | kitware | 4 | 0.986033 | 0.987509 | 16972 | 1.09 | 1.09 |
| zstd | unchanged | kitware | 4 | 0.038118 | 0.036632 | 14012 | 1.09 | 1.09 |
| zstd | cmakelists-edit | kitware | 4 | 0.038501 | 0.036656 | 13968 | 1.09 | 1.09 |
| zstd | option-change | kitware | 4 | 0.039370 | 0.037675 | 13976 | 1.09 | 1.09 |
| zstd | initial | musl | 5 | 1.040739 | 1.048601 | 15760 | 1.09 | 1.09 |
| zstd | unchanged | musl | 5 | 0.056989 | 0.055557 | 12592 | 1.09 | 1.09 |
| zstd | cmakelists-edit | musl | 5 | 0.055066 | 0.053080 | 12596 | 1.09 | 1.09 |
| zstd | option-change | musl | 5 | 0.056272 | 0.054217 | 12592 | 1.09 | 1.09 |
| zstd | initial | kitware | 5 | 1.000381 | 1.001592 | 16960 | 1.09 | 1.09 |
| zstd | unchanged | kitware | 5 | 0.037698 | 0.036376 | 13988 | 1.09 | 1.09 |
| zstd | cmakelists-edit | kitware | 5 | 0.040298 | 0.038357 | 13964 | 1.09 | 1.09 |
| zstd | option-change | kitware | 5 | 0.041430 | 0.039313 | 13996 | 1.09 | 1.08 |
| zstd | initial | product | 5 | 1.075382 | 1.083300 | 15712 | 1.08 | 1.08 |
| zstd | unchanged | product | 5 | 0.057604 | 0.056071 | 12616 | 1.08 | 1.08 |
| zstd | cmakelists-edit | product | 5 | 0.059685 | 0.057817 | 12616 | 1.08 | 1.08 |
| zstd | option-change | product | 5 | 0.059817 | 0.057766 | 12616 | 1.08 | 1.08 |
| libjpeg-turbo | initial | product | 1 | 0.633135 | 0.633573 | 15120 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | product | 1 | 0.109823 | 0.109336 | 13424 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | product | 1 | 0.115210 | 0.111405 | 13400 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | product | 1 | 0.119276 | 0.116155 | 13424 | 1.83 | 1.83 |
| libjpeg-turbo | initial | musl | 1 | 0.623090 | 0.625859 | 15236 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | musl | 1 | 0.108597 | 0.106933 | 13484 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | musl | 1 | 0.110149 | 0.107719 | 13372 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | musl | 1 | 0.117388 | 0.114579 | 13412 | 1.83 | 1.83 |
| libjpeg-turbo | initial | kitware | 1 | 0.620326 | 0.619242 | 16320 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | kitware | 1 | 0.091658 | 0.091122 | 14828 | 1.83 | 1.83 |
| libjpeg-turbo | cmakelists-edit | kitware | 1 | 0.094867 | 0.092308 | 14836 | 1.83 | 1.83 |
| libjpeg-turbo | option-change | kitware | 1 | 0.099663 | 0.097038 | 14860 | 1.83 | 1.83 |
| libjpeg-turbo | initial | musl | 2 | 0.639903 | 0.641190 | 15076 | 1.83 | 1.83 |
| libjpeg-turbo | unchanged | musl | 2 | 0.110323 | 0.110023 | 13416 | 1.83 | 2.16 |
| libjpeg-turbo | cmakelists-edit | musl | 2 | 0.114077 | 0.111528 | 13624 | 2.16 | 2.16 |
| libjpeg-turbo | option-change | musl | 2 | 0.119347 | 0.116456 | 13404 | 2.16 | 2.16 |
| libjpeg-turbo | initial | kitware | 2 | 0.619513 | 0.614978 | 16320 | 2.16 | 2.16 |
| libjpeg-turbo | unchanged | kitware | 2 | 0.096140 | 0.093541 | 14824 | 2.16 | 2.16 |
| libjpeg-turbo | cmakelists-edit | kitware | 2 | 0.094983 | 0.094013 | 14840 | 2.16 | 2.16 |
| libjpeg-turbo | option-change | kitware | 2 | 0.096938 | 0.095948 | 14860 | 2.16 | 2.16 |
| libjpeg-turbo | initial | product | 2 | 0.652288 | 0.655317 | 15076 | 2.16 | 2.16 |
| libjpeg-turbo | unchanged | product | 2 | 0.113313 | 0.112186 | 13424 | 2.16 | 2.16 |
| libjpeg-turbo | cmakelists-edit | product | 2 | 0.115557 | 0.112185 | 13396 | 2.16 | 2.16 |
| libjpeg-turbo | option-change | product | 2 | 0.121290 | 0.118832 | 13376 | 2.16 | 2.16 |
| libjpeg-turbo | initial | kitware | 3 | 0.631269 | 0.630180 | 16308 | 2.16 | 2.16 |
| libjpeg-turbo | unchanged | kitware | 3 | 0.096594 | 0.094419 | 14828 | 2.16 | 2.16 |
| libjpeg-turbo | cmakelists-edit | kitware | 3 | 0.097180 | 0.096246 | 14840 | 2.16 | 2.16 |
| libjpeg-turbo | option-change | kitware | 3 | 0.097782 | 0.096783 | 14860 | 2.16 | 2.16 |
| libjpeg-turbo | initial | product | 3 | 0.657272 | 0.656769 | 14996 | 2.16 | 2.16 |
| libjpeg-turbo | unchanged | product | 3 | 0.113442 | 0.112063 | 13392 | 2.16 | 2.16 |
| libjpeg-turbo | cmakelists-edit | product | 3 | 0.116216 | 0.111049 | 13396 | 2.16 | 2.16 |
| libjpeg-turbo | option-change | product | 3 | 0.121312 | 0.119164 | 13504 | 2.16 | 2.16 |
| libjpeg-turbo | initial | musl | 3 | 0.643791 | 0.648258 | 15128 | 2.16 | 2.15 |
| libjpeg-turbo | unchanged | musl | 3 | 0.110162 | 0.109824 | 13492 | 2.15 | 2.15 |
| libjpeg-turbo | cmakelists-edit | musl | 3 | 0.113378 | 0.110650 | 13536 | 2.15 | 2.15 |
| libjpeg-turbo | option-change | musl | 3 | 0.118841 | 0.115921 | 13508 | 2.15 | 2.15 |
| libjpeg-turbo | initial | product | 4 | 0.659767 | 0.658532 | 15076 | 2.15 | 2.15 |
| libjpeg-turbo | unchanged | product | 4 | 0.113890 | 0.113346 | 13392 | 2.15 | 2.15 |
| libjpeg-turbo | cmakelists-edit | product | 4 | 0.116469 | 0.113668 | 13424 | 2.15 | 2.15 |
| libjpeg-turbo | option-change | product | 4 | 0.125408 | 0.123285 | 13376 | 2.15 | 2.15 |
| libjpeg-turbo | initial | musl | 4 | 0.676734 | 0.674778 | 15124 | 2.15 | 2.15 |
| libjpeg-turbo | unchanged | musl | 4 | 0.112227 | 0.110979 | 13612 | 2.15 | 2.15 |
| libjpeg-turbo | cmakelists-edit | musl | 4 | 0.112908 | 0.110808 | 13412 | 2.15 | 2.15 |
| libjpeg-turbo | option-change | musl | 4 | 0.123266 | 0.119283 | 13412 | 2.15 | 2.15 |
| libjpeg-turbo | initial | kitware | 4 | 0.634884 | 0.634261 | 16316 | 2.15 | 2.15 |
| libjpeg-turbo | unchanged | kitware | 4 | 0.094336 | 0.093950 | 14844 | 2.15 | 2.15 |
| libjpeg-turbo | cmakelists-edit | kitware | 4 | 0.097854 | 0.094793 | 14824 | 2.15 | 2.15 |
| libjpeg-turbo | option-change | kitware | 4 | 0.100612 | 0.097269 | 14860 | 2.15 | 2.15 |
| libjpeg-turbo | initial | musl | 5 | 0.655925 | 0.655403 | 14988 | 2.15 | 2.15 |
| libjpeg-turbo | unchanged | musl | 5 | 0.109203 | 0.108982 | 13484 | 2.15 | 2.22 |
| libjpeg-turbo | cmakelists-edit | musl | 5 | 0.115656 | 0.112070 | 13544 | 2.22 | 2.22 |
| libjpeg-turbo | option-change | musl | 5 | 0.124130 | 0.118112 | 13496 | 2.22 | 2.22 |
| libjpeg-turbo | initial | kitware | 5 | 0.629569 | 0.627861 | 16304 | 2.22 | 2.22 |
| libjpeg-turbo | unchanged | kitware | 5 | 0.095477 | 0.093615 | 14844 | 2.22 | 2.22 |
| libjpeg-turbo | cmakelists-edit | kitware | 5 | 0.099066 | 0.096141 | 14820 | 2.22 | 2.22 |
| libjpeg-turbo | option-change | kitware | 5 | 0.102484 | 0.098603 | 14900 | 2.22 | 2.22 |
| libjpeg-turbo | initial | product | 5 | 0.663813 | 0.660344 | 15164 | 2.22 | 2.22 |
| libjpeg-turbo | unchanged | product | 5 | 0.114229 | 0.113883 | 13392 | 2.22 | 2.22 |
| libjpeg-turbo | cmakelists-edit | product | 5 | 0.113374 | 0.111158 | 13396 | 2.22 | 2.22 |
| libjpeg-turbo | option-change | product | 5 | 0.125014 | 0.121007 | 13424 | 2.22 | 2.22 |
| llvm-clang | initial | product | 1 | 18.450211 | 18.342007 | 488308 | 1.85 | 1.82 |
| llvm-clang | unchanged | product | 1 | 12.183309 | 12.006506 | 477764 | 1.82 | 1.71 |
| llvm-clang | cmakelists-edit | product | 1 | 12.294007 | 11.979976 | 477784 | 1.71 | 1.60 |
| llvm-clang | option-change | product | 1 | 12.052499 | 12.003272 | 477884 | 1.47 | 1.40 |
| llvm-clang | initial | musl | 1 | 18.578283 | 18.599615 | 487700 | 1.40 | 1.44 |
| llvm-clang | unchanged | musl | 1 | 11.890103 | 11.892381 | 477124 | 1.44 | 1.41 |
| llvm-clang | cmakelists-edit | musl | 1 | 12.062378 | 11.926847 | 477000 | 1.41 | 1.35 |
| llvm-clang | option-change | musl | 1 | 11.870687 | 11.803785 | 476996 | 1.29 | 1.23 |
| llvm-clang | initial | kitware | 1 | 16.992387 | 17.031054 | 516268 | 1.23 | 1.24 |
| llvm-clang | unchanged | kitware | 1 | 11.109021 | 11.028365 | 507140 | 1.22 | 1.19 |
| llvm-clang | cmakelists-edit | kitware | 1 | 11.465229 | 11.211558 | 507188 | 1.19 | 1.16 |
| llvm-clang | option-change | kitware | 1 | 10.960924 | 10.891060 | 507128 | 1.13 | 1.26 |
| llvm-clang | initial | musl | 2 | 17.763674 | 17.763967 | 487520 | 1.26 | 1.20 |
| llvm-clang | unchanged | musl | 2 | 11.758093 | 11.698193 | 476912 | 1.18 | 1.16 |
| llvm-clang | cmakelists-edit | musl | 2 | 12.405908 | 11.975224 | 477120 | 1.16 | 1.13 |
| llvm-clang | option-change | musl | 2 | 12.423752 | 12.363836 | 476884 | 1.10 | 1.09 |
| llvm-clang | initial | kitware | 2 | 17.794604 | 17.833211 | 516284 | 1.08 | 1.06 |
| llvm-clang | unchanged | kitware | 2 | 11.250242 | 11.166410 | 507168 | 1.06 | 1.05 |
| llvm-clang | cmakelists-edit | kitware | 2 | 11.392023 | 10.977747 | 507152 | 1.05 | 1.12 |
| llvm-clang | option-change | kitware | 2 | 10.792588 | 10.742069 | 507192 | 1.17 | 1.15 |
| llvm-clang | initial | product | 2 | 17.247247 | 17.269473 | 488488 | 1.15 | 1.31 |
| llvm-clang | unchanged | product | 2 | 11.711053 | 11.526454 | 477904 | 1.31 | 1.27 |
| llvm-clang | cmakelists-edit | product | 2 | 11.638524 | 11.588544 | 477776 | 1.27 | 1.21 |
| llvm-clang | option-change | product | 2 | 12.004326 | 11.758067 | 477712 | 1.17 | 1.15 |
| llvm-clang | initial | kitware | 3 | 16.484104 | 16.522947 | 516272 | 1.13 | 1.10 |
| llvm-clang | unchanged | kitware | 3 | 10.588241 | 10.588720 | 507116 | 1.10 | 1.17 |
| llvm-clang | cmakelists-edit | kitware | 3 | 10.632886 | 10.582274 | 507168 | 1.17 | 1.30 |
| llvm-clang | option-change | kitware | 3 | 10.821815 | 10.766404 | 507104 | 1.30 | 1.25 |
| llvm-clang | initial | product | 3 | 18.305196 | 18.351888 | 488232 | 1.25 | 1.18 |
| llvm-clang | unchanged | product | 3 | 11.677922 | 11.660096 | 477784 | 1.18 | 1.15 |
| llvm-clang | cmakelists-edit | product | 3 | 11.810090 | 11.760671 | 477656 | 1.15 | 1.12 |
| llvm-clang | option-change | product | 3 | 11.986047 | 11.936523 | 477656 | 1.10 | 1.08 |
| llvm-clang | initial | musl | 3 | 18.092562 | 18.073160 | 487656 | 1.08 | 1.21 |
| llvm-clang | unchanged | musl | 3 | 11.600862 | 11.590891 | 476952 | 1.21 | 1.31 |
| llvm-clang | cmakelists-edit | musl | 3 | 11.822663 | 11.423314 | 476860 | 1.31 | 1.26 |
| llvm-clang | option-change | musl | 3 | 11.452119 | 11.399946 | 476828 | 1.22 | 1.24 |
| llvm-clang | initial | product | 4 | 18.780144 | 18.761765 | 488340 | 1.24 | 1.17 |
| llvm-clang | unchanged | product | 4 | 12.298006 | 12.298463 | 477880 | 1.17 | 1.14 |
| llvm-clang | cmakelists-edit | product | 4 | 12.389537 | 12.336915 | 477900 | 1.14 | 1.11 |
| llvm-clang | option-change | product | 4 | 12.237058 | 12.026940 | 477780 | 1.09 | 1.23 |
| llvm-clang | initial | musl | 4 | 18.289752 | 18.335461 | 487664 | 1.23 | 1.22 |
| llvm-clang | unchanged | musl | 4 | 11.593460 | 11.508513 | 476932 | 1.22 | 1.19 |
| llvm-clang | cmakelists-edit | musl | 4 | 11.993190 | 11.667450 | 476792 | 1.19 | 1.16 |
| llvm-clang | option-change | musl | 4 | 11.798747 | 11.677401 | 476908 | 1.12 | 1.10 |
| llvm-clang | initial | kitware | 4 | 17.112790 | 17.148385 | 516272 | 1.10 | 1.07 |
| llvm-clang | unchanged | kitware | 4 | 10.733273 | 10.731105 | 507132 | 1.07 | 1.14 |
| llvm-clang | cmakelists-edit | kitware | 4 | 10.750914 | 10.645405 | 507124 | 1.14 | 1.11 |
| llvm-clang | option-change | kitware | 4 | 10.695725 | 10.645113 | 507120 | 1.25 | 1.13 |
| llvm-clang | initial | musl | 5 | 17.262955 | 17.300245 | 487524 | 1.13 | 1.10 |
| llvm-clang | unchanged | musl | 5 | 11.391049 | 11.393110 | 476912 | 1.10 | 1.14 |
| llvm-clang | cmakelists-edit | musl | 5 | 12.057891 | 11.763901 | 477000 | 1.14 | 1.12 |
| llvm-clang | option-change | musl | 5 | 11.785801 | 11.732647 | 476996 | 1.09 | 1.08 |
| llvm-clang | initial | kitware | 5 | 17.584495 | 17.607189 | 516264 | 1.08 | 1.06 |
| llvm-clang | unchanged | kitware | 5 | 10.858204 | 10.858556 | 507156 | 1.06 | 1.13 |
| llvm-clang | cmakelists-edit | kitware | 5 | 10.914878 | 10.864627 | 507176 | 1.13 | 1.18 |
| llvm-clang | option-change | kitware | 5 | 10.787201 | 10.738619 | 507152 | 1.23 | 1.19 |
| llvm-clang | initial | product | 5 | 17.637036 | 17.657260 | 488412 | 1.18 | 1.14 |
| llvm-clang | unchanged | product | 5 | 11.926048 | 11.923682 | 477760 | 1.14 | 1.11 |
| llvm-clang | cmakelists-edit | product | 5 | 12.097286 | 11.982048 | 477772 | 1.11 | 1.09 |
| llvm-clang | option-change | product | 5 | 12.198013 | 11.996808 | 477808 | 1.07 | 1.06 |

## File and process syscall profiles

These untimed `strace -f -c` profiles cover an unchanged reconfigure after the
measured runs. They include child processes and use a host tracer, not the release binary.
Tracing changes execution cost; its syscall times are not untraced wall-time shares.
Kernel sampling with `perf` is not collected by this command.

### fmt: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 28.18    0.002930        1465         2           wait4
 14.18    0.001475           5       283        42 faccessat
 12.97    0.001349          12       110         4 openat
 12.41    0.001291           5       257        14 newfstatat
  9.26    0.000963           5       179       175 readlinkat
  8.25    0.000858         286         3           execve
  6.91    0.000719          14        50        39 unlinkat
  4.04    0.000420          60         7         2 renameat
  2.12    0.000220         110         2           clone
  0.80    0.000083          11         7         6 mkdirat
  0.69    0.000072          12         6           fchmodat
  0.10    0.000010          10         1           chdir
  0.09    0.000009           9         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.010399          11       908       282 total
```

### fmt: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 24.27    0.002332        1166         2           wait4
 16.98    0.001632           6       257        14 newfstatat
 15.84    0.001522           5       283        42 faccessat
 13.79    0.001325          12       110         4 openat
  9.67    0.000929           5       179       175 readlinkat
  6.44    0.000619          12        50        39 unlinkat
  3.81    0.000366         183         2           clone
  3.71    0.000357         119         3           execve
  3.69    0.000355          50         7         2 renameat
  0.96    0.000092          13         7         6 mkdirat
  0.76    0.000073          12         6           fchmodat
  0.08    0.000008           8         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.009610          10       908       282 total
```

### fmt: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 20.91    0.001289           5       257        14 newfstatat
 17.83    0.001099           9       121         7 openat
 15.95    0.000983           5       179       175 readlinkat
 15.82    0.000975           3       284        41 faccessat
 11.08    0.000683          13        50        39 unlinkat
  7.24    0.000446          63         7         2 renameat
  4.06    0.000250         125         2           clone
  3.96    0.000244          81         3           execve
  1.46    0.000090          12         7         6 mkdirat
  0.97    0.000060          10         6           fchmodat
  0.63    0.000039          19         2           wait4
  0.10    0.000006           6         1           getcwd
  0.00    0.000000           0         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.006164           6       920       284 total
```

### zstd: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 20.35    0.003216           4       684       211 faccessat
 18.67    0.002951           6       446        37 newfstatat
 18.07    0.002856        1428         2           wait4
 11.97    0.001891           5       369       361 readlinkat
 11.69    0.001847          11       161         4 openat
  6.42    0.001015          10        95        85 unlinkat
  5.68    0.000898          99         9         2 renameat
  3.87    0.000611         203         3           execve
  2.22    0.000351         175         2           clone
  0.61    0.000097          13         7         6 mkdirat
  0.40    0.000063          12         5           fchmodat
  0.04    0.000007           7         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.015803           8      1785       706 total
```

### zstd: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 23.65    0.002846           6       446        37 newfstatat
 20.95    0.002521           3       684       211 faccessat
 15.24    0.001834           4       369       361 readlinkat
 12.47    0.001501           9       161         4 openat
 10.78    0.001297         648         2           wait4
  5.59    0.000673           7        95        85 unlinkat
  5.19    0.000625          69         9         2 renameat
  3.02    0.000363         121         3           execve
  1.73    0.000208         104         2           clone
  0.84    0.000101          14         7         6 mkdirat
  0.47    0.000057          11         5           fchmodat
  0.07    0.000008           8         1           chdir
  0.00    0.000000           0         1           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.012034           6      1785       706 total
```

### zstd: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 22.37    0.002489        1244         2           wait4
 20.12    0.002238           3       685       210 faccessat
 15.89    0.001768           3       446        37 newfstatat
 11.24    0.001250           7       172         7 openat
 10.76    0.001197           3       362       354 readlinkat
  6.49    0.000722           7        95        85 unlinkat
  5.72    0.000636          70         9         2 renameat
  3.33    0.000371         185         2           clone
  2.72    0.000303         101         3           execve
  0.77    0.000086          12         7         6 mkdirat
  0.28    0.000031           6         5           fchmodat
  0.15    0.000017           2         7           faccessat2
  0.08    0.000009           9         1           getcwd
  0.07    0.000008           8         1           chdir
------ ----------- ----------- --------- --------- ----------------
100.00    0.011125           6      1797       701 total
```

### libjpeg-turbo: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 74.35    0.080459        5747        14         2 wait4
  6.83    0.007391           5      1380       112 newfstatat
  4.47    0.004838           2      1632      1580 readlinkat
  4.08    0.004413           4      1040       451 faccessat
  3.39    0.003669          11       312        18 openat
  2.11    0.002280          11       204       155 unlinkat
  1.73    0.001872         144        13           execve
  1.60    0.001731         108        16           clone
  1.07    0.001163          55        21         5 renameat
  0.20    0.000212           7        27           fchmodat
  0.11    0.000115           4        25        21 mkdirat
  0.05    0.000049           7         7           chdir
  0.02    0.000024           8         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.108216          23      4694      2344 total
```

### libjpeg-turbo: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 75.05    0.090121        6437        14         2 wait4
  6.41    0.007702           5      1380       112 newfstatat
  5.41    0.006500           3      1632      1580 readlinkat
  3.81    0.004575           4      1040       451 faccessat
  3.13    0.003763          12       312        18 openat
  1.92    0.002304          11       204       155 unlinkat
  1.54    0.001844         141        13           execve
  1.39    0.001669         104        16           clone
  0.83    0.000995          47        21         5 renameat
  0.28    0.000340          13        25        21 mkdirat
  0.16    0.000187           6        27           fchmodat
  0.04    0.000051           7         7           chdir
  0.02    0.000024           8         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.120075          25      4694      2344 total
```

### libjpeg-turbo: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 76.04    0.085538        6109        14         2 wait4
  5.49    0.006178           4      1380       112 newfstatat
  4.20    0.004729           2      1632      1580 readlinkat
  3.23    0.003634          11       323        21 openat
  3.12    0.003507           3      1041       450 faccessat
  3.10    0.003488         268        13           execve
  1.67    0.001880         117        16           clone
  1.67    0.001874           9       204       155 unlinkat
  1.00    0.001127          53        21         5 renameat
  0.23    0.000261          10        25        21 mkdirat
  0.18    0.000204           7        27           fchmodat
  0.05    0.000052           7         7           chdir
  0.02    0.000026           8         3           getcwd
------ ----------- ----------- --------- --------- ----------------
100.00    0.112498          23      4706      2346 total
```

### llvm-clang: product

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 50.64    2.011030           5    358424      3525 newfstatat
 15.78    0.626697       10108        62         9 wait4
 13.39    0.531874           3    147712    145843 readlinkat
  6.69    0.265640           3     70814     42341 faccessat
  3.96    0.157191        3082        51           execve
  2.80    0.111240        1951        57           clone
  2.58    0.102334           5     19693     19585 unlinkat
  2.49    0.098693           7     13815       219 openat
  1.63    0.064723          94       682         5 renameat
  0.02    0.000802           7       109           fchmodat
  0.01    0.000314           3        80           getcwd
  0.01    0.000218           8        25        21 mkdirat
  0.00    0.000140           9        15           chdir
  0.00    0.000028          14         2         2 statfs
  0.00    0.000014           2         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    3.970938           6    611546    211550 total
```

### llvm-clang: musl

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 51.03    2.038669           5    358424      3525 newfstatat
 15.91    0.635713       10253        62         9 wait4
 13.62    0.543909           3    147712    145843 readlinkat
  6.30    0.251573           3     70814     42341 faccessat
  3.95    0.157688        3091        51           execve
  2.72    0.108827        1909        57           clone
  2.49    0.099656           7     13815       219 openat
  2.38    0.094944           4     19693     19585 unlinkat
  1.56    0.062358          91       682         5 renameat
  0.02    0.000839           7       109           fchmodat
  0.01    0.000313           3        80           getcwd
  0.01    0.000234           9        25        21 mkdirat
  0.00    0.000099           6        15           chdir
  0.00    0.000023          11         2         2 statfs
  0.00    0.000012           2         5           utimensat
------ ----------- ----------- --------- --------- ----------------
100.00    3.994857           6    611546    211550 total
```

### llvm-clang: kitware

```text
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 49.93    1.998668           5    358424      3525 newfstatat
 16.83    0.673836       10868        62         9 wait4
 12.61    0.504666           3    147688    145819 readlinkat
  5.90    0.236189           3     70817     42338 faccessat
  4.36    0.174583        3423        51           execve
  3.32    0.132805        2329        57           clone
  2.65    0.105990           7     13848       228 openat
  2.60    0.104229           5     19693     19585 unlinkat
  1.76    0.070267         103       682         5 renameat
  0.02    0.000752           6       109           fchmodat
  0.01    0.000337           4        80           getcwd
  0.01    0.000219           8        25        21 mkdirat
  0.00    0.000132           8        15           chdir
  0.00    0.000069           2        24           faccessat2
  0.00    0.000024           4         5           utimensat
  0.00    0.000021          10         2         2 statfs
------ ----------- ----------- --------- --------- ----------------
100.00    4.002787           6    611582    211532 total
```
