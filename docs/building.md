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

## Trace a dependency fix

For a Rustls source update, pin and verify the new `rustls-ffi-source` digest in
`sources.lock.json`. The digest is an input to the Rust vendor phase. Its output
digest is an input to the Rust static-library phase, whose output digest is an
input to the CMake build phase. A changed output invalidates its dependent
phase; an identical output can be reused. The archive's `artifact.json` lists
the locked build inputs, and the detached results bind qualification to the
archive SHA-256.

For the x86-64 prerelease at commit `58313ac`, the recorded Rustls lock digest
matches the vendor input and the archive metadata. The local phase records
also connect the vendor output to the static library and the static library to
CMake. A synthetic change to the source digest changed the vendor fingerprint;
no dependency fix or replacement artifact was built in this exercise.

After a real fix, build a new candidate, run the network and other qualification
suites on its exact archive, and require native qualification for both targets.
Run clean-build reproduction before publishing the replacement. Check each new
archive digest against its detached qualification results.
