# CMake for musl

Relocatable CMake 4.4.5 for native x86-64 and aarch64 Linux systems using musl.
The distribution uses the pinned LLVM/musl toolchain and Rustls with system
certificate trust. It contains `usr/bin/cmake`, `usr/bin/ctest`, and
`usr/bin/cpack`, with resources under `usr/share/cmake-4.4/`.
The earlier published prerelease contains only `cmake`.

```sh
make fetch TARGET=x86_64-unknown-linux-musl
make verify TARGET=x86_64-unknown-linux-musl
make repro TARGET=x86_64-unknown-linux-musl
```

The targets call the `build.py` phases directly:

```sh
python3 build.py fetch --target x86_64-unknown-linux-musl
python3 build.py qualify --target x86_64-unknown-linux-musl
python3 build.py reproduce --target x86_64-unknown-linux-musl
```

Build each target on a machine of the same architecture. Downloads are pinned
and verified; builds run in a network-isolated container. Developer builds
reuse a persistent compiler cache. Qualification includes explicit network
checks, tests the exact archive, and records results separately from its
embedded metadata.

See [building](docs/building.md), [build measurements](docs/build-system.md), [executable performance](docs/performance.md), [dependencies](docs/dependencies.md),
[qualification](docs/qualification.md), [CI and prereleases](docs/ci-and-releases.md), and [Laputa integration](docs/laputa-integration.md).
