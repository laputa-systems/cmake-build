# cmake-build

`make clean` removes the root Ruff cache and transient build, Rust, and phase outputs.
It preserves installed dependencies and unrelated scratch files.

Relocatable CMake 4.4.5 distribution for `x86_64-unknown-linux-musl` and
`aarch64-unknown-linux-musl`, built with the pinned LLVM/musl toolchain.

## Commands

```sh
make lint                                   # ruff and ty
make test                                   # portable controller checks
make test-native                            # prepared native audit and TLS checks (after fetch and prepare)
make coverage                               # branch coverage in the prepared native builder
make fetch TARGET=x86_64-unknown-linux-musl   # also: build, package, verify (qualify), repro (reproduce), clean
python3 build.py controller-test            # controller suite, exit 0 or 1
python3 build.py controller-test -k tls     # module-name filter
python3 build.py doctor --target x86_64-unknown-linux-musl
python3 build.py fetch --target x86_64-unknown-linux-musl
python3 build.py test --target x86_64-unknown-linux-musl --suite basic
python3 build.py test --target x86_64-unknown-linux-musl --suite parity
python3 build.py test --target x86_64-unknown-linux-musl --suite network
python3 build.py test --target x86_64-unknown-linux-musl --suite projects,upstream
python3 build.py package --target x86_64-unknown-linux-musl
python3 build.py qualify --target x86_64-unknown-linux-musl
python3 build.py reproduce --target x86_64-unknown-linux-musl
python3 build.py benchmark --target x86_64-unknown-linux-musl
```

`make test` needs only `make setup`. `make test-native` runs the `test_native_*` modules and needs
`fetch` and `prepare` for the native target first; the TLS dependency gate checks the locked,
vendored Cargo graph offline without Docker. `controller-test` without `--scope` runs both.
Run `make coverage` after preparing the native compiler and the pinned
`jaq` under `.work/tools`, as in the hosted controller job. It measures the
same suite in the sealed Alpine builder and writes
`.work/coverage/controller-<target>.json`.
`package` creates a candidate archive; `qualify` runs the project and upstream
suites and qualifies the extracted archive before activation. `benchmark`
requires a qualified generation, an unmodified musl baseline, and host `strace`.
It writes the measured report and checks size and memory budgets after five runs.
An unmeasured memory baseline can be established only with its recorded archive.

## Verification

- On the prepared hosted x86_64 Linux builder, `make test-ci` passed 113 tests in 21 modules twice at 9.17 s and 9.41 s elapsed. Those runs include the sealed test launch and exclude native build preparation. [Cost measurement](https://github.com/laputa-systems/cmake-build/pull/9)
- On macOS ARM64, `make lint` passed in 1.22 s on the first run and 1.18 s warm. The controller suite needs the prepared Linux builder for the full check.
- CI reuses the native build phases across edits confined to `tests/controller/`. The full controller suite runs after native phase preparation. Changes to the build sources and native fixtures change the phase cache key.
- `tests/controller/test_cli.py` exercises CLI arguments and exit codes. `test_inputs.py`, `test_bootstrap.py`, and `test_buildlib_wheel.py` check locks, acquisition, byte identity, and the pinned wheel.
- `test_sandbox.py`, `test_tls.py`, and the prepared-native `test_native_tls.py` check network, toolchain, and dependency boundaries; `test_native_audit.py` checks ELF hardening with the prepared toolchain. `test_phases.py` checks build phase records and invalidation.
- `test_package_archive.py`, `test_package_generations.py`, and `test_package_reproduce.py` check archive and generation contracts. `make verify` separately qualifies real archives and project consumers.
- The shipped CMake, CTest, and CPack CLI contracts are exercised by the basic, project, and upstream qualification suites. Certificate trust and network behavior have their own suite.
- `build.py benchmark` measures declared command workloads and size and memory limits on qualified candidate and reference archives. Its prerequisites and baselines are in [Building and qualification](docs/building.md).
- `sources.lock.json` records the upstream artifacts and digests. The tracked license notices are under `licenses/`.

## Layout

- `Makefile` — `build`, `verify`, `lint`, `clean`, `fetch`, `package`, and `repro` map to `build.py` phases; `TARGET` is a Rust target triple.
- `build.py` — argument parsing and dispatch only.
- `buildsys/targets.py` — the supported Linux targets taken from `buildlib`, plus their CPU baselines.
- `buildsys/inputs.py` — repository rules over `buildlib` lock loading, content-addressed cache, safe extraction.
- `buildsys/buildlib_wheel.py` — puts the locked `laputa-buildlib` wheel from the input cache on `sys.path`; every context imports `buildlib` through `buildsys`.
- `buildsys/phases.py` — input-fingerprinted phase records.
- `sources.lock.json` — upstream sources, toolchains, and reference binaries.
- `bootstrap.lock.json` — pinned Alpine and Debian image indexes, apks, and Rust components.
- `tests/controller/` — controller suite.

## Documentation

- [Roadmap and current status](docs/roadmap.md)
- [Building and qualification](docs/building.md)
- [Build measurements](docs/build-system.md)
- [CMake executable performance](docs/performance.md)
- [x86-64 memory baseline](docs/performance-baseline-x86_64.md)
- [ARM executable performance](docs/performance-aarch64.md)
- [ARM memory baseline](docs/performance-baseline-aarch64.md)
- [Earlier x86-64 performance results](docs/performance-legacy-x86_64.md)
- [Earlier ARM performance results](docs/performance-legacy-aarch64.md)
- [Rustls release-profile study](docs/performance-rust-release.md)
- [Optimization level study](docs/performance-o2.md)
- [Size-oriented optimization study](docs/performance-oz.md)
- [ThinLTO provenance probe](docs/performance-thinlto.md)
- [Section garbage collection study](docs/performance-gc.md)
- [LLVM reconfiguration CPU profile](docs/profiles/llvm-reconfigure.md)
- [Initial performance analysis](docs/performance-analysis.md)
- [Dependency inventory](docs/dependencies.md)
- [Qualification results](docs/qualification.md)
- [CI and prereleases](docs/ci-and-releases.md)
- [Laputa integration](docs/laputa-integration.md)

## Build rules

- Every downloaded byte is pinned by sha256 and size and is verified on both
  cache read and cache write. Never lock on first fetch.
- All scratch, caches, downloads, and build trees live under `.work/`. Never
  use `/tmp` or `$TMPDIR`; export `TMPDIR=$PWD/.work/tmp` for builds.
- A phase is reused only when its input fingerprint and its output tree digest
  both match. A killed phase never leaves a completion record.
- Targets build natively on their own machine. No emulation anywhere.
- No formatters. Commits are Conventional Commits with the workstream scope.
