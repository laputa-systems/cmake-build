# Building and qualification

The host needs Python 3.11 or later, Docker, `kache`, and `jaq`. Build a target
on the matching native architecture; cross-architecture emulation is not used.
All local work, including downloaded inputs and build outputs, lives under
`.work/`. Set `TMPDIR` to `.work/tmp` before running builds.

```sh
mkdir -p .work/tmp
export TMPDIR="$PWD/.work/tmp"
python3 build.py fetch --target x86_64-unknown-linux-musl
python3 build.py test --target x86_64-unknown-linux-musl --suite basic
python3 build.py test --target x86_64-unknown-linux-musl --suite parity
python3 build.py test --target x86_64-unknown-linux-musl --suite network
python3 build.py test --target x86_64-unknown-linux-musl --suite projects,upstream
python3 build.py package --target x86_64-unknown-linux-musl
python3 build.py qualify --target x86_64-unknown-linux-musl
python3 build.py reproduce --target x86_64-unknown-linux-musl
```

Replace the target with `aarch64-unknown-linux-musl` on an aarch64 host. The
fetch step downloads pinned sources, toolchains, and test inputs and verifies
their size and SHA-256 on both download and reuse. The build runs in the pinned
Alpine container with networking disabled. The network suite uses an isolated
local server and a separate explicit internet check.

`build` enables a persistent developer C/C++ cache in `.work/compiler-cache/`.
Qualification uses a separate uncached C/C++ build phase. All completed phases
are reused only when both their input fingerprints and output tree digests
match. `package` creates a candidate archive and detached candidate record.
`qualify` checks that archive, runs the project and upstream suites, and tests
the extracted bytes before atomically selecting the qualified generation.
`reproduce` creates two separate clean build roots and compares their file
trees and archive bytes.

The archive contains build metadata, file hashes, and third-party notices.
Qualification results, archive size and SHA-256 are detached because they are
known only after the archive bytes exist. See [qualification](qualification.md)
for the native test results and known differences from the reference.
