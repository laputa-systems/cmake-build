# Laputa integration

Laputa's existing `cmake` package requires `cmake`, `ctest`, `cpack`, and the
unversioned module-tree path `usr/share/cmake/`. The next distribution is being
prepared to provide all three tools and that resource path. Keep the existing
package until the complete-tools archive is qualified and downstream consumers
have been checked. The published prerelease below contains only `cmake`.

At Laputa commit `c1b407ad272f8ea64542d5e6475f4b45da8299a7`, package recipes
for zlib, expat, freetype, harfbuzz, libevent, libpng, utf8proc, Vulkan
headers and loader, and llvm-static invoke `cmake`. A text search of the
repository found no direct `ctest` or `cpack` invocation outside the CMake
package's payload and proof declarations. That search cannot establish what
interactive users or commands launched by upstream build scripts require.
`build-essential-native` also depends on the full `cmake` package.

The intended integration consumes a qualified complete-tools archive. Preserve
the source-built recipe for rollback until downstream compatibility is proven.

## Consuming a qualified archive

The [qualified prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-5932be3ecbc4-run42907504620-1)
contains these archives:

| Target | Archive SHA-256 |
| --- | --- |
| `x86_64-unknown-linux-musl` | `cbab9ea823b0e1b609b7b3b273e6a9a8c89d3bfdb7aa382d380f880bf7f78e7c` |
| `aarch64-unknown-linux-musl` | `66ec96c09705c67adfa83494bf512dc4b7eb5f6cb0f9d706d8499bb460a1c3a8` |

Select the `x86_64-unknown-linux-musl` or `aarch64-unknown-linux-musl` archive
for the package target. Pin its SHA-256 per architecture in the recipe's
`upstream_sources` and verify it through Laputa's source cache. Require detached
qualification results for the same archive digest and architecture before
updating the pin. Pin the release URL and the independently recorded digest.
GitHub does not currently mark the prerelease immutable, so verify the pinned
digest even when the release includes its own checksum file.

The published CMake-only archive extracts to a relocatable `usr/` prefix with `usr/bin/cmake`,
`usr/share/cmake-4.4/`, and `usr/share/doc/cmake-build/`. The executable finds
its resources relative to its location. Laputa's current package proof instead
requires `usr/share/cmake/Modules/CMake.cmake`; a separate package needs its own
proof for the versioned resource path. Preserve the resource tree when staging.
The complete-tools candidate adds a relative `usr/share/cmake` symlink to
`cmake-4.4` for the existing proof. Its native qualification is pending.

The x86-64 product is static PIE and requires no runtime loader. The native
ELF audit checks the target and runtime closure for each architecture. Curl
uses Rustls and system certificate trust. HTTPS consumers need a system trust
store; compiler and executor dependencies remain those of the downstream
build. The executable needs no host CMake resources, GCC runtime, glibc,
OpenSSL library, D-Bus, or systemd.

Both the build and Laputa's LLVM recipe now pin `llvm-musl-23.1.5-dc0d9b9`.
The compiler archive digest remains the toolchain identity. This agreement
is not proof that every Laputa consumer's compiler, sysroot, or ABI is
compatible: run the consumer with its actual package environment.

Keep the current recipe and its checksums available for rollback. Do not claim
that the published CMake-only prerelease provides `ctest` or `cpack`. For each
selected consumer, compare provisioning cost and normal development work with
the current package, then verify configure, graph generation, compilation,
incremental rebuild, installation, exported metadata, and the consumer's own
tests in an isolated environment. Check for host CMake and unapproved runtime
libraries. This downstream proof has not yet run.

## Proposed downstream proof

Use zlib, libpng, and expat as the first consumer set. The libpng recipe uses
zlib and installs CMake package metadata; the expat recipe also installs CMake
package metadata. Their existing package proofs compile and run programs
against the installed libraries. The libpng recipe disables its upstream tests,
so the package proof does not replace a separate upstream test run.

On each native architecture, prepare two isolated Laputa build environments
with identical pinned sources, toolchains, executor settings, and resource
limits. Keep the existing 4.4.4 recipe in one. In the other, use a separately
approved complete-tools package based on the newly qualified 4.4.5 archive. Confirm that
neither environment finds a host CMake. This comparison includes a CMake version
change and cannot by itself attribute a difference to build flags.

Measure provisioning separately from consumer work. With a fresh artifact
store, build the same closure in each environment:

```sh
make build ARCH=x86_64 PKGS="zlib libpng expat" JOBS=4
```

Repeat with aarch64 on its native host. Record source-cache state, elapsed and
CPU time, peak memory, failures, and per-package logs. A warm unchanged `make
build` may reuse Laputa's artifact store without invoking CMake; label that
result as package-cache reuse rather than CMake reconfiguration. In isolated
consumer build trees, separately measure unchanged reconfiguration and an
incremental source and header rebuild.

Run the installed package proofs, each selected upstream project's applicable
tests, and a downstream CMake project that imports the installed PNG and expat
config packages. Verify the install paths and exports, inspect the generated
Ninja graphs, and audit executables and libraries for the intended architecture
and runtime closure. A failure or an unavailable test remains a recorded gap.
This proof requires a Laputa integration change and has not yet run.
