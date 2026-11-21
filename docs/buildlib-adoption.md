# Buildlib adoption

cmake-build depends on `laputa-buildlib` for lock reading, verified acquisition, hashing,
release archives, target descriptions, and the ELF hardening check. This record covers the BLD-3
slice: the audit of remaining local reimplementations, the vendored interpreter bootstrap, the
code that changed, and the proof the plan's per-repository items require. Base revision:
`a1b92cd7eee3675ceecedb3cef9b428769732554`.

## 1. Bound the change

Entrypoints are unchanged: `make build|verify|package|repro|fetch|doctor|test|lint`, the
`build.py` subcommands, the compiler flags, and the release/archive formats. `make` now runs the
controller through the vendored `bootstrap/buildlib-run`, and the local wheel downloader is gone.

| Local implementation (base) | What it did | Replaced with |
| --- | --- | --- |
| `buildsys/buildlib_wheel.py` `_download` | Downloaded the `buildlib-wheel` input with `urllib` into the content-addressed cache. | The vendored `bootstrap/buildlib-run`, which buildlib owns. `buildsys` provisions a missing cache object by asking the shim for its already-verified wheel; it never downloads. |
| `buildsys/buildlib_wheel.py` `_matches`, `_pin`, `locate` | Read the pin as plain JSON, hashed the file, and inserted it on `sys.path`. | Kept as a narrow admission boundary, because the sealed containers and the benchmark runtime run `python3 build.py` and cannot run the shim. It still verifies size and SHA-256 and still reads only the one lock input it needs before `buildlib` is importable. |
| `Makefile` `PYTHON ?= python3` | Required a distribution `python3`; the controllers declare Python 3.15. | `PYTHON ?= sh bootstrap/buildlib-run --`, which provisions the pinned CPython 3.15 and the wheel. |

Already on buildlib before this slice (no change, kept): `locks.load_sources`/`load_budgets`/
`load_bootstrap`/`fetch_input`/`verify_file` (`buildsys/inputs.py`, `buildsys/budgets.py`),
`hashing.sha256_file`/`digest_file` (every record), `release.create_archive`
(`buildsys/package.py`), `elf.hardening_violations` (`buildsys/elf.py`), and
`targets.target_for_triple`/`native_target` (`buildsys/targets.py`).

### Interpreter path a fresh host takes (base)

`docs/building.md` told a newcomer to run `python3 build.py ...`. `buildsys/__init__.py` then
imported `buildsys.buildlib_wheel`, which fetched the wheel with `urllib` if it was absent. That
path depends on the distribution providing `python3` at all: Ubuntu 24.04 ships none, and the
project declares `requires-python = ">=3.15"`. The adoption path removes the host-Python
dependency for the documented `make` gates: the shim provisions a pinned CPython 3.15 and runs
the wheel on it, so a host with no Python, no `uv`, and no `pip` still runs them.

### Audit of remaining local code (not replaced)

- `buildsys/buildlib_wheel.py` `locate`/`admit`: the cache object is what the sealed builder
  containers and the benchmark runtime import, and `build.py` gives every container
  `PYTHONPATH=/src`. Nothing inside those contexts can execute `bootstrap/buildlib-run`, so a
  small in-tree admission that verifies the existing cache object is still required. The
  provisioning path delegates to the shim rather than duplicating its download, and its
  verification is the same size-and-SHA-256 check buildlib's `locks.verify_file` performs.
- `buildsys/inputs.py` `safe_extract`: `tar.extractall(filter="data")` plus an explicit
  escape/link pre-check. buildlib has no extraction helper. Kept with its escape/symlink tests.
- `buildsys/inputs.py` `canonical_json`, `identity`, `tree_digest`: a stable JSON encoder and a
  tree digest over paths, modes, links, and contents. buildlib exposes file digests but no tree
  digest or canonical encoder, so a rewrite would not remove a shared operation.
- `buildsys/patches.py` `verify_inventory`: reads patches with `O_NOFOLLOW` at every path
  component and checks them against the inventory table. This is stronger than a plain file hash
  and has no buildlib equivalent. Kept.
- `buildsys/elf.py` `audit`: it calls buildlib's `hardening_violations` for the baseline, then
  adds the repository's own interpreter, `DT_NEEDED`, symbol-version, compiler-provenance,
  OpenSSL, and build-host-path checks from `llvm-readelf`/`llvm-nm`/`llvm-strings`. Those are
  product policy and stay local.
- `buildsys/budgets.py` `check_size`, `memory_baseline`, `check_memory`, `apply_memory`: the
  structural `locks.load_budgets` is buildlib's; the ceilings, RSS scope, and measured values are
  consumer policy and stay local.
- `buildsys/phases.py`, `buildsys/generations.py`, `buildsys/benchmark.py`: phase fingerprints,
  archive admission, and the benchmark harness. No shared primitive.

Consumer policy that stays local and validated: source-lock extension fields (the
`buildlib-wheel` entry stays in `sources.lock.json` and is cross-checked against
`bootstrap/python.lock`), budget values and byte ceilings, `ALLOWED_NEEDED` dynamic
dependencies, the patch inventory, product manifest fields, and every release-layout and
cleanup check.

## 2. Pin and exercise the installed bytes

- `sources.lock.json` pins `laputa-buildlib` 0.2.0 at
  `sha256:aaee620f0478544b1d32075b44de48e69bbcbd8b974d5f599d037494d59f4b4a`, size 25193.
- `pyproject.toml` pins `laputa-buildlib==0.2.0`; `uv.lock` records the same wheel URL and hash.
- `bootstrap/python.lock` (vendored) pins the same wheel URL and SHA-256.

`tests/controller/test_buildlib_wheel.py` keeps the three identities equal and proves import
provenance: the ordinary controller imports `buildlib` from the
`…/.work/cache/objects/<wheel-sha>.blob` cache object, not from a source tree, and refuses a
source tree that shadows the wheel.

### Vendored bootstrap provenance

| File | Source | Digest (SHA-256) | Local differences |
| --- | --- | --- | --- |
| `bootstrap/buildlib-run` | buildlib `30ad4a0a8b697031a008b1de3b5359fc5cf6f2fe` (`bootstrap/buildlib-run`) | `e7f957ca6af0b151d25a9ff5bedb5deca0bfc86ba05ff3225a5405d56fa95957` | none |
| `bootstrap/python.lock` | buildlib `30ad4a0…` (`bootstrap/python.lock`) | `cab50541ce8b2c2a6a41829f26aac19344532d239535f4d6795d80d5af933832` | none |

Both files are byte-identical to buildlib 0.2.0 (`git rev-parse HEAD` = `30ad4a0`, tag `0.2.0`).
Repin them together: the wheel line must stay equal to the `sources.lock.json` entry. The shim's
trust paths are unchanged from buildlib: python-build archives verify by size and SHA-256 before
extraction; the uv fallback's managed Python is verified by uv's upstream metadata (a distinct
trust path, recorded here rather than claimed equivalent).

## 3. Boundary tests

- `tests/controller/test_bootstrap_shim.py` (new): runs the vendored shim against a local fixture
  server. It proves a verified archive and wheel execute the cached Python, and that an injected
  wrong wheel digest, wrong archive size, and truncated download each fail clearly with the
  pinned interpreter never running. This covers the shim's own trust paths.
- `tests/controller/test_buildlib_wheel.py` (rewritten): proves cache admission and provenance.
  Injected wrong wheel digest and wrong size fail before `buildlib` imports; a corrupt or
  truncated cache object is replaced from the shim, not imported; a cache symlink is refused; a
  local source tree that shadows the wheel is refused.

Preserved stronger checks (unchanged): archive admission (refuses overwrite), safe extraction
(escape and symlink), patch inventory (`O_NOFOLLOW`), cache integrity (source marker binds the
extracted tree to the pinned archive), release-layout membership/modes/symlinks, complete
`SHA256SUMS`, assembly concurrency, and the product hardening gate. No test was weakened or
skipped.

## 4. Compare outcomes

No release or archive format changed. Archive bytes, manifest fields, checksums, and the
`.tar.xz` writer are unchanged (still `buildlib.release.create_archive` with the same prefix and
`SOURCE_DATE_EPOCH`). Only interpreter provisioning and the missing-wheel provisioning path
changed; the controller's observable output and error contracts are unchanged.

## 5. Prove the environment

macOS arm64 (native): `make lint` and `make test` pass except `tests/controller/test_audit.py`
(`setUpClass`, the native toolchain is not prepared) and two `tests/controller/test_tls.py` cases
that need a prepared toolchain cache. Both fail identically on the base commit
`a1b92cd7ee` in the same capsule and on this host: the lane runs 347 tests in 38 modules with the
same three errors, the base runs 340 tests in 37 modules with the same three errors.

Cold capsules cloned from a read-only mount of the worktree at lane tip `b2f463b2`, native
arm64, run as root:

| Capsule | interpreter branch | repository clone | setup | interpreter | lint | test | `git status --porcelain` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ubuntu:24.04` (`ubuntu@sha256:9c7f200c…`) | uv fallback (musl 1.2.4) | 0 | 0 | 0 | 0 | 2 | empty |
| `ubuntu:26.04` + `musl` 1.2.5 (`ubuntu@sha256:d66b366d…`) | python-build (musl 1.2.5) | 0 | 0 | 0 | 0 | 2 | empty |

Both capsules ran the documented `sh scripts/setup-dev` (no preinstalled Python, uv, pip, or
jaq), then `make lint` and `make test`, and ran 347 tests in 38 modules. The `make test` exit 2 is
`test_audit` and `test_tls`, which fail on a missing `prepare` toolchain
(`.../phases/prepare/toolchain/bin/clang`) and a missing `rustls-ffi-source` cache object; the
controller suite never runs `build.py prepare`, so they need it first. Every other module passes.
`test` is recorded as a known environment failure, not a pass.

The base commit in the same `ubuntu:24.04` capsule (system Python 3.12) failed six modules:
`test_audit` and `test_tls` (same missing toolchain), `test_bootstrap`, `test_cmake`, and
`test_reference` (`unittest.mock` cannot patch `os.process_cpu_count`, which 3.12 lacks), and
`test_projects` (no `jaq`). The lane removes the four failures caused by an unsupported
interpreter and a missing `jaq`.

The default Linux gate the capsules can complete is `make lint` plus `make test`; the full
`make build` needs the pinned native toolchain, `kache`, Docker, and `jaq` on the host and is
recorded as not run in the capsules. Capsule logs stay in scratch.

## 6. Benefit and cost

- Duplicate code removed: the local wheel downloader (`_download`, its `urllib` request, its
  size-bounded read, and its `mkstemp`/`os.replace` publish) is deleted. A missing wheel is now
  provisioned by the shared shim, which verifies the interpreter and wheel by size and SHA-256;
  `buildsys` re-checks the copied bytes against the pin before admitting them.
- Shared operations actually used after the slice: the interpreter and wheel bootstrap
  (`bootstrap/buildlib-run`), plus the pre-existing lock/hashing/archive/target/ELF calls.
- Correctness gain: the documented `make` gates no longer need a distribution Python new enough
  to import the controllers, and there is one verified download path for the wheel instead of a
  second, weaker one.

## Repin procedure

1. Change `laputa-buildlib==X.Y.Z` in `pyproject.toml`, run `uv lock`.
2. Update the `buildlib-wheel` entry in `sources.lock.json` (URL, SHA-256, size).
3. Re-vendor `bootstrap/buildlib-run` and `bootstrap/python.lock` from the new buildlib tag and
   update the digests above. The wheel line must match step 2.
4. `make setup && make lint test`, then the cold capsules.
