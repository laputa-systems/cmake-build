# Development environment

cmake-build runs its controller on a pinned Python 3.15 with the pinned
`laputa-buildlib` wheel, provisioned by the vendored
[buildlib bootstrap](https://github.com/laputa-systems/buildlib/blob/main/docs/bootstrap.md).
No distribution Python, `uv`, or `pip` is required for the documented `make` gates; the shim
downloads and verifies the interpreter and the wheel by size and SHA-256.

```sh
sh bootstrap/buildlib-run -- build.py controller-test
sh bootstrap/buildlib-run -- -c 'import sys, buildlib; print(sys.version, buildlib.__file__)'
```

Arguments after `--` go to Python. Verified hosts: Apple Silicon macOS 27+ and Linux with musl
>= 1.2.5 (Alpine, Debian 13, Ubuntu 26.04 with the `musl` package). On glibc hosts without a
compatible musl loader (Ubuntu 24.04) the shim uses a pinned `uv` binary and uv's upstream
CPython, verified by uv's metadata.

`make` runs the controller through the shim (`PYTHON ?= sh bootstrap/buildlib-run --`). The
sealed builder containers and the benchmark runtime still run `build.py` under the pinned Alpine
Python; `buildsys` admits the wheel from `.work/cache` there, so populate the cache with the shim
(or `make fetch`) before those contexts run.

## One-command setup

```sh
make setup          # or: sh scripts/setup-dev
make lint test
```

`scripts/setup-dev` is idempotent. It installs the distribution packages below on a verified
Linux distribution, installs the pinned `uv` for development tooling, syncs the locked
development dependencies, and checks that the bootstrap brings up Python and the wheel. It fails
clearly on an unverified distribution.

| Package (Linux) | Consumer |
| --- | --- |
| `curl`, `ca-certificates` | `buildlib-run`, `scripts/setup-dev`, and `build.py fetch` downloads |
| `tar`, `xz-utils` | archive extraction (`buildlib-run`, `setup-dev`, `safe_extract`) |
| `git` | release provenance, the reproduction test |
| `make` | the documented `make` gates |
| `musl` (Ubuntu 26.04, Debian 13) | the python-build interpreter branch of `buildlib-run` |

On macOS, install the Xcode command line tools (`xcode-select --install`) for the native
toolchain; everything else comes from the bootstrap.

## Development tools

`make lint` runs Ruff and ty, pinned in `uv.lock` and installed by `make setup`. They are
development-only, not controller runtime dependencies. `make coverage` and the benchmark targets
assume the same development environment.

## Optional tools

- `perf-gate-ready` gates benchmark timings; without it the benchmark harness reports the timing
  as deferred and non-gating.
- A native toolchain matching `bootstrap.lock.json`, Docker, `kache`, and `jaq` are required for
  `make build|verify|repro`; none are needed for `make lint test`.

See [buildlib-adoption.md](buildlib-adoption.md) for how the bootstrap and shared helpers were
adopted, and [building.md](building.md) for the locked build chain.
