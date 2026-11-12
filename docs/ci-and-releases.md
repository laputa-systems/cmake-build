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
extracted archive, runs five benchmark repetitions against a committed memory
baseline, and uploads the archive with its embedded metadata, detached results,
and CMake-image memory evidence. The time measurements are informational. Dispatch
`release.yml` on the default branch at that same commit. It requires a successful
qualification run containing both native jobs at `github.sha`, verifies the
artifacts and archive-bound memory evidence again, and creates the
`release-<sha>` tag through the GitHub API when it does not exist. The
prerelease holds `cmake-<version>-<target>.tar.xz` and
`cmake-<version>-<target>.manifest.json` for each target, the detached
qualification evidence, and a sorted `SHA256SUMS` checked with `sha256sum -c`.
It never rebuilds an artifact or updates an existing release.
Releases before this layout use `cmake-<version>-<sha12>-run<id>-<attempt>` tags
and have no manifests.

The [complete-tools qualification](https://github.com/laputa-systems/cmake-build/actions/runs/42930810892)
passed on both native architectures at `40f84ae`. Its
[prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-40f84aef2341-run42938731214-1)
contains those archives and their detached evidence. The x86-64 archive matched
two clean builds. The [ARM64 reproduction](https://github.com/laputa-systems/cmake-build/actions/runs/42938846057)
also matched two clean builds to the published archive.

The [qualification run for `5932be3`](https://github.com/laputa-systems/cmake-build/actions/runs/42900481859)
passed both native jobs and their corrected memory gates. The
[prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-5932be3ecbc4-run42907504620-1)
contains those exact archives, detached results, memory evidence, and reports.
Both archives also matched two independent clean builds on their native
architectures. The [ARM64 reproduction workflow](https://github.com/laputa-systems/cmake-build/actions/runs/42912387088)
checks the qualification record, published bytes, and both rebuilt archives.

The [qualification run for `58313ac`](https://github.com/laputa-systems/cmake-build/actions/runs/42828105487)
passed both native jobs. The [prerelease](https://github.com/laputa-systems/cmake-build/releases/tag/cmake-4.4.5-58313acce6f9-run42833257470-1)
contains those qualified archives. A later native run restored and reused all
three caches on both architectures.

The workflow refuses to replace an existing release or tag. GitHub does not
currently mark the prerelease immutable, so consumers must verify an independently
pinned archive digest; the workflow's no-overwrite check does not prevent later
manual changes by someone with repository permissions.
