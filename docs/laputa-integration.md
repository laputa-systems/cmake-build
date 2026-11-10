# Laputa integration

The archive extracts to a relocatable `usr/` prefix. Invoke `usr/bin/cmake`;
CMake locates its modules and templates under `usr/share/cmake-4.4/`. The
package metadata is the `artifact.json` file in `usr/share/doc/cmake-build/`.
The detached qualification results identify the archive by SHA-256 and size.

The x86-64 binary is a static PIE and needs no runtime loader. Its bundled
curl uses Rustls with system certificate trust. The native audit rejects GCC
runtime libraries, OpenSSL libraries and API symbols, host build paths, and
unapproved runtime dependencies. It permits the documented OpenSSL version
recognition and certificate discovery identifiers.

The build uses LLVM/musl toolchain release `dc0d9b9`. The toolchain and Samurai
were exercised in the native provenance and basic qualification fixtures.
The older Laputa toolchain pin `2f0b039` predates this toolchain release and
must be updated in Laputa by its owner. The distribution does not require
D-Bus, systemd, glibc, GCC runtime libraries, or host CMake resources.

Qualification is per architecture. Use only an archive whose detached results
match its SHA-256 and report all required suites for the intended target.
