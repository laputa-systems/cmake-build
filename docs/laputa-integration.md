# Laputa integration

Laputa's existing `cmake` package is the safe default when complete CMake tools
are required. The qualified archive is suitable for a separate CMake-only
build tool after consumer-specific validation. Do not replace the existing
package wholesale: its declared payload and proof require `cmake`, `ctest`,
and `cpack`, but this distribution contains only `cmake`.

At Laputa commit `c1b407ad272f8ea64542d5e6475f4b45da8299a7`, package recipes
for zlib, expat, freetype, harfbuzz, libevent, libpng, utf8proc, Vulkan
headers and loader, and llvm-static invoke `cmake`. A text search of the
repository found no direct `ctest` or `cpack` invocation outside the CMake
package's payload and proof declarations. That search cannot establish what
interactive users or commands launched by upstream build scripts require.
`build-essential-native` also depends on the full `cmake` package.

Three integration choices remain:

- Use the CMake-only archive for a separate build-tool package or isolated
  consumer workflow. Keep the existing package for complete tooling.
- Produce separately qualified `ctest` and `cpack` packages from the same
  toolchain if consumers need them and their ownership and upgrades are defined.
- Keep Laputa's existing source-built package unchanged where the complete
  contract is needed. This is the current recommendation until downstream
  compatibility is proven.

## Consuming a qualified archive

Select the `x86_64-unknown-linux-musl` or `aarch64-unknown-linux-musl` archive
for the package target. Pin its SHA-256 per architecture in the recipe's
`upstream_sources` and verify it through Laputa's source cache. Require detached
qualification results for the same archive digest and architecture before
updating the pin. Pin a published immutable asset rather than a moving URL.

The archive extracts to a relocatable `usr/` prefix with `usr/bin/cmake`,
`usr/share/cmake-4.4/`, and `usr/share/doc/cmake-build/`. The executable finds
its resources relative to its location. Laputa's current package proof instead
requires `usr/share/cmake/Modules/CMake.cmake`; a separate package needs its own
proof for the versioned resource path. Preserve the resource tree when staging.

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

Keep the current recipe and its checksums available for rollback. A proposed
CMake-only package must not claim to provide `ctest` or `cpack`. For each
selected consumer, compare provisioning cost and normal development work with
the current package, then verify configure, graph generation, compilation,
incremental rebuild, installation, exported metadata, and the consumer's own
tests in an isolated environment. Check for host CMake and unapproved runtime
libraries. This downstream proof has not yet run.
