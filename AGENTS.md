# cmake-build

Relocatable CMake 4.4.5 distribution for `x86_64-unknown-linux-musl` and
`aarch64-unknown-linux-musl`, built with the pinned LLVM/musl toolchain.

## Commands

```sh
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

Run `fetch` for the native target before `controller-test`; the TLS dependency
gate checks the locked, vendored Cargo graph offline without Docker.
`package` creates a candidate archive; `qualify` runs the project and upstream
suites and qualifies the extracted archive before activation. `benchmark`
requires a qualified generation, an unmodified musl baseline, and host `strace`.
It writes the measured report and checks size and memory budgets after five runs.
An unmeasured memory baseline can be established only with its recorded archive.

## Layout

- `build.py` — argument parsing and dispatch only.
- `buildsys/targets.py` — the only architecture-specific data.
- `buildsys/inputs.py` — lock schemas, content-addressed cache, safe extraction.
- `buildsys/phases.py` — input-fingerprinted phase records.
- `sources.lock.json` — upstream sources, toolchains, and reference binaries.
- `bootstrap.lock.json` — pinned Alpine and Debian image indexes, apks, and Rust components.
- `tests/controller/` — controller suite.

## Documentation

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
