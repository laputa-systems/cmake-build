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

The workflows are defined but their first hosted qualification and prerelease
runs have not yet completed.
