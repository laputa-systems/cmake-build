# CMake for musl

Relocatable CMake 4.4.5 for native x86-64 and aarch64 Linux systems using musl.
The distribution uses the pinned LLVM/musl toolchain and Rustls with system
certificate trust. It contains `usr/bin/cmake` and its resources under
`usr/share/cmake-4.4/`.
It does not include `ctest` or `cpack`.

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

See [building](docs/building.md), [build measurements](docs/build-system.md), [dependencies](docs/dependencies.md),
[qualification](docs/qualification.md), [CI and prereleases](docs/ci-and-releases.md), and [Laputa integration](docs/laputa-integration.md).
