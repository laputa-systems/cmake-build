# CI and prereleases

The controller workflow prepares the pinned native x86-64 builder and runs the
controller suite inside it. The qualification workflow runs on native x86-64
and aarch64 GitHub runners. Both restore verified source inputs and completed
qualification build phases from keys derived from the tracked build inputs.
The controller checks each phase's input fingerprint and output digest before
reuse. Qualification does not use the developer C/C++ compiler cache.

The runner installs pinned `jaq` and `kache` binaries from the source lock.
They run on the CI host and are not included in the CMake distribution. `jaq`
is required to read upstream qualification reports; `kache` is the existing
Rust compiler wrapper. The exact downloads are checked for size and SHA-256.

Dispatch `qualify.yml` at the commit to qualify. Each native job tests the
extracted archive and uploads it with its embedded metadata and detached
results. `release.yml` takes that full commit SHA and requires a successful
qualification run containing both native jobs at the same SHA. It verifies
the artifacts again and creates a new prerelease tag and release with combined
SHA-256 sums. It never rebuilds an artifact or updates an existing release.

The [qualification run for `58313ac`](https://github.com/laputa-systems/cmake-build/actions/runs/42828105487)
passed both native jobs. The [prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-58313acce6f9-run42833257470-1)
contains those qualified archives. A later native run restored and reused all
three caches on both architectures.

The workflow refuses to replace an existing release or tag. GitHub does not
currently mark the prerelease immutable, so consumers must verify an independently
pinned archive digest; the workflow's no-overwrite check does not prevent later
manual changes by someone with repository permissions.
