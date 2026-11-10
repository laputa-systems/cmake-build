# cmake-build

Relocatable CMake 4.4.5 distribution for `x86_64-unknown-linux-musl` and
`aarch64-unknown-linux-musl`, built with the pinned LLVM/musl toolchain.

## Commands

```sh
python3 build.py controller-test            # controller suite, exit 0 or 1
python3 build.py controller-test -k tls     # module-name filter
python3 build.py doctor --target x86_64-unknown-linux-musl
python3 build.py fetch --target x86_64-unknown-linux-musl
```

`prepare`, `configure`, `build`, `test`, `package`, `qualify`, `reproduce`, and
`benchmark` are registered and fail with a clear message until their slices
land.

## Layout

- `build.py` — argument parsing and dispatch only.
- `buildsys/targets.py` — the only architecture-specific data.
- `buildsys/inputs.py` — lock schemas, content-addressed cache, safe extraction.
- `buildsys/phases.py` — input-fingerprinted phase records.
- `sources.lock.json` — upstream sources, toolchains, and reference binaries.
- `bootstrap.lock.json` — pinned Alpine image, apks, and Rust components.
- `tests/controller/` — controller suite.

## Build rules

- Every downloaded byte is pinned by sha256 and size and is verified on both
  cache read and cache write. Never lock on first fetch.
- All scratch, caches, downloads, and build trees live under `.work/`. Never
  use `/tmp` or `$TMPDIR`; export `TMPDIR=$PWD/.work/tmp` for builds.
- A phase is reused only when its input fingerprint and its output tree digest
  both match. A killed phase never leaves a completion record.
- Targets build natively on their own machine. No emulation anywhere.
- No formatters. Commits are Conventional Commits with the workstream scope.
