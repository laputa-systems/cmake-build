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

## Shared build library

Lock loading, input fetching, target descriptions, archive writing, and the ELF
hardening check come from `laputa-buildlib`, which is standard-library-only. It
is pinned twice, to the same wheel: `pyproject.toml` and `uv.lock` for `make
lint`, and the `buildlib-wheel` input in `sources.lock.json` for everything that
runs `build.py`. Plain `python3`, the offline Alpine builder containers (Python
3.14), the CI jobs, and the benchmark runtime have no uv environment, so
importing `buildsys` verifies the cached wheel by size and SHA-256, downloads
it into `.work/cache` when absent, and puts the file on `sys.path`
(`buildsys/buildlib_wheel.py`). `fetch` on the host therefore populates the
cache before any sealed container starts. The benchmark container sees only
`buildsys/`, so `benchmark` also mounts `sources.lock.json` and a copy of the
wheel at the paths the module expects. A controller test keeps the two pins
equal. Change the version in `pyproject.toml`, run `uv lock`, and update the
`buildlib-wheel` entry from the new `uv.lock` hash and the wheel size.

Archives are written by `buildlib.release.create_archive`, which sorts entries
by relative path. For the same stage tree and source date the archive bytes
equal those of the earlier writer; the archive file mode is now 0644 instead of
0600. Moving the pinned wheel into the build inputs changes the `build_inputs`
list in `artifact.json`, so archives built before this change do not match
earlier qualification, reproduction, or memory-baseline evidence, and the
implementation digests in phase fingerprints change.

`build` enables a persistent developer C/C++ cache in `.work/compiler-cache/`.
Qualification uses a separate uncached C/C++ build phase. All completed phases
are reused only when both their input fingerprints and output tree digests
match. `package` creates a candidate archive and detached candidate record.
`qualify` checks that archive, runs the project and upstream suites, and tests
the extracted bytes before atomically selecting the qualified generation.
`reproduce` creates two separate clean build roots and compares their file
trees and archive bytes.

Qualification checks executable, unpacked, and archive sizes against the
target's committed budget before activation. It runs the project suite against
the extracted archive, including its packaged `ctest`. The upstream subset uses the extracted executable in an isolated
copy of the build tree, with the upstream test resources.

`python3 build.py benchmark --target x86_64-unknown-linux-musl` runs five
interleaved repetitions on a native Linux host with `strace` installed. It
requires an active qualified generation and the unmodified musl baseline from
the upstream suite. The command writes [performance results](performance.md)
and compares size and CMake-image peak-memory measurements with
`release-budgets.json`. RSS excludes compiler and other child processes. The
configure runs use process tracing to read the image high-water mark at exit;
startup timing uses an untraced invocation and measures RSS separately. CPU time
includes waited child processes.
The [ARM baseline report](performance-aarch64.md) records its native run.
The [Rustls profile study](performance-rust-release.md) compares the smaller
candidate with the previous x86-64 release.
Existing limits are retained. When a target's memory baseline is unmeasured,
the recorded baseline archive can establish it for review and commit.
The native baseline workflow checks that historical archive against its own
recorded size limits; release qualification continues to use the current
candidate limits.
Memory baselines must carry the current RSS scope; earlier process-tree RSS
baselines are rejected because they could include launcher memory. The recorded archive digest identifies the
memory baseline; size limits can
be tightened separately when a smaller qualified build is measured.
The local `qualify` command enforces size limits. The native qualification
workflow also requires a measured memory baseline and a passing benchmark;
its memory results are bound to the archive and budget hashes.
Memory limits compare the median initial-configuration peak RSS against the
baseline, allowing for the baseline's observed range and the candidate's
interquartile range. A rejected measurement is written to
`.work/tmp/benchmark-rejected.md` and does not replace the accepted report.

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
