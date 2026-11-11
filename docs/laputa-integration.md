# Laputa integration

Laputa's existing `cmake` package requires `cmake`, `ctest`, `cpack`, and the
unversioned module-tree path `usr/share/cmake/`. The complete-tools prerelease
provides all three tools and that resource path. Keep the existing package
until downstream consumers have been checked in Laputa's package environment.

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

The [qualified complete-tools prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-40f84aef2341-run42938731214-1)
contains these archives:

| Target | Archive SHA-256 |
| --- | --- |
| `x86_64-unknown-linux-musl` | `fc6ed71475af45e4db67895addffaffd291588d12c49190d734dcafa2b73d73b` |
| `aarch64-unknown-linux-musl` | `d05210064fb9a5a6bde7c663a4e9c1336bd9d53f6e3bc1b1d0b9fd14437b1057` |

Select the `x86_64-unknown-linux-musl` or `aarch64-unknown-linux-musl` archive
for the package target. Pin its SHA-256 per architecture in the recipe's
`upstream_sources` and verify it through Laputa's source cache. Require detached
qualification results for the same archive digest and architecture before
updating the pin. Pin the release URL and the independently recorded digest.
GitHub does not currently mark the prerelease immutable, so verify the pinned
digest even when the release includes its own checksum file.

For the Laputa recipe, set the package version to `4.4.5` and select the
archive matching the target architecture. Install its `usr/` tree into the
package destination without rebuilding it. Retain the declared executables and
run the existing package proof. Keep compiler and executor dependencies needed
by downstream builds. The archive itself has no dynamic runtime dependency;
HTTPS needs a system certificate store.

The archive extracts to a relocatable `usr/` prefix with `usr/bin/cmake`,
`usr/bin/ctest`, `usr/bin/cpack`, `usr/share/cmake-4.4/`, and
`usr/share/doc/cmake-build/`. The executables find their resources relative to
their location. The relative `usr/share/cmake` symlink points to `cmake-4.4`,
so Laputa's existing module-tree proof can find `Modules/CMake.cmake`.
Preserve the resource tree and symlink when staging the package.

Both products are static PIE and require no runtime loader. The native
ELF audit checks the target and runtime closure for each architecture. Curl
uses Rustls and system certificate trust. HTTPS consumers need a system trust
store; compiler and executor dependencies remain those of the downstream
build. The executable needs no host CMake resources, GCC runtime, glibc,
OpenSSL library, D-Bus, or systemd.

Both the build and Laputa's LLVM recipe now pin `llvm-musl-23.1.5-dc0d9b9`.
The compiler archive digest remains the toolchain identity. This agreement
is not proof that every Laputa consumer's compiler, sysroot, or ABI is
compatible: run the consumer with its actual package environment.

Keep the current recipe and its checksums available for rollback. For each
selected consumer, compare provisioning cost and normal development work with
the current package, then verify configure, graph generation, compilation,
incremental rebuild, installation, exported metadata, and the consumer's own
tests in an isolated environment. Check for host CMake and unapproved runtime
libraries. This downstream proof has not yet run.

An x86-64 check against the extracted archive exercised the version, module
path, and a fresh configure modeled on the existing package proof. It used a
shell stand-in for Laputa's `xsh` Ninja probe. The actual Laputa proof has not
run.

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
