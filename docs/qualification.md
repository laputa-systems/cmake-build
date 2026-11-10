# Qualification

## Preliminary x86-64 parity

The graph and archive fixtures passed on the staged CMake 4.4.5 binary and Kitware's official 4.4.5 binary. The candidate ran in the locked Alpine builder. The reference ran in Debian trixie-slim at image index `sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`. Both used the pinned LLVM toolchain on the same native x86-64 host.

The graph fixture exercised Ninja and Unix Makefiles, compiler checks, generated files, transitive and imported targets, module and config packages, installation, downstream consumption, incremental builds, presets, file API replies, and selected system-information fields. The archive fixture created and extracted gzip, xz, bzip2, zstd, and zip archives through both `cmake -E tar` and `file()`.

The selected system-information fields matched. The Ninja build files differed in the `edit_cache` command: the reference distribution includes `ccmake`, and the staged distribution does not. The file API cache replies also differed in these fields:

- The reference included `CMAKE_EDIT_COMMAND` for `ccmake`.
- `CMAKE_INSTALL_SO_NO_EXE` was `1` in Debian and `0` in Alpine. The bundled Linux platform module selects that default from `/etc/debian_version`.
- The Makefiles generator selected `/usr/bin/make` in Debian and `/usr/bin/gmake` in Alpine.
- The detected `uname` path was `/usr/bin/uname` in Debian and `/bin/uname` in Alpine.

The Ninja codemodel listed the `base` and `wrapper` dependencies in the opposite order, and the target reply filename differed. Both generated executables and the downstream executable ran successfully. The effect of the dependency ordering on other consumers has not been established.

These runs cover the fixtures above, not the complete parity, networking, project, or upstream suites.

## Preliminary x86-64 networking

The staged CMake passed local HTTPS downloads, redirects, expected hash checks, certificate-file and certificate-directory trust, hostname rejection, verification settings, and an HTTP CONNECT proxy. The negative cases returned the expected TLS status or hash mismatch.

A separate networked container used `FetchContent` to download the locked CMake source archive and verify its SHA-256. The local tests ran with only loopback networking. These runs do not yet constitute the registered network qualification suite.

## Preliminary real-project results

fmt 12.2.1 configured and built with the staged CMake and pinned LLVM/musl toolchain. Its test run passed 18 of 21 CTest cases. `chrono-test`, `unicode-test`, and `xchar-test` failed locale assertions. A separate build with the official CMake binary and the same toolchain reproduced all three failures. The failures remain reported by the project fixture.

zstd 1.5.7 configured and built, and its command-line program passed a compression and decompression round trip. The libjpeg-turbo and LLVM runs are still in progress.
