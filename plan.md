# Campaign: laputa-systems/cmake-build

Build a small, fast, secure, relocatable distribution of real upstream CMake 4.4.5 for `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl`. Every shipped native object is compiled with the pinned GCC-free LLVM/musl toolchain. HTTPS goes through OpenSSL-free curl+Rustls with system trust. Packages are qualified, reproducible, and published atomically.

## Status

- **Goal:** ship qualified CMake 4.4.5 archives with `cmake`, `ctest`, and `cpack` for x86-64 and ARM64 musl.
- **Prerelease:** complete tools at commit `40f84ae`, qualified on both native architectures in run `42930810892` and published in run `42938731214`. Each archive matched two clean builds on its native architecture; ARM reproduction ran in `42938846057`. GitHub does not mark the prerelease immutable; pin its digest.
- **Accepted:** the controller suite, ELF and TLS audits, relocation, real projects, upstream subset, native memory and size gates, and exact-archive qualification. Each final native upstream subset ran 85 tests, with one failure shared by the unmodified baseline. The full upstream run on the released x86-64 executable executed 674 tests; its seven failures had also occurred in the unmodified baseline.
- **Measured:** five-run native reports compare the released executables with the pinned Kitware binary and unmodified static-musl baseline. The x86-64 section-garbage-collection study reduced executable size without a demonstrated runtime change. `-Oz` was rejected after a measured LLVM reconfiguration regression; the current provenance audit rejects ThinLTO bitcode members. Historical `wait4` RSS values are invalid and are labeled accordingly.
- **Handoff:** the qualified complete-tools archive provides Laputa's `cmake`, `ctest`, and `cpack` package contract and unversioned resource path. The Laputa repository remains unchanged.
- **Parked:** locale-specific fmt assertions need locale data. CPU call-stack sampling needs a suitable profiling tool. ThinLTO link time and memory remain unmeasured until bitcode provenance can be audited. The independent section-collection review returned no conclusion, and the full `ultrareview` was not run. The Laputa consumer proof has not been run.
- **Next:** validate selected consumers in a separately authorized Laputa integration.

## Charter

- **Decide and keep going.** Make judgment calls inside **Decisions**. Record a decision in this doc only when a later slice depends on it. Otherwise the commit body carries it.
- **Execution grant.** You may write anything in this repository and commit to `main`. You may push verified commits to `origin main`. You may run `gh workflow run` for the qualification workflows, and `gh run watch`/`gh run view` for their results. You may download the locked inputs listed in **Decisions** and the crates their lockfiles name. You may pull and build Docker images. A plan does not grant more than this. Park any item that needs more.
- **Hard stops.** Each one parks the item with its cause:
  - dispatching a stable release or creating a stable release tag;
  - writing to any other repository (`laputa`, `python-build`, `llvm-prebuilt-musl`, `chromium-build`, `h12tiny`, upstream);
  - force-pushing or rewriting pushed history;
  - deleting anything outside `.work/` and this repo's build outputs;
  - a loop that cannot check anything.
- **Failing item rule.** Establish the cause before you retry, using `root-cause`. Allow three attempts per slice. Then park the slice on branch `park/<id>` with the cause and a retry condition, and move on to the next unblocked slice. A shared environment blocker (Docker, network, GitHub runner) gets one owner slice. Nothing else waits on a retry.
- **Fix egregious problems on the way, in their own commit.** These are:
  - a phase that reruns while its fingerprint is unchanged;
  - `controller-test` taking over 60 s;
  - any slice acceptance command taking over 2× its **Baseline** time;
  - a check that reports pass on zero executed tests.

  Record anything smaller in the slice's commit body and leave it.
- **Parity before optimization.** Optimization flags, size work, and PGO/BOLT belong to phase E only. Before E, measure and record sizes and timings, but they do not gate.
- **One writer by default.** Parallel lanes are allowed only for the pairs named in **Sequence**. Each lane works in a worktree at `.work/wt/<lane>`, following `orchestrate`'s worktree lifecycle. Subagents launch only through `pi-subagent-bridge`.
- **Paths.** Put scratch, caches, downloads, and worktrees under `.work/` (ignored via `.git/info/exclude`). Never use `/tmp` or `$TMPDIR`. Export `TMPDIR=$PWD/.work/tmp` for builds.
- **Commits.** Each commit is a Conventional Commit with the workstream as its scope (`controller`, `toolchain`, `cmake`, `tls`, `audit`, `package`, `qualify`, `bench`, `ci`, `docs`). Put the item ID in the body, and end the body with the session's attribution lines. Code comments never cite this doc. No formatters.
- **Verification.** Run the slice's acceptance command and the narrowest affected suite on the integrated tree. Run the full local suite (`python3 build.py qualify --target x86_64-unknown-linux-musl`) only at milestones M1–M3 and at close. The owner waived the performance gate; record host load and measurement variation. Never claim a check passed unless it ran and passed. Anything not executed is reported as not executed.
- **Steering.** After each accepted slice, on resume, and after any second failure of a slice, run `orchestrate`'s parent steering checkpoint (`~/.claude/skills/orchestrate/references/campaigns.md#parent-steering-checkpoint`). Then rewrite **Status** in place. Never append logs.

## Decisions

### Owner (2026-11-10)

- **O1 Toolchain release.** Use the latest llvm-prebuilt-musl release, `llvm-musl-23.1.5-dc0d9b9`, pinned by asset sha256 (values in **Reference**). Laputa's current `llvm-toolchain` recipe also pins `llvm-musl-23.1.5-dc0d9b9` (Laputa commit `c1b407ad`).
- **O2 HTTP stack.** Keep CMake's bundled curl (`Utilities/cmcurl`, curl 8.20.0) with the Rustls backend. h12tiny was considered and rejected for now: its blocking client has no proxy, redirect, or FTP support, so replacing curl would mean a shim with more friction.
- **O3 Push and CI.** The executor may push verified commits to `origin main` and dispatch the native x86_64 and aarch64 qualification workflows. A prerelease dispatch is authorized by O8; stable release dispatch stays with the owner (see **Needs environment**).

- **O4 Crypto provider.** Use Graviola through a small rustls-ffi provider patch (P5). This matches python-build and h12tiny.

- **O5 Performance gate.** The owner waived the performance gate on 2026-11-10. Measurements remain required and report observed load and variation. Five interleaved repetitions are sufficient.

- **O6 OpenSSL identifiers.** The owner allows version-recognition text and `openssl-probe` identifiers that locate system certificates. The audit still rejects OpenSSL libraries, API symbols, and other OpenSSL text.

- **O7 Package evidence.** The archive contains `artifact.json` with build metadata and hashes for the other packaged files. A separate results record binds the final archive hash, size, and qualification results to the exact archive bytes.

- **O8 Prerelease.** The owner authorized a native CI prerelease workflow and its dispatch on 2026-11-10. Publish only after both native qualification jobs succeed at the exact commit.

- **O9 Laputa tools.** The owner requested the tools necessary for Laputa. Include `ctest` and `cpack` alongside `cmake`, with the same provenance, ELF, relocation, and native qualification guarantees. The previously published CMake-only prerelease does not satisfy this contract.

### Prescribed

Each decision gives its reason and, where one exists, the condition that would reverse it.

- **P1 Source.** CMake 4.4.5 from `https://github.com/Kitware/CMake/releases/download/v4.4.5/cmake-4.4.5.tar.gz`, sha256 `a0c54c88abb8078dd8eccadb717fc6bb194bf18e7d44c86309910288886e04e2`, size 13289246. This was verified on 2026-11-10 against GitHub's asset digest and Kitware's `cmake-4.4.5-SHA-256.txt`. Lock both the digest and the signed checksum file's sha256 (`f502d705…dd25`). The archive has no absolute or `..` members. Extraction must still reject them, and reject symlinks that escape the tree.
- **P2 Builder environment.** All offline phases (`prepare` through `package`) run in a Docker container started with `--network none`:
  - The image is built from Alpine `3.25.0_alpha20260805`, image index `sha256:020dfcbaaf4cc1078bf2d9c7ba31a8466e334061dcd2f248001d68f79e52c000`. This is the image python-build pins, and it matches this host.
  - Each apk in the image is pinned by sha256 in `bootstrap.lock.json`.
  - The image has no `gcc`, `binutils`, `musl-dev`, `libstdc++-dev`, or OpenSSL dev package. It may contain `python3`, `make`, `linux-headers`, `xz`, and runtime libraries.
  - Locked apk entries are produced the way python-build's `build/relock_linux.py` produces them: from the APKINDEX, checked against `alpine-keys`. Never lock-on-first-fetch.
  - Alpine edge drops superseded apks from its CDN. If a locked apk returns 404, relock that package to the current version by the same method, in its own `build(lock)` commit, and continue. Never publish a mirror.
  - The index digest was verified on 2026-11-10: its amd64 manifest is `alpinelinux/docker-alpine@410e6fcf`.

  `fetch` and image construction are the only networked steps. Evidence of the boundary is recorded in `artifact.json`. It is the container's `NetworkMode=none` plus a live probe inside the container showing that a TCP connect to a listener the controller opened on the host fails. That probe follows python-build's `buildsys/sandbox.py` `network_boundary_selftest`. `controller-test` runs on the host Python without Docker.
- **P3 Sysroot.** Supplies headers plus one link-time loader:
  - musl headers come from `make install-headers ARCH=<arch>` on musl 1.2.6 source (`https://musl.libc.org/releases/musl-1.2.6.tar.gz`, sha256 `d585fd3b613c66151fc3249e8ed44f77020cb5e6c1e635a616d3f9f82460512a`). That is the same source as the toolchain's bundled `libc.a`.
  - Linux UAPI headers come from the locked Alpine `linux-headers` apk (x86_64 `7.2.1-r0`, sha256 `45e0d4df3e4002122c953d0af6e208f1e8369fc6c88c67138400b87f871fd54b`; the aarch64 entry is relocked by the P2 method). Both sha256s were re-verified on download on 2026-11-10.
  - The toolchain's `lib/musl/libc.so` is a linker script, `GROUP ( =/lib/ld-musl-<arch>.so.1 )`, resolved through `--sysroot`. A headers-only sysroot therefore fails every dynamic link with `cannot open <sysroot>//lib/ld-musl-x86_64.so.1`. This was reproduced on 2026-11-10 by `./bootstrap`'s compiler probe. So the sysroot also gets `lib/ld-musl-<arch>.so.1`: musl 1.2.6 `lib/libc.so`, built from the same source by the P4 clang, configured as `LIBCC=$(clang -print-libgcc-file-name) ./configure --target=<arch>` and built with `make lib/libc.so LDFLAGS=-Wl,-soname,libc.musl-<arch>.so.1`. The build takes about 10 s, and its `.comment` holds only clang and LLD. It is a link-time DSO and fixture loader only, and is never shipped.
  - The soname is required. Without it, lld records the sysroot path itself as `DT_NEEDED`: `[/home/…/sysroot//lib/ld-musl-x86_64.so.1]`, observed on 2026-11-10 in a bootstrap-built `cmake`. With it, `DT_NEEDED` is `libc.musl-<arch>.so.1`, matching Alpine's loader. The D1 audit's builder-host-path rule must catch the soname-less case, and `tests/audit` keeps it as a fixture.

  Startup objects, `libc.a`, and the loader script always come from the toolchain's `lib/musl/` (its `clang.cfg` searches there first). The provenance fixture fails if any linked object resolves from the sysroot (other than that loader DSO) or from `/usr/lib`. Reverse only if musl 1.2.6 headers and the toolchain's libc disagree, which the fixture would show.
- **P4 Toolchain invocation.** Set explicitly:
  - `CC=<tc>/bin/clang`, `CXX=<tc>/bin/clang++`;
  - `AR/RANLIB/NM/STRIP/OBJCOPY/READELF=<tc>/bin/llvm-*`;
  - `--target=<arch>-linux-musl --sysroot=<sysroot>`, `-fuse-ld=lld`, `--rtlib=compiler-rt`, `--unwindlib=libunwind`, `-stdlib=libc++`.

  Use a CMake toolchain file generated per target under the build root. Before every phase, compiler identity is checked against the lock: the first lines of `clang --version` and `ld.lld --version` must equal `clang version 23.1.5` and `LLD 23.1.5 (compatible with GNU linkers)`, and every tool must resolve inside `<tc>`. The released Clang does not print a commit; the locked archive digest identifies the asset, whose GitHub release target is `dc0d9b96ab4c5ddb11e308303e0129a559f2235d`. Report that as the release target, not as a compiler-reported commit. A tool resolving outside `<tc>`, or a different version string, is a hard failure.
- **P5 TLS.** Configure curl with `CMAKE_USE_OPENSSL=OFF`, `CURL_USE_RUSTLS=ON`, `CURL_CA_BUNDLE=none`, and `CURL_CA_PATH=none`, so no build-host path is baked in.
  - **Library.** rustls-ffi `v0.15.7`. curl 8.20 requires 0.15 or newer, checked at `Utilities/cmcurl/CMakeLists.txt:1158`. The crypto provider is **Graviola** (owner decision O4). Build it as a staticlib with `--no-default-features --features graviola`.
  - **Source package.** Use the crates.io `rustls-ffi` 0.15.7 package, locked by the registry index checksum and the package size. Its VCS metadata names commit `8f0eadf96fa21ade96d867c7ea06f8f5fddda856`, matching the upstream tag. The package contains the `librustls` subtree at its root, so patch paths are relative to that root.
  - **Provider patch.** Upstream rustls-ffi offers only ring and aws-lc-rs, so `patches/rustls-ffi/0001-graviola-provider.patch` does three things:
    - adds a `graviola` feature to `librustls/Cargo.toml`, depending on `rustls-graviola` 0.4 (h12tiny's version; `default-features = false`);
    - adds a `#[cfg(all(feature = "graviola", not(feature = "ring"), not(feature = "aws-lc-rs")))]` branch returning `rustls_graviola::default_provider()` in `provider_from_crate_features` (`librustls/src/crypto_provider.rs:611`), and gates the matching ring/aws-lc-rs-only code the same way;
    - carries the resulting `Cargo.lock`.

    The pattern is python-build's `backend/rtls-graviola.patch`. The platform verifier must receive the same Graviola provider.
  - **Graviola floor.** Graviola has no C, only Rust and asm, so no C compiler touches the TLS stack. Its crypto entry asserts CPU support (`graviola/src/low/x86_64/cpu.rs:228`): x86_64 needs adx, aes, avx, avx2, bmi1, bmi2, and pclmulqdq (Broadwell, 2014 and later); aarch64 needs aes, sha2, pmull, and neon.
    - The product keeps the P8 generic CPU baseline, so `cmake` runs everywhere and HTTPS alone carries this floor.
    - Under `panic_unwind`, rustls-ffi's panic boundary turns that assert into an error result, so curl reports a TLS failure and `cmake` does not abort. This host's CPU meets the floor, so the unsupported-CPU path is on **Needs environment**. Add no test-only seam to fake it. `docs/tls.md` and the Laputa handoff state the floor.
  - **Dependency gate.** `cargo tree -e normal --target <triple>` for the patched librustls must contain `graviola` and none of `ring`, `aws-lc-rs`, `aws-lc-sys`, `openssl`, `openssl-sys`, or `native-tls`. This runs in `controller-test` and in `qualify`.
  - **Rust toolchain.** Pin `nightly-2026-09-15` with the component sha256s from python-build `backend/linux-bootstrap-x86_64.json` and `linux-bootstrap.lock.json` (aarch64). Build with `-Zbuild-std=std,panic_unwind -Zbuild-std-features=panic-unwind,backtrace,llvm-libunwind`, linking the toolchain's `lib/libunwind.a`. python-build `backend/build-no-openssl.py:914-960` found that the prebuilt musl `libstd` carries GCC-compiled compiler-rt and libunwind objects.
  - **Crate sources.** Vendor them with `cargo vendor --locked` in `fetch`. Cargo verifies the `Cargo.lock` checksums. `build` runs `cargo --offline --frozen`. Do not change the nightly pin.
  - **Trust patch.** curl's rustls backend ignores `CURLOPT_CAPATH` (no CAPATH handling in `lib/vtls/rustls.c`). With no CA it fails closed, because no verifier is set (`rustls.c:1039-1060`). Patch `Source/cmCurl.cxx` `cmCurlSetCAInfo` (`:128-185`):
    - Keep `CAINFO` for `CMAKE_TLS_CAINFO`, for `SSL_CERT_FILE`, and for the first existing upstream default file.
    - In every other case, including `SSL_CERT_DIR`, set `CURLSSLOPT_NATIVE_CA`. That selects `rustls_platform_server_cert_verifier`, which reads `SSL_CERT_FILE`, `SSL_CERT_DIR`, and the probed system paths.
    - Never embed a root store, never disable verification unless the user sets `CMAKE_TLS_VERIFY OFF`, and keep upstream's default of verifying.
- **P6 Bootstrap and executor.** The bootstrap CMake is never shipped. The production compiler is always the P4 toolchain.
  - The selected bootstrap is the locked Alpine CMake package. The `G3` comparison and its warm-cache limits are in `docs/build-system.md`.
  - The selected build executor is the pinned Ninja built with the P4 toolchain. Samurai remains a qualification generator.
- **P7 Configuration and targets.**
  - Settings: `CMAKE_BUILD_TYPE=Release`, `BUILD_CursesDialog=OFF`, `BUILD_QtDialog=OFF`, `SPHINX_*=OFF`, `CMAKE_USE_SYSTEM_LIBRARIES=OFF` (every bundled library is compiled by P4), `CMake_ENABLE_DEBUGGER=ON`.
  - The debugger stays because `cmake --debugger` is a `cmake` feature.
  - Upstream tests need `ctest`. The default upstream build also builds `cpack`. Stage and qualify both tools alongside `cmake`.
  - Remove targets only through upstream options. Patch only where upstream has no option, and give each patch an inventory entry.
  - Laputa's three musl patches (`laputa/packages/cmake/patches/`) are candidates, not defaults. Apply one only after the unpatched build fails on our P3 sysroot with the error it fixes, and record that error. The 2026-11-10 Baseline build needed none of them, and the `linux/fs.h` failure they work around came from a sysroot missing Linux headers.
- **P8 Hardening and linkage.** The baseline, before phase E, is:
  - upstream Release flags;
  - static PIE (`-static-pie`);
  - `-fstack-protector-strong -fstack-clash-protection`;
  - `-Wl,-z,relro,-z,now,-z,noexecstack`;
  - no `-march`. The CPU baseline is generic `x86-64` and `armv8-a`, because CMake is a build tool and must run on every host Laputa supports.

  No `_FORTIFY_SOURCE`: musl has no fortify without fortify-headers, which is a recorded non-goal. Phase E compares static PIE against musl-dynamic. It switches to musl-dynamic only if static PIE fails an acceptance item or costs more than 10% startup latency.
- **P9 Reference CMake.**
  - Kitware's official `cmake-4.4.5-linux-{x86_64,aarch64}.tar.gz` (sha256s in **Reference**) is the performance baseline and the output-comparison oracle. It is glibc-linked, so it runs only in a reference container: `debian:trixie-slim`, pinned by index digest at `fetch` time. Docker index digests are content addresses, so locking one when first resolved is sound.
  - A second build of unmodified 4.4.5 with the P4 toolchain, default options, and no patches is the baseline for upstream-test failures and for patch impact.
- **P10 Real projects.** Lock each by release tarball sha256 in `sources.lock.json`:
  - **small:** fmt (latest release): configure, build, test.
  - **medium:** zstd `build/cmake`: configure, build, run.
  - **nontrivial custom commands and dependencies:** libjpeg-turbo (latest release, `-DWITH_SIMD=OFF` because nasm is not locked): configure, build, run `tjunittest`.
  - **large (configure only):** LLVM 23.1.5 `llvm-project-23.1.5.src.tar.xz` with `-DLLVM_ENABLE_PROJECTS=clang`, used for the configure and generate timings.

  Delegated bound: you may substitute a project with another of the same tier only when its build needs an unlocked tool, and you must record why.
- **P11 Upstream regression subset.** Write it to `tests/upstream-subset.txt` as `ctest -R` regexes. It runs from the build tree with the built `ctest`.
  - It covers RunCMake `CommandLine`, `CommandLineTar`, `File_Archive`, `file`, `file-DOWNLOAD`, `CMakePresets`, `FileAPI`, `GeneratorExpression`, `try_compile`, `try_run`, `find_package`, `install`, `export`, `Ninja`, `BuildDepends`, `ExternalProject`, `FetchContent`, and the `CMakeLib` and `kwsys` unit tests.
  - Bound: at most 20 minutes on 8 cores. Add tests to the subset freely. Remove one only by recording an upstream-failing reason.
  - A test is red when it fails on our build and passes on the P9 unmodified build. A failure shared with the P9 build is listed in `docs/qualification.md`, not hidden.
  - The full upstream `ctest` runs once at close. It is expensive, so report its start before running it.
- **P12 Release budgets.** `release-budgets.json` holds the budgets measured at milestone M2: executable size, unpacked size, compressed size, `cmake --version` latency, and the small-project configure time. The regression threshold for each metric is the larger of 3% and 2× the observed spread over at least five interleaved runs. Timing gates are waived; size and CMake-image memory gates remain binding.
- **P13 CI shape.** Mirror python-build `.github/workflows/build.yml`:
  - `controller.yml` runs `controller-test` on push and PR.
  - `qualify.yml` uses `workflow_dispatch` only, with native jobs on `ubuntu-24.04` and `ubuntu-24.04-arm`. Each job runs `python3 build.py qualify --target <triple>` in the P2 container and uploads its archive, `artifact.json`, and qualification report.
  - `release.yml` uses `workflow_dispatch` on the default branch and tags `release-<sha>`. It requires both native qualification jobs at that SHA and verifies archive-bound results and memory evidence. It publishes a new prerelease with `SHA256SUMS` and never rebuilds or overwrites an existing release. GitHub does not mark the prerelease immutable; consumers must pin its digest.

  No emulation is used anywhere. CI cache keys include the full input fingerprint.

### Delegated (executor decides within the bound and records the choice in the commit body)

- **Module layout.** Organize `buildsys/` the way python-build is organized (`inputs`, `elf`, `generations`, `reproduce`, `sandbox`), with no third-party Python dependencies. Copy no file wholesale; reuse patterns. The bound: one module per concern, and no framework shared with other repos.
- **Phase E flag choices.** Adopt a flag set only if it improves a measured metric by more than its threshold and keeps every acceptance check green. Candidates: `-O2`/`-O3`/`-Oz`, sections plus `--gc-sections`, ThinLTO, `--icf=safe` (never `all`), `-fvisibility=hidden` for bundled libraries, and stripping. RTTI and exceptions stay on. Never use `-ffast-math` or `-march=native`. On a tie, keep the simpler set.
- **Compiler cache.** Developer C and C++ builds use `kache` with a persistent per-target store. Qualification and reproduction do not use that developer cache. Rust uses its existing wrapper with isolated build state. CI restores verified inputs and qualification phases, which remain subject to fingerprint and output-digest checks.
- **Link parallelism.** Set `-j` to `nproc` and limit ThinLTO link jobs so peak RSS stays below 75% of available memory, measured.
- **PGO and BOLT.** These are optional research items after `E3`. Do them only if all of E is accepted, and never let them gate release.

## Baseline

- **Host:** x86_64 Alpine 3.25.0_alpha20260805, 8 CPUs, 29 GiB RAM, Docker 29.9.2, `unshare -rn` works. There is no host `cmake`, `ninja`, or `samu`. Host `/usr/include` has musl headers but no `linux/fs.h` (no linux-headers). That explains Laputa's ioctl patch, and P3 supplies the missing headers.
- **Known red:** none (greenfield).
- **Foundation proof (2026-11-10, x86_64):** `dc0d9b9` `clang++ -O2 -flto=thin` built a C++ program using exceptions, destructors, and `std::filesystem`, both static-PIE and musl-dynamic, and both ran correctly. The dynamic build's `DT_NEEDED` was only `libc.musl-x86_64.so.1`, with interpreter `/lib/ld-musl-x86_64.so.1`. `.comment` held only `clang version 23.1.5` and `Linker: LLD 23.1.5`. Each compile and link took about 1 s.
- **Loop timings (2026-11-10, x86_64 host, not in a container, P4 clang with the P3 sysroot, unpatched 4.4.5, `-DCMAKE_USE_OPENSSL=OFF -DBUILD_CursesDialog=OFF`, Release, upstream test targets on):**
  - upstream `./bootstrap --parallel=8`: 207 s, peak RSS 343 MB;
  - full `make -j8`: 410 s, peak RSS 368 MB;
  - rebuild after touching `Source/cmake.cxx`: 25 s.

  The bootstrap-built `cmake` reports `4.4.5`. It is a 23.4 MB unstripped, dynamic, PIE binary. No musl patch was needed with the P3 headers. A cold C1 build therefore costs about 10 minutes, and a phase-reused rerun only the changed objects. Size C1 and the later CMake-rebuilding slices on that basis. Their acceptance reuses phase outputs whenever fingerprints match.
- **Fetch:** the toolchain archive (100.7 MB) downloads in about 9 s here.

## Sequence

The `ID` names the slice. Each slice lists the files it owns, its prerequisites, and the acceptance command that ends it. Slices run in order unless a pair is named parallel. `M` marks a milestone, where the full local suite runs.

### Phase G: ground and viability

1. **G1 Controller skeleton and input verification.**
   - Owns `build.py`, `buildsys/{__init__,inputs,phases,targets}.py`, `sources.lock.json`, `bootstrap.lock.json`, `tests/controller/`, `AGENTS.md`.
   - Work: the subcommands from the source brief (`doctor`, `fetch`, `prepare`, `configure`, `build`, `test`, `package`, `qualify`, `reproduce`, `benchmark`, `controller-test`); the lock schema; download into `.work/cache` with sha256 and size verification of both cached and fresh bytes; archive extraction that rejects absolute paths, `..`, escaping symlinks, hardlinks, and device nodes; content-fingerprinted phase records whose reuse requires every input to match; and clean operations that never touch externally supplied sources or caches.
   - Accept: `python3 build.py controller-test` (≤ 60 s). It covers these negative controls: a corrupted cached input, a corrupted fresh input, a missing lock entry, a modified lock entry, a traversal archive, an unsafe-symlink archive, stale reuse after a fingerprint change, and an interrupted phase that is never marked complete.
2. **G2 Builder image, sysroot, and provenance fixture.**
   - Owns `docker/builder.Dockerfile`, `buildsys/{sandbox,toolchain,sysroot}.py`, `tests/fixtures/provenance/`.
   - Prereq: G1.
   - Work: build the P2 image; lay out the P3 sysroot; run the six-point provenance fixture from the source brief inside the sealed container. The six points: C and C++ compile; static and dynamic musl links; exceptions, destructors, and `std::filesystem`; selection of compiler-rt and libc++ proven from `-Wl,--trace`/`-Wl,-Map` input paths inside `<tc>`; a ThinLTO compile, `llvm-ar` archive, link, and run; and ELF machine plus closure.
   - Accept: `python3 build.py doctor --target x86_64-unknown-linux-musl && python3 build.py prepare --target x86_64-unknown-linux-musl`, which runs the fixture and the network-boundary probe. Negative controls in `controller-test`: a fake `clang` earlier on `PATH` or a wrong version string fails `doctor`; an `--target aarch64` artifact fails the x86_64 machine check; a link that pulls an object from a sysroot `crt1.o` fails; a fetch attempted inside `prepare` fails.
3. **G3 Bootstrap and executor, measured.**
   - Owns `buildsys/bootstrap.py`, `docs/build-system.md` (bootstrap section).
   - Prereq: G2.
   - Work: apply P6. Measure cold bootstrap+build wall time and peak RSS for (a) upstream bootstrap and (b) the Alpine `cmake` apk, and for samurai versus Ninja (full build and no-op), each over 3 interleaved runs.
   - Accept: `python3 build.py configure --target x86_64-unknown-linux-musl`, then rerun it and show the phase is reused with no work. Record the measurements in `docs/build-system.md`.
4. **G4 OpenSSL-free HTTPS viability.**
   - Owns `buildsys/rust.py`, `buildsys/tls.py`, `patches/0001-cmcurl-native-ca-fallback.patch`, `patches/rustls-ffi/0001-graviola-provider.patch`, `patches/README.md`, `tests/tls/`.
   - Prereq: G2. G3 and G4 may run as parallel lanes: their files are disjoint, and the only shared file, `bootstrap.lock.json`, is edited by the coordinator only.
   - Work: build rustls-ffi per P5 and link a minimal C program against it plus cmcurl in isolation. The program runs against a local TLS server whose CA and certificates are generated at test time by the `openssl` CLI in the test container. That CLI is test-only and never in the product.
   - Accept: `python3 build.py controller-test -k tls` and `tests/tls/run.sh`, proving: a trusted CA via `CAINFO` succeeds; `SSL_CERT_DIR`-only succeeds through `NATIVE_CA`; an untrusted CA fails; a hostname mismatch fails; an expired certificate fails; a TLS 1.3 and a TLS 1.2-only server both handshake; `nm` on the archive shows no `SSL_`/`OPENSSL_` symbols; and the P5 dependency gate passes. If this cannot pass, mark the HTTPS lane `dev-candidate`, record the blocker in `docs/tls.md`, and continue. A dev candidate is never promoted (Acceptance A4).

### Phase C: minimum complete product

5. **C1 Locked CMake build.**
   - Owns `buildsys/cmake.py`, `patches/` (series additions), `buildsys/patches.py`.
   - Prereq: G3, G4.
   - Work: configure and build the full CMake with P5, P7, and P8 in the sealed container. Write the patch inventory (`patches/README.md`: file, sha256, rationale, order), checked at `prepare`. Write the dependency inventory, generated from the actual CMake target graph via `cmake --graphviz` plus the link map. It records each bundled library's version, license, and whether it is reachable from `cmake` or only from `ctest`/`cpack`/the debugger.
   - Accept: `python3 build.py build --target x86_64-unknown-linux-musl`. Then the built `bin/cmake --version` prints `4.4.5`, and `cmake -E capabilities` shows the TLS/`curl` feature enabled.
6. **C2 Staging, relocation, and basic qualification.**
   - Owns `buildsys/stage.py`, `tests/acceptance/{cli,c_cxx,generators,relocation}/`, `buildsys/qualify.py`.
   - Prereq: C1.
   - Work: stage `bin/cmake`, `share/cmake-4.4/` (modules, templates, platform files, compiler detection), `share/doc/cmake-build/` (notices plus `artifact.json`), and nothing else. Run acceptance against the staged tree copied to a directory with spaces, with the build tree unmounted.
   - Accept: `python3 build.py test --target x86_64-unknown-linux-musl --suite basic`. It covers: CLI (`--version`, `--help`, `-E`, `-P`, `-S`/`-B`, `--build`, `--install`, cache `-D`/`-U`/`-L`); a C and C++ configure, build, install, and run with the P4 compiler under both Ninja/samurai and Unix Makefiles; and `CMAKE_ROOT` resolving inside the relocated prefix with no host CMake. Negative controls: a removed `Modules/CMakeDetermineCCompiler.cmake` fails with a missing-resource error; a broken relocation (moved `share/` only) fails.
   - **M1:** run `qualify` (basic suites).

### Phase D: hardening and parity

Slices D2, D3, and D4 own disjoint test directories. Any two of them may run in parallel after D1. Each D slice runs on top of C2's controller, and the coordinator alone edits `buildsys/qualify.py` to register the suites.

7. **D1 Independent ELF audit.**
   - Owns `buildsys/elf.py`, `tests/audit/`, including a contaminated fixture.
   - Prereq: C1.
   - Work: audit every packaged ELF with `llvm-readelf`/`llvm-objdump`/`llvm-nm` against python-build `buildsys/elf.py` and llvm-prebuilt-musl `scripts/check-purity.sh`. Checks: exact `e_machine`; static PIE, or the approved musl interpreter plus `DT_NEEDED` ⊆ {`libc.musl-<arch>.so.1`}; no `GLIBC_*`, libgcc, libgcc_s, libstdc++, or OpenSSL (symbols, strings, `DT_NEEDED`); `.comment` free of `GCC:`; no `.gnu.version_r` beyond musl's; `PT_GNU_STACK` not executable; `PT_GNU_RELRO` plus `BIND_NOW`; ET_DYN PIE; no RPATH or RUNPATH; no build-host paths (`/home/`, the build root, `.work`) in strings. Before the final link, also audit every archive member the link actually extracts (`-Wl,--why-extract=`), including `librustls.a`, for `.comment` provenance. Also rerun the P5 cargo dependency gate.
   - Accept: `python3 build.py controller-test -k audit` passes on the real `cmake`. It must reject fixtures with each of these: GCC-built objects, a `libstdc++` `DT_NEEDED`, an exec stack, a host RPATH, and a wrong machine.
8. **D2 Functional parity suite.**
   - Owns `tests/acceptance/{graph,features,packages,incremental,presets_fileapi,archive}/`.
   - Prereq: C2.
   - Work: build graphs with multiple libraries, PUBLIC/PRIVATE/INTERFACE dependencies, imported targets, genexes, generated sources, custom commands, and transitive includes; language detection, feature checks, `try_compile`, and `try_run`; `find_package` in config and module mode, plus install/export and downstream consumption of the installed export; incremental rebuild after touching a source, a header, and `CMakeLists.txt` on both generators; presets and file API replies; `cmake -E tar` create and extract (gz, xz, zstd, bz2, zip) and `file(ARCHIVE_CREATE|ARCHIVE_EXTRACT)`. Each output that could differ (file API JSON with paths normalized, generated `build.ninja` command lines, `--system-information` subsets) is diffed against the P9 Kitware binary. Differences are reported in `docs/qualification.md`, never assumed harmless.
   - Accept: `python3 build.py test --target x86_64-unknown-linux-musl --suite parity`.
9. **D3 Networking.**
   - Owns `tests/acceptance/network/`.
   - Prereq: C2, G4.
   - Work: test against the local TLS server: `file(DOWNLOAD)` over HTTPS, a 302 redirect, `EXPECTED_HASH` success and mismatch, an untrusted CA, a hostname mismatch, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `CMAKE_TLS_CAINFO`, `CMAKE_TLS_VERIFY OFF` honored only when set, and an `https_proxy` CONNECT through a local proxy. Then one real-internet workflow: `FetchContent` of a locked GitHub tarball with `URL_HASH`.
   - Accept: `python3 build.py test --target x86_64-unknown-linux-musl --suite network`. The internet case reports `skipped: no network`, never pass, when offline.
10. **D4 Real projects and upstream subset.**
    - Owns `tests/projects/`, `tests/upstream-subset.txt`.
    - Prereq: C2.
    - Work: P10 and P11.
    - Accept: `python3 build.py test --target x86_64-unknown-linux-musl --suite projects,upstream`. Zero executed tests, a missing report, or a timeout is a failure.
11. **D5 Packaging, generations, reproducibility.**
    - Owns `buildsys/{package,generations,reproduce}.py`, `tests/controller/test_package*.py`.
    - Prereq: D1.
    - Work:
      - **Archive.** Deterministic `tar.xz`: sorted entries, uid/gid 0, names empty, mode normalized, `mtime=SOURCE_DATE_EPOCH` (the CMake source release time), and fixed xz settings.
      - **`artifact.json`.** Contains every field from the source brief §9: source version and digest; repository commit and patch-set identity; LLVM toolchain release, digest, and compiler identity; target architecture and CPU baseline; effective compiler and linker flags; build-time dependency closure; build mode and isolation evidence; file inventory with hashes; ELF audit results; complete qualification summary; archive size and unpacked size.
      - **Generations and selection.** Immutable generations following python-build `buildsys/generations.py`, with active selection by atomic rename.
      - **Qualification of the packaged bytes.** `qualify` extracts the exact archive into a fresh directory whose name contains spaces and reruns the `basic`, `parity`, and `network` suites on those bytes.
      - **Reproducibility.** `reproduce` runs two clean builds in separate roots and compares file types, modes, symlink targets, content, archive bytes, and embedded paths.
    - Accept: `python3 build.py controller-test -k package` must show all of these: a failed or interrupted qualification never activates a generation; a previously accepted generation survives a failed candidate; and a tampered archive fails `qualify`. Then `python3 build.py reproduce --target x86_64-unknown-linux-musl` reports identical output, or lists each defect. Reproducibility is claimed only when identical.
    - **M2:** `qualify` (all suites) on x86_64, then record P12 budgets.
12. **D6 Native CI.**
    - Owns `.github/workflows/`, `docs/ci-and-releases.md`.
    - Prereq: D5.
    - Work: P13. Push, then dispatch `qualify.yml` for both targets.
    - Accept: `gh run watch <id> --exit-status` green for both jobs at the pushed SHA, and the aarch64 artifacts pass the same audit and suites natively. If the ARM64 runner is unavailable, aarch64 stays `unqualified` and moves to **Needs environment**.

### Phase E: optimization (budgets gate from here)

13. **E1 Benchmark harness.**
    - Owns `buildsys/benchmark.py`, `docs/performance.md`.
    - Prereq: M2.
    - Work: compare against the P9 Kitware binary on the same machine and the same projects, with interleaved runs (≥ 5) and median plus spread. Measure: clean and incremental CMake build wall time and peak RSS; configure/generate time for P10 small, medium, and large; no-op reconfigure; reconfigure after a relevant edit; `cmake --version` and `cmake -P` latency; peak configure RSS; executable size; resource size; archive size. Label cold-cache and warm-cache runs (drop caches only via a fresh container plus `vmtouch -e` when available; otherwise mark cold `not measured`). Use `perf-gate-ready` per the Charter.
    - Accept: `python3 build.py benchmark --target x86_64-unknown-linux-musl` writes `docs/performance.md` tables from a fresh run.
14. **E2 Flag and linkage study.**
    - Owns `buildsys/cmake.py` (flags only), `release-budgets.json`.
    - Prereq: E1.
    - Work: apply the Delegated flag bound and the P8 linkage comparison, measuring each candidate on its own before combining any.
    - Accept: `python3 build.py qualify --target x86_64-unknown-linux-musl` green, with the adopted set's gains in `docs/performance.md`.
15. **E3 Target trimming.**
    - Owns `patches/`, `buildsys/cmake.py`.
    - Prereq: E2.
    - Work: drop any still-built target not needed by `cmake` or by qualification `ctest`, using upstream options first.
    - Accept: same as E2, plus the D1 audit.
    - **M3:** `qualify` and `reproduce` on x86_64, and a CI rerun for both targets.

### Phase F: docs and close

16. **F1 Documentation and Laputa handoff.**
    - Owns `README.md`, `AGENTS.md`, `docs/*.md`, `NOTICE`/`licenses/`.
    - Prereq: M3.
    - Work: write the topics from source brief §12: product and target contracts; bootstrap and toolchain architecture; source and dependency provenance; exact build commands; offline build isolation; native dependency and ELF purity policies; qualification matrix and evidence; packaging, relocation, and reproducibility; performance measurements and optimization decisions; integration instructions for Laputa; outstanding limitations and follow-up work. The README stays short. Licenses cover CMake, every bundled library, rustls-ffi and its crates (from `cargo metadata`), and the LLVM runtime libraries linked in (compiler-rt, libc++, libc++abi, libunwind: Apache-2.0 WITH LLVM-exception) and musl (MIT). `docs/laputa-integration.md` covers: the package layout (`usr/bin/cmake`, `usr/share/cmake-4.4/`); that there are no runtime deps beyond the musl loader when dynamic, and none when static PIE; proof with the `dc0d9b9` toolchain plus samurai; no D-Bus, systemd, glibc, GCC runtime, or host CMake resources; and the current Laputa toolchain pin.
    - Accept: `mdtool check --untracked docs README.md AGENTS.md` clean, and every command in the docs ran during this campaign.
17. **F2 Close.**
    - Prereq: F1.
    - Work: run `dead-code-archaeology` over `buildsys/` and delete what is unreachable from `build.py`. Run the full upstream `ctest` once (report before starting). Run `ultrareview` and fix P1/P2 findings. Write the final report: commit SHA, implemented scope, tests executed, per-architecture verdicts, sizes, performance, and blockers.
    - Accept: `qualify` for both targets green in CI at the final SHA, and `controller-test` green locally.

## Acceptance

Each deliverable is met only when its command passes on the integrated `main`.

| # | Deliverable | Proof | Fails when |
| --- | --- | --- | --- |
| A1 | Locked, repeatable build for both targets | `build.py qualify --target <t>` locally (x86_64) and `qualify.yml` (both) | any input unverified, any lock entry missing, or any phase reused across changed inputs |
| A2 | Real functional and compatibility behavior | suites `basic`, `parity`, `network`, `projects`, `upstream` | any test red versus the P9 unmodified build, zero tests run, a missing report, or a timeout |
| A3 | Binary purity | D1 audit on every packaged ELF plus contaminated fixtures rejected | any rule in D1 is violated, or the contaminated fixture passes |
| A4 | OpenSSL-free verified HTTPS | D3 suite plus `nm`/`DT_NEEDED` OpenSSL absence | an untrusted, expired, or mismatched certificate succeeds; trusted fails; OpenSSL is present; the lane is `dev-candidate` |
| A5 | Relocatable | packaged-byte qualification in a spaced fresh directory | anything resolves outside the prefix or into the build tree |
| A6 | Atomic, qualification-bound publication | D5 `controller-test -k package`; `release.yml` SHA and evidence checks | a partial or failed candidate activates, or a release proceeds without same-SHA qualification |
| A7 | Native CI for both architectures | D6 green runs | any emulation, or aarch64 qualified off-runner |
| A8 | Measured performance and size versus official CMake | E1 report plus `release-budgets.json` | a claim without a fresh interleaved measurement, or native-versus-emulated comparison |
| A9 | Accurate docs | F1 | a doc states something not executed |
| A10 | Reproducible | `build.py reproduce` | any difference; it is then reported as a defect and reproducibility is not claimed |

## Needs environment

- **Release publication:** the owner runs `gh workflow run release.yml` on the default branch after both `qualify.yml` jobs are green at that SHA.
- **aarch64 qualification**, only if GitHub's `ubuntu-24.04-arm` runner is unavailable to the repo: the owner runs `gh workflow run qualify.yml -f target=aarch64-unknown-linux-musl` when it becomes available. Until then aarch64 is `unqualified`.
- **HTTPS on a CPU below Graviola's floor** (pre-Broadwell x86_64, or a Raspberry Pi 4): the owner runs `cmake -P tests/acceptance/network/https-download.cmake` from the extracted archive. Expected result: a TLS error and exit status 1, not a crash. Until then this is `not executed`.
- **aarch64 performance numbers:** only from the native runner. If it can't produce stable timings, they stay `not measured`.

## Execution boundary and non-goals

- **Authorized:** everything in the Charter's execution grant.
- **Forbidden:**
  - the release dispatch or creating tags;
  - changes to other repositories, including the Laputa recipe pins;
  - QEMU or binfmt emulation;
  - shipping `ccmake`, `cmake-gui`, docs generators, tests, debug info, or caches;
  - shipping a frozen Mozilla root store;
  - importing Alpine shared libraries into the product;
  - disabling TLS verification by default;
  - weakening a test or budget to pass.
- **Non-goals, each with its reason:**
  - glibc, Windows, and macOS targets: out of contract;
  - `_FORTIFY_SOURCE`: musl lacks it (P8);
  - PGO and BOLT as release prerequisites: optional research only;
  - replacing curl with h12tiny: owner decision O2;
  - a shared framework with python-build: forbidden by the brief;
  - Laputa repository edits: handoff only.
- **Contract changes for the owner:**
  - `cmCurl.cxx` trust selection now uses the system platform verifier when no CA file is found. Upstream instead silently ran with whatever curl's build-time default was, and with Rustls that fails closed (P5).
  - The product includes `ctest` and `cpack` to satisfy Laputa's package contract.
  - HTTPS requires Graviola's CPU floor (P5). Below it, `file(DOWNLOAD)` and other HTTPS operations fail with a TLS error, while the rest of `cmake` works.
  - rustls-ffi carries a local provider patch.
  - Any patch added under P7.

## Reference

- **Toolchain `dc0d9b9`:**
  - x86_64: `clang+llvm-23.1.5-x86_64-linux-musl.tar.xz`, sha256 `c43f18f143cc17f49814b6c5dda8a1122d17b6bcdff9848b6f77e97b33026dfe`, 100671508 B.
  - aarch64: sha256 `fe0a382993c36a04a505157b59503a7294db97e2ac9923e5630f8b393b78f118`, 93784384 B.
  - Release target commit `dc0d9b96ab4c5ddb11e308303e0129a559f2235d`. The release is not marked immutable, so the sha256 is the identity.
  - `bin/clang++.cfg` selects lld, compiler-rt, libunwind, and `lib/musl` first.
- **Kitware binaries (P9):**
  - x86_64 sha256 `ed85135c5a5135b45e50423cb406dea04ca3338da0b8ef3c9ede963559680be0`;
  - aarch64 sha256 `301d5063ab259577c1b57ce5490b1aab9ea5c56dc4c822f73499553dab94925f`.
- **CMake source map (4.4.5):**
  - curl options are set in `Utilities/cmcurl/CMakeLists.txt:12-110`: FTP, FILE, HTTP, proxy, and netrc are on; dict, gopher, imap, ldap, and the like are off.
  - The Rustls option is at `:929`, and the 0.15 floor check at `:1158`.
  - CA resolution is in `Source/cmCurl.cxx:128-185`.
  - The Rustls verifier choice is in `Utilities/cmcurl/lib/vtls/rustls.c:1039-1060`.
  - System-library toggles are in `CMakeLists.txt:98-122`.
  - Dialog and debugger options are in `Source/CMakeLists.txt:899,1425-1431`.
- **rustls-ffi `v0.15.7`:** the provider is chosen in `librustls/src/crypto_provider.rs:596-630` (`get_default_or_install_from_crate_features`, `provider_from_crate_features`). The default features are `aws-lc-rs` and `prefer-post-quantum`, and both must stay off.
- **Patterns to read, not copy:**
  - python-build: `buildsys/{inputs,elf,generations,reproduce,sandbox,bootstrap}.py`, `backend/rtls-graviola.patch`, `build/relock_linux.py`, `backend/build-no-openssl.py:914-960`, `docs/{build-system,qualification-and-packaging,ci-and-releases}.md`, `.github/workflows/build.yml`;
  - llvm-prebuilt-musl: `scripts/check-purity.sh`, `README.md`;
  - chromium-build: `docs/linux.md` (cache isolation, staged-runtime tests);
  - Laputa: `packages/cmake/` (4.4.4 recipe and musl patches), `packages/llvm-toolchain/PKGBUILD.xsh`.
