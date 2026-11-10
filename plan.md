# Implement laputa-systems/cmake-build

You are an autonomous senior build-systems and toolchain engineer. Implement a complete, production-quality repository named `laputa-systems/cmake-build`.

**This is an implementation assignment, not a research or planning assignment.** Inspect the reference repositories, establish the architecture, write the build system, build and qualify real artifacts wherever the environment permits, fix failures, write tests and documentation, and commit the completed changes.

Work unattended. Make reasonable technical decisions without asking for approval. Never claim a validation passed unless it actually ran and passed.

## 1. Reference implementations

Thoroughly inspect these repositories before implementation:

- https://github.com/laputa-systems/python-build
- https://github.com/laputa-systems/chromium-build
- https://github.com/laputa-systems/llvm-prebuilt-musl
- https://github.com/laputa-systems/laputa

Pay particular attention to:

**python-build**
- `AGENTS.md`
- `build.py`, `buildsys/`, `bootstrap.lock.json`, `sources.lock.json`
- `docs/build-system.md`
- `docs/qualification-and-packaging.md`
- `docs/ci-and-releases.md`
- `buildsys/elf.py`, `buildsys/inputs.py`, `buildsys/generations.py`
- Controller tests, sealed builds, release generations, and artifact acceptance.

**chromium-build**
- Build orchestration and resumable phases.
- Source and dependency locking.
- Native musl compilation.
- Compiler/linker identity checks.
- Independent binary and build-graph audits.
- Functional and packaged-runtime acceptance.
- Compiler-cache behavior and isolation.

**llvm-prebuilt-musl**
- Compiler/runtime package contracts.
- `clang.cfg`, `clang++.cfg`, compiler-rt, libc++, libunwind, and bundled musl.
- Exact release archives and validation requirements.
- GCC-free dependency enforcement and purity checks.

**laputa**
- Package layout and the current `llvm-toolchain` recipe.
- Runtime dependencies, sysroot expectations, package consumption, and compatibility requirements.

Reuse engineering patterns, not gratuitous code duplication. Do not introduce a shared framework or modify the reference repositories merely to simplify this implementation.

## 2. Product contract

Build a small, fast, secure, relocatable, fully functional upstream CMake distribution.

Start with **upstream CMake 4.4.5** from Kitware, pinned to the exact source release with a verified checksum. No moving branches, floating versions, or unverified downloads.

Production targets:

- `x86_64-unknown-linux-musl`
- `aarch64-unknown-linux-musl`

No glibc target, Windows, or macOS build in this campaign. Linux architectures must build natively, not under QEMU emulation.

The distributed product must contain:

- The actual `cmake` executable.
- All essential CMake modules, platform definitions, compiler detection files, templates, and runtime resources.
- Required legal notices and version/provenance metadata.

The normal product must not contain:

- `ccmake`, `cmake-gui`, `cpack`, or `ctest` executables.
- GUI dependencies, documentation generators, tests, or development-only build tools.
- GCC runtime libraries, libstdc++, libgcc_s, glibc, or OpenSSL.
- Unnecessary shared libraries, debug symbols, build caches, or temporary files.

Build-only `ctest` is permitted and encouraged for upstream regression qualification. Do not sacrifice testing merely to reduce the release payload.

**Critical:** This is a distribution of actual CMake with its established language semantics and generator compatibility. It is not a new CMake interpreter or a limited CMake-compatible frontend.

Keep full ordinary functionality: script mode, configure/generate, Ninja and Makefile generators, compiler detection, `try_compile`, generator expressions, package discovery, install/export, presets, file API, and CMake's command-line utility operations.

Do not remove an upstream feature just because the initial tests do not exercise it.

## 3. Authoritative compiler and runtime

Use:

https://github.com/laputa-systems/llvm-prebuilt-musl

Current reference version: LLVM/Clang/LLD 23.1.5.

This toolchain provides:

- `clang`, `clang++`, `ld.lld`
- LLVM binutils
- compiler-rt
- static libc++, libc++abi, and libunwind
- clang-built musl libc and startup objects

It deliberately avoids GNU runtime code.

Use this toolchain to compile and link **every shipped native object**, including dependency libraries.

The Python-build and Laputa repositories currently reference different release revisions of the same LLVM 23.1.5 toolchain. Investigate and reconcile this explicitly. Select one verified, immutable release and record the complete asset identity in the lock. Never silently mix them.

Set explicit CC, CXX, AR, RANLIB, NM, STRIP, compiler target, linker, and sysroot configuration. Use the toolchain's configured defaults where appropriate.

Only obtain target musl headers and Linux headers from verified sysroot inputs. The packaged toolchain must supply the runtime/startup objects. Do not accidentally link Alpine's GCC-built startup objects or libc archive.

Before building CMake, run a standalone compiler-provenance fixture proving:

1. C and C++ compile correctly.
2. Static and dynamic musl linking work.
3. C++ exceptions, destructors, and filesystem functionality work.
4. Compiler-rt and libc++ are actually selected.
5. ThinLTO compilation, archiving, linking, and execution work.
6. ELF output has the expected machine architecture and runtime closure.

Fail closed if any compiler or linker falls back to an unapproved executable or library.

## 4. Source and dependency policy

Build from immutable, checksum-verified inputs.

Implement:

- `sources.lock.json`
- `bootstrap.lock.json`
- A documented patch inventory with hashes, rationale, and application order.
- A complete build-time dependency inventory, including upstream-bundled libraries.

Follow python-build's patterns for verifying cached and freshly downloaded bytes, rejecting hostile archive paths, and refusing invalid source or toolchain identities.

Prefer CMake's upstream-bundled libraries where they reduce dependency complexity, provided they are compiled using our Clang toolchain and their licensing and runtime behavior are acceptable.

Study CMake's bundled bzip2, curl, expat, jsoncpp, libarchive, liblzma, librhash, libuv, nghttp2, zlib, and zstd arrangements.

Do not automatically import Alpine's shared versions.

Inspect the actual CMake target graph. Determine which dependencies are reachable from the `cmake` executable and which belong exclusively to CPack, CTest, the debugger, or GUI.

Eliminate unnecessary build targets through upstream-supported configuration first. Maintain a small, well-documented patch series only where upstream offers no suitable mechanism.

Do not carry forks of large libraries when straightforward upstream configuration or a small surgical patch suffices.

### HTTPS and TLS

The release must support secure HTTPS downloads for normal CMake workflows.

The product must remain OpenSSL-free.

Investigate a statically linked libcurl with a Rustls backend, using a pinned and audited Rustls C ABI implementation where appropriate. Prefer existing trustworthy upstream infrastructure.

Use system-configured certificate trust. Do not ship a private, permanently frozen Mozilla root store.

Verify actual TLS certificate validation, hostname checking, and rejection of untrusted certificates. Support standard certificate configuration mechanisms.

Do not disable certificate verification or silently drop HTTPS functionality to make a smaller binary.

If OpenSSL-free HTTPS proves difficult, establish a separately identified development candidate and document the blocker. Do not promote a release that fails the product contract.

## 5. Build architecture

Implement a small, understandable orchestration layer, preferably using standard-library Python following python-build's separation of concerns.

Provide an entry point resembling:

```text
python3 build.py doctor
python3 build.py fetch --target <triple>
python3 build.py prepare --target <triple>
python3 build.py configure --target <triple>
python3 build.py build --target <triple>
python3 build.py test --target <triple>
python3 build.py package --target <triple>
python3 build.py qualify --target <triple>
python3 build.py reproduce --target <triple>
python3 build.py benchmark --target <triple>
python3 build.py controller-test
```

Make clean operations non-destructive to externally supplied sources and caches.

Use explicit phases with content-based fingerprints. A phase can be reused only when all its relevant inputs match.

Builds must be resumable and idempotent.

Separate:

1. Network-enabled, verification-enforced input acquisition.
2. Offline preparation and configuration.
3. Offline native compilation.
4. Runtime staging.
5. Isolated qualification of staged and packaged bytes.
6. Atomic publication of immutable artifacts.

Do not allow network access during sealed compilation. Record evidence of the enforced boundary.

### Bootstrap strategy

CMake can bootstrap itself, but its source bootstrap can be costly.

Investigate the fastest trustworthy approach:

- A separately pinned build-host CMake used only to configure the production build.
- CMake's own bootstrap as a verified fallback.
- Ninja versus Samurai as the build executor.

Measure the alternatives. Prefer the faster, maintainable path with equivalent final-artifact correctness.

The bootstrap CMake is never part of the product.

The production compiler must always remain our selected LLVM/musl toolchain, regardless of how the initial configuration is executed.

## 6. Compilation and optimization

The objective is a small and fast executable without compromising compatibility.

Establish a conventional, reproducible Release baseline before optimizing.

Investigate, measure, and selectively adopt:

- `-O2`, `-O3`, and `-Oz`
- Function/data sections and linker garbage collection
- ThinLTO
- LLD identical-code folding where safe
- Symbol visibility and symbol stripping
- Static PIE versus musl-dynamic linking
- Incremental rebuilds and compiler caching
- Exclusion of truly unreachable optional targets
- Build parallelism and memory-bound linking limits

Do not indiscriminately combine flags.

Retain necessary C++ language behavior, including exceptions and RTTI where required. Do not use unsafe optimization assumptions or host-specific `-march=native` in release artifacts.

Prefer fully static PIE if it is demonstrably compatible with the complete product contract.

Otherwise use a strictly audited musl-only dynamic closure, ideally with no external C++ runtime dependencies. Record the tradeoff.

Never assume static linkage is superior without measuring its size, startup cost, and functionality.

PGO and BOLT are optional research lanes, not prerequisites for an initial accepted release.

## 7. Functional validation

Build a real acceptance suite, not merely a collection of version-string checks.

Test the actual extracted distribution in a clean environment with no access to the original build tree.

Mandatory areas:

**CLI and scripting:** `--version`, `--help`, `-E`, `-P`, `-S`, `-B`, `--build`, `--install`, presets, file API, and basic cache operations.

**C/C++ projects:** configure, compile, link, install, and run a small C and C++ project using our LLVM/musl compiler.

**Build graph:** multiple libraries, PUBLIC/PRIVATE/INTERFACE dependencies, imported targets, generator expressions, source generation, custom commands, and transitive includes.

**Compiler features:** language detection, feature checks, `try_compile`, and appropriate `try_run` behavior.

**Packages:** `find_package`, config-mode package discovery, module-mode discovery, install/export, and downstream consumption of an installed exported target.

**Generators:** Ninja and Unix Makefiles. Test generated commands and incremental rebuilding, including correctly detecting a modified source, header, or build definition.

**Resources:** confirm `CMAKE_ROOT` resolves inside the relocated package and essential modules are found without falling back to a host CMake installation.

**Networking:** HTTPS downloads, redirects where appropriate, trusted and untrusted certificates, checksum validation, and at least one representative network-based CMake workflow.

**Archive operations:** CMake's tar creation and extraction behavior and its relevant `file(ARCHIVE_*)` commands.

**Real projects:** configure and build multiple pinned, reasonably representative upstream CMake projects, including one with nontrivial custom commands and dependencies.

Run a meaningful subset of CMake's upstream regression tests, supplemented by our own compatibility tests.

When useful, compare outputs against an unmodified reference CMake of the exact same version. Report differences rather than assuming they are harmless.

### Negative controls

Explicitly test:

- Corrupted downloaded inputs.
- Missing or modified lock entries.
- Unexpected toolchain identity.
- Architecture mismatch.
- Source archive traversal and unsafe symlinks.
- Attempts to fetch during offline build phases.
- Unapproved ELF dependencies.
- Broken relocation.
- Missing runtime resources.
- TLS certificate verification failures.
- Incomplete or interrupted qualification.
- Stale output from a previous build fingerprint.

Failures, timeouts, missing test reports, and zero executed tests must not become passing verdicts.

## 8. Binary purity audit

Create an independent ELF auditor, modeled on the strongest purity checks in python-build and llvm-prebuilt-musl.

Validate all packaged executables and shared objects using LLVM binary tools.

Require:

- Exact architecture.
- Approved musl interpreter, if dynamically linked.
- Approved `DT_NEEDED` closure.
- No glibc or `GLIBC_*` dependencies.
- No libgcc, libgcc_s, or libstdc++.
- No OpenSSL dependency or embedded OpenSSL runtime.
- No GCC-compiled objects, including through static libraries.
- No unapproved GNU symbol-version requirements.
- Non-executable stack.
- Appropriate PIE, RELRO, and binding hardening for the chosen linkage.
- No unexpected RPATH/RUNPATH or builder-host paths.

Inspect object provenance and archive members before final linking where necessary; final ELF metadata alone cannot prove every static object came from Clang.

Build a negative-control fixture showing that the auditor rejects a deliberately contaminated binary.

Do not establish purity by grepping only `ldd`.

## 9. Packaging and reproducibility

Produce one immutable archive for each target:

```text
cmake-4.4.5-x86_64-unknown-linux-musl.tar.xz
cmake-4.4.5-aarch64-unknown-linux-musl.tar.xz
```

Include a machine-readable `artifact.json` containing:

- Source version and digest.
- Repository commit and patch-set identity.
- LLVM toolchain release, digest, and compiler identity.
- Target architecture and CPU baseline.
- Effective compiler and linker flags.
- Build-time dependency closure.
- Build mode and isolation evidence.
- Artifact file inventory and cryptographic hashes.
- ELF audit results.
- Complete qualification summary.
- Archive size and unpacked size.

Construct deterministic archives with normalized ownership, ordering, permissions, and timestamps.

After packaging, extract the exact archive to a fresh directory whose name contains spaces. Perform runtime and functional tests against those extracted bytes.

Implement python-build-style immutable generations and atomic active-artifact selection.

Never replace a previously accepted artifact with a partial or failed candidate.

Implement independent clean-build reproducibility comparison. Check file types, permissions, symlink targets, content, archive bytes, and embedded build paths.

Fix reproducibility defects where feasible; otherwise report them explicitly and do not claim reproducibility.

Record third-party licenses and provide the necessary notices.

## 10. Performance and size evaluation

Measure the resulting tool against an official upstream CMake build of the same version.

Use identical target projects, the same native machine, controlled environments, and repeated runs.

Record:

- Clean CMake compilation wall time and peak memory.
- Incremental CMake compilation wall time.
- Configure/generate time on small, medium, and large projects.
- Reconfigure time with no changes.
- Reconfigure time after a relevant input change.
- Startup and `cmake -P` execution latency.
- Peak RSS during configuration.
- Executable size.
- Installed runtime-resource size.
- Compressed archive size.

Include cold and warm filesystem-cache results when practical; distinguish them clearly.

Measure toolchain options rather than making performance claims from intuition.

Do not compare native x86-64 timing with emulated AArch64 timing.

Establish an initial size and performance budget from measured baseline artifacts. Document the rationale and detect meaningful regressions.

Avoid overengineering marginal optimizations. Prefer simple, sustainable improvements with demonstrable benefit.

## 11. CI and releases

Mirror the mature CI discipline of python-build.

Provide:

- Fast controller and policy tests.
- Native x86-64 qualification.
- Native AArch64 qualification.
- Clean-container runtime validation.
- Artifact assembly and integrity checks.
- Manual release dispatch.
- Source/commit/tag identity verification.
- Immutable published artifacts and checksums.

Use GitHub's native ARM64 runners where available.

Expensive native builds should not run automatically on every trivial commit. Keep normal checks cheap and releases intentional.

A release must require current, complete qualification at the exact source revision. Historical CI success cannot substitute for current evidence.

Do not upload or publish an unqualified artifact.

## 12. Repository structure and documentation

Keep the repository compact and understandable. Suggested layout:

```text
cmake-build/
  AGENTS.md
  README.md
  build.py
  sources.lock.json
  bootstrap.lock.json
  release-budgets.json
  buildsys/
  patches/
  tests/
  docs/
  .github/workflows/
```

Produce concise, authoritative documentation covering:

- Product and target contracts.
- Bootstrap and toolchain architecture.
- Source and dependency provenance.
- Exact build commands.
- Offline build isolation.
- Native dependency and ELF purity policies.
- Qualification matrix and evidence.
- Packaging, relocation, and reproducibility.
- Performance measurements and optimization decisions.
- Integration instructions for Laputa.
- Outstanding limitations and follow-up work.

Keep the README accessible; put detailed engineering contracts in `docs/`.

Add a useful `AGENTS.md` for subsequent maintenance.

Avoid speculative abstraction layers, duplicated validation logic, large dependencies in the orchestrator, or meaningless configuration knobs.

## 13. Laputa consumption

The resulting CMake installation must be suitable for use inside Laputa's musl environment.

Document how its binary and resources should be incorporated into a Laputa package or build-tool root.

Prove operation with the prebuilt LLVM toolchain and the chosen Ninja/Samurai executor.

Ensure that it does not require D-Bus, systemd, glibc, GCC runtimes, or host-installed CMake resource files.

Keep changes to the Laputa repository out of scope unless explicitly authorized. Deliver a precise integration handoff instead.

## 14. Execution discipline

Proceed in this order:

**Phase A — reconnaissance:** Read the reference repositories and the pinned upstream CMake source. Identify the actual target graph, toolchain requirements, optional components, dependency closure, and bootstrap paths.

**Phase B — viability:** Prove native Clang/musl C++ compilation, static/runtime closure, basic CMake compilation, and OpenSSL-free HTTPS. Eliminate architectural unknowns before spending effort on a full build.

**Phase C — minimum complete product:** Implement a locked, repeatable build producing a functioning CMake executable and its required resources. Qualify basic compiler, generator, and relocation behavior.

**Phase D — hardening:** Add sealed isolation, independent audits, negative controls, real-project compatibility tests, reproducibility, and transactional packaging.

**Phase E — optimization:** Benchmark, reduce unnecessary targets and dependencies, evaluate compiler/linker settings, and establish measured budgets.

**Phase F — release engineering:** Add native CI, archive-bound qualification, documentation, and release controls.

Do not stop after producing plans or scaffolding.

Make real implementation progress on every phase. Prioritize the minimum complete, working product over prematurely exhaustive infrastructure.

Use focused checks while developing. Do not run unrelated formatters, modify unrelated repositories, or launch expensive CI speculatively.

If the available environment cannot execute an architecture's native build, complete its deterministic build/CI support and explicitly mark that architecture unqualified. Never substitute emulation as native performance evidence.

## 15. Completion criteria

The project is complete only when:

1. Both supported architectures have a reproducible, locked build procedure.
2. The resulting CMake distribution passes real functional and compatibility tests.
3. Every packaged binary passes independent architecture and runtime-purity audits.
4. HTTPS works with certificate verification and without OpenSSL.
5. The extracted distribution works from an arbitrary relocated prefix.
6. Packaging and publication are atomic and qualification-bound.
7. Native CI can build and independently validate both architectures.
8. Performance and size are measured against an appropriate baseline.
9. Documentation accurately reflects implemented and verified functionality.

Anything not executed must be recorded as not executed, not passed.

Commit the implementation with conventional commit messages, following the repository's authorization and push rules. Do not open a PR unless required.

In the final report include the commit SHA, exact implemented scope, actual tests executed, per-architecture verdicts, artifact sizes where measured, performance results, and any remaining blockers.

**Governing principle:** Maintain python-build's level of correctness, provenance, and packaging rigor, chromium-build's real-world acceptance discipline, and llvm-prebuilt-musl's strict GCC-free toolchain purity. Optimization must never weaken these guarantees.
