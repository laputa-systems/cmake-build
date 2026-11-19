Prefix: DSLP
Next: 7

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier A). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

## Report

Ground (DSLP-1) passed at base `dfd9c86c33e52bf56c0eb699d1d8a166817c82e4`. The prepared Linux builder passed 113 controller tests twice. Local Ruff and ty passed. [Verification](AGENTS.md#verification) records the scope, costs, and separate native qualification.


This Diagnose slice at `cc8296d` traced `build.py` command routing, source and
bootstrap lock validation in `buildsys/inputs.py`, archive inventory and
qualification handoffs, the release workflow, and the consumer of the active
generation in `buildsys/benchmark.py`. Existing tests cover interrupted
qualification, changed archives, mutated trees, and budgets. The sealed
reproduction below checks reuse of an existing generation. No native binary
or benchmark workload was run. Remaining controller review stays open.

Create an archive with one `bin/cmake` fixture using `buildsys.package.create`.
Qualify its SHA-256 into a private store with a callback returning a nonempty
passing result. Change the generated `results.json` `archive_size` to zero.
Requalify the same archive and digest. The returned generation stays active,
and its recorded size remains zero. In `benchmark.run`, the admission check
fails with `qualified archive digest or size does not match results`. The
fixture reaches this check by substituting the Linux host predicate and does
not proceed past admission.


DSLP-6 closes the reproduced generation reuse issue. A successful rerun
atomically replaces the result record after checking the stored archive and
tree. A forced replacement failure preserved the exact old record and the
active generation. The real benchmark admission progressed to its budget
read after recovering the corrupt size. Seven focused generation tests and
both linters passed. The unsealed macOS base and candidate had the same three
controller modules failing on host or cache prerequisites. The sealed Linux
controller job covers those modules.

Phase cache recovery at `1959946ee17b617cb69b7015f6b12a05f7171d02`
exercised a completed local phase with an unreadable UTF-8 cache record.
The same build phase aborted with `UnicodeDecodeError` on the base.
The candidate treats that record as stale, rebuilds the output under the
same fingerprint and reuses the recovered record on the next call. Run
`PYTHONPATH="$PWD/tests/controller:$PWD" uv run --frozen python -m unittest test_phases`
to exercise the recovery and ordinary phase reuse without a native build.

The first strict-typing inventory at
`0111edef816280ce3ebca3ab42e6a89ea4113299` found 52 missing generic
arguments and 13 unsound returns using ty 0.0.101. The
`unused-ignore-comment` setting added no findings in the same run.
`buildsys/dependencies.py` accounted for two of the unsound returns:
`re.findall` erased the capture types for revision tags and version
macros. The parser now slices the known input string at each required
capture span. `uv run --frozen ty check --error unsound-return-statement buildsys/dependencies.py`
fails twice on the base and passes on the candidate. The aggregate
strict check has 63 remaining diagnostics. No policy setting changes.

A before-and-after helper comparison used an inline header version,
a pair of numeric macros, a tag, the unversioned fallback, an absent
tag and duplicate macros. Each value or diagnostic matched. The
existing CMake and budgets suites passed nine tests. Decoded budget
and phase data, process status and the remaining generic annotations
remain open under DSLP-3.

Phase and budget types at `e5051ef9978249471a28796f9b2e4a52891c4bd8`
reduce the strict inventory from 63 to 60 diagnostics, with 50 generic
arguments and 10 unsound returns still open elsewhere. Phase records
expose decoded fields as `object` until callers check them. The successful
memory-baseline modes return the two literal values the branches establish.

A checker witness that reads the private phase record and calls
`record["output_digest"].startswith("a")` without a type guard passes
on the old signature and now reports one `missing-attribute` diagnostic.
The budget witness imports `assert_type` and checks the return value of
`validate_memory_source({}, "target", "0" * 64, 1)` against
`Literal["measured", "unmeasured"]`. The old signature reports one
`type-assertion-failure`; the candidate accepts the witness. These files
are checker inputs only. Run `uv run --frozen ty check <witness-file>`
for each and the earlier three-setting inventory for repository counts.

Existing phase recovery and budget tests passed 12 cases. The serialized
record shape, archive bindings and budget decisions remain the same.
The repository-wide strict settings remain open under DSLP-3.

Controller command output at
`8f6643d183dc0f4b5cd41c1c831c75b2c447725e` reduced the strict inventory
from 60 to 50 diagnostics. Both process helpers already request text
output. Typing the results and the probe data removed eight missing
generic arguments and the unsound gateway return. The sysroot parser
now returns the required SONAME capture from the original string,
removing the second unsound return. The data decoded from Docker's
inspection report remains a separate typing boundary.

`assert_type(_docker("version").stdout, str)` gives one
`type-assertion-failure` before and passes after when checked in a scratch
file with the project's ty command. The fixture does not execute Docker.
The existing sandbox suite passed all 22 tests. A local parser witness
compared a normal LLVM SONAME line and the missing SONAME diagnostic.
Ruff and ty passed. The remaining strict inventory is 42 generic
arguments and eight unsound returns.

Memory samples at `339507934ee7dd37d0d17b0c0541710458b970ba`
exposed a raw `KeyError` when a product sample lacked `max_rss_kib`.
The budget boundary now reports that as an invalid sample. Matching
records are checked as positive integers, then the metric calculation
returns typed numeric fields without changing the existing median,
spread and allowance arithmetic.

A scratch `assert_type(memory_baseline([])["fmt_initial_rss_kib"]["value"], float)`
fails with `type-assertion-failure` before the change and passes afterward.
The checker proof does not execute the empty sample list. All seven
budget tests pass, including the missing RSS witness. Strict findings
fell from 50 to 44: 37 missing generic arguments and seven unsound
returns remain. Ruff and ty passed.

At `54ba25ecfa70efb36e82087fc4981038f5d32a70`, jaq produced a case
with a null or empty name for two malformed JUnit fixtures. Both
reports had previously been accepted. The controller now rejects
them while preserving the existing successful report and duplicate,
empty-report and skipped-test outcomes. Rust phase validation checks
that the stored digest is text before walking the output tree. The
fixtures cover the valid digest, drifted output and a non-text digest.

Run the controller's `test_projects.py` and the isolated Rust phase
fixtures for the boundary controls. The same full strict invocation
reduces 44 diagnostics to 42, with 37 missing generic arguments and
five unsound returns still open. Ruff and the normal ty check pass.

A release budget with `targets` set to null, a list or a string
raised an uncaught `AttributeError` at `745ac5f7`. All three fixtures
now report the missing target through `BudgetError`. The typed
boundary keeps the original nested mappings, so initialization
updates the same metrics and preserves opaque JSON fields.

The budget and package-generation suites each passed seven tests.
Scratch `assert_type` checks of the emitted archive size and an RSS
measurement give two diagnostics on the base and pass on the
candidate. The strict inventory fell from 42 to 31, with 27 missing
generic arguments and four unsound returns still open. Ruff and the
normal ty check pass.

The artifact reader at `a8dd64b7` accepted a one-byte member whose
inventory declared `true` or `1.0` as its size. Python compares those
values equal to integer `1`. Both sealed repack fixtures now fail
with the inventory diagnostic. An initial JSON null manifest also
previously hid a second manifest and now fails at the invalid record.
Valid tar members retain the same
metadata, and directory, file and symlink records carry their own
types. The benchmark consumer checks the target and build metadata
shapes before using them.

All 14 package controller tests and both linters passed. The full
strict inventory fell from 31 to 27, leaving 23 generic arguments
and four unsound returns. No native release ran for this slice.

The command controller now carries the concrete target through its
paths and package metadata, uses text-mode child process results, and
types the qualification callback's output. A fake command that
returned a string previously escaped `main()` as its result. It now
produces the controller's error status and a diagnostic. The nine CLI
and seven generation tests passed with Ruff and ty.

The strict inventory fell from 27 to 21 at this boundary, with 20
missing generic arguments and one unsound return still open.

Diagnose ranks input acquisition and phase reuse first. A cold runner
must acquire the signed bytes, and any changed phase input or output
must invalidate reuse. The sandbox boundary follows because host
tools and network access change what the controller can build. The
archive and generation boundary must check typed member metadata,
qualified suites and unmodified package bytes before activation.
The lock, phase, TLS, sandbox and package controller tests exercise
those boundaries. Full native qualification exercises both targets.
DSLP-3 retained the strict typing work; DSLP-4 is closed below.

The first cold ARM64 trial stopped before compilation when Alpine
Edge returned 404 for the locked OpenSSL CLI APK. Alpine 3.24 is the
oldest supported branch with the pinned musl 1.2.6 runtime. The
builder now uses the fleet's Alpine 3.24.2 image and its signed
`v3.24/main` packages. CMake, Python, make, patch, Linux headers,
xz and the musl runtime determine the builder closure. The OpenSSL
CLI remains a separate qualification input.

The [two-platform stable trial](https://github.com/laputa-systems/cmake-build/actions/runs/44351416444)
at `9506d7900bc2c1d959a0db7c09029eb779648d03` passed basic, parity,
network, project and upstream qualification. Both archives passed
their size budgets.

| Target | Archive bytes | SHA-256 |
| --- | ---: | --- |
| ARM64 musl | 19,014,068 | `b812bd069e39c69880e8ee020d66d103ce564c94d968c113bb6a06f24e378809` |
| x86-64 musl | 20,741,632 | `8bfe12b64fe504d4e8c64ab884f8c739f78b02687eb6325559c6456238372d04` |

The merged tree at `0bbf8f4e900aa1590bb4c61241a5099190ab790b`
matches the [green PR](https://github.com/laputa-systems/cmake-build/pull/24)
at `bb220e139909c40cbd7132ca979f2327b0f9333f`. The PR also includes
the command-controller typing change that merged after the first trial.
All 123 prepared controller tests and both linters passed.
Its [exact-tree qualification](https://github.com/laputa-systems/cmake-build/actions/runs/44354687939)
passed the native archive, size and memory gates on both architectures.
The first x86-64 attempt lost its connection
while downloading the pinned Buildlib wheel before reaching Alpine.
The re-fetched wheel matched its locked SHA-256. The second attempt
used the verified input cache and passed. Both uploaded manifests
passed their SHA-256 checks and named `bb220e139909c40cbd7132ca979f2327b0f9333f`.

| Exact target | Archive bytes | SHA-256 |
| --- | ---: | --- |
| ARM64 musl | 19,014,072 | `b296226391aa9788296a130377eb3031dd756a61dc602717d810f9d7f002b5b1` |
| x86-64 musl | 20,741,636 | `cf450193664523aad3bd4a104fefda597d6a5d9abe78415089cccb4d40107acf` |

The five-repeat memory reports used the committed budget with SHA-256
`67d3c1e375b5060df59955327539ba5a6cc1bea1a481e8b1a461b7050c0e5e08`.

| Exact target | fmt RSS (KiB) | libjpeg-turbo RSS (KiB) | LLVM/Clang RSS (KiB) | zstd RSS (KiB) |
| --- | ---: | ---: | ---: | ---: |
| ARM64 musl | 14,444 | 15,820 | 489,032 | 16,496 |
| x86-64 musl | 15,852 | 17,284 | 490,376 | 17,964 |

To requalify, run the `qualify.yml` workflow on the checked branch. It
fetches and verifies the lock, builds on both native architectures,
tests the packaged archives, and checks the committed memory budgets.

Types (DSLP-3) closes the 21 remaining diagnostics from the candidate
checks at `1617378`. Default ty now rejects missing generic arguments,
unsound returns and unused ignore directives. The wheel bootstrap
validates its URL, digest and size before cache access. Bootstrap APK
and Rust entries leave the parser as validated Buildlib inputs. A
direct comparison with the previous reader matched all 36 locked input
records for each target, including ordering.

The benchmark report, provenance fixture and tool checks expose their
record fields to the checker. In a scratch file, assigning `"unknown"`
to `Measurement["max_rss_kib"]` failed with `invalid-assignment`.
The focused controller cases exercise malformed wheel pins and optional
bootstrap metadata. The later Tests disposition is recorded below.

The bootstrap parser Tests slice uses `test_inputs.py` at controller
base `d1678b5`. On macOS ARM64 with Python 3.15.2, mutmut 3.8.1 ran
the same 172 `buildsys.inputs.*load_bootstrap*` identities with one
child, pytest 9.2.0, `timeout_constant = 5.0` and
`timeout_multiplier = 15.0`. The original tests caught 132 and missed
40. The candidate caught all 172. Generate the trial from `buildsys/`,
`build.py`, both lock files and the controller fixtures, using
`test_inputs.py` as the pytest selection and the SHA-verified Buildlib
wheel cache. Inspect the selected exit codes in
`mutants/buildsys/inputs.py.meta`.

Coverage.py 7.17.3 reported 221 → 235 of 254 statements and
80 → 93 of 110 branches in `buildsys/inputs.py`. The same module
passed 24 ordinary tests. Reversing the input order, rewriting explicit
Rust roles and discarding the Alpine object diagnostic failed the
corresponding fixture checks. The native release retains its separate verification.


**DSLP-4 · Tests — complete under the revised mutation policy**

The required critical scope is input and lock admission (`buildsys/inputs.py`
`load_sources`, `load_bootstrap`, `_bootstrap_input`, `Cache.require` and
`fetch`); cache store integrity and destination-filesystem staging
(`Cache.store`); archive member admission and publication (`_check_member`,
`safe_extract`, `buildsys/package.py` `create` and `inspect`); flat archive
unwrapping (`buildsys/toolchain.py` `install`); tree identity (`tree_digest`
and `buildsys/phases.py` `PhaseCache.run`); atomic activation, cleanup and
retry (`buildsys/generations.py` `qualify`); and success/failure reporting
(`build.py` `main` and `_controller_test`, `buildsys/benchmark.py` `run` and
`_write_atomic`). Coverage remains a report, not a gate.

Ordinary controller tests protect distinct behaviors: malformed or unpinned
locks and changed cache bytes are rejected; concurrent stores use separate
staging on the destination filesystem and reject source changes, clean up and
retry (#38, #39); traversal and unsafe links are rejected and extraction
failure preserves the destination; flat and wrapped toolchain archives retain
files regardless of entry order (#87); tree content, modes, links and root
record exclusions determine phase reuse; failed archive writes and generation
activation preserve the prior artifact, clean staging and allow retry; failed
commands or invalid reports cannot be published as success. The witnesses are
in `test_inputs.py`, `test_phases.py`, `test_sandbox.py`,
`test_package_archive.py`, `test_package_generations.py`, `test_cli.py` and
`test_benchmark_admission.py` under `tests/controller/`.

Recorded mutation evidence, not new trials: at input source SHA-256
`a5f481a06a20ced2e77f012972c462fb49e96e3782d8812dc55ffb2531272831`,
535 of 565 input identities were caught; native x86-64 and ARM64 jobs
repeated that result and caught 169 of 178 phase identities
([positive trial](https://github.com/laputa-systems/cmake-build/actions/runs/44446845009),
[mixed deletion control](https://github.com/laputa-systems/cmake-build/actions/runs/44447078808)).
The tree digest selection caught 70 of 72; cache store caught 34 of 38;
archive package caught 314 of 319; toolchain install caught 223 of 225;
generation caught 121 of 141; the CLI selection caught 373 of 376;
the benchmark atomic writer caught all 21 selected identities. These
selections used mutmut 3.8.1 and pytest 9.2.0 on macOS ARM64 with CPython 3.15.2 unless the native jobs are
specified. Historical runner times and full result metadata were not retained;
the counts do not establish a timed mandatory gate. To replay the store
selection, use the input trial layout with `only_mutate = ["buildsys/inputs.py"]`,
select `tests/controller/test_inputs.py::CacheTests`, and run
`mutmut run --max-children 1 'buildsys.inputs.*Cache*store*'` with the locked
Buildlib wheel. The source, lock files, controller fixtures and result metadata
are needed for a comparable run.

Survivor dispositions in the demonstrated critical selections:

- Four cache-store variants only change a private staging-directory prefix.
- Extraction prefixes are private; the default read mode, member iteration and
  Python 3.14/3.15 data filter are equivalent. Member-rejection variants alter
  diagnostics while retaining rejection; the non-string JSON key check is
  unreachable through the JSON lock reader.
- Tree sibling sorts compare children of the same directory and are equivalent;
  phase writer variants change private suffixes or decoded JSON formatting,
  and the codec spelling is equivalent.
- Package survivors change a depth-only stack value, equivalent sibling sort,
  or rejection text. Toolchain survivors change equivalent `_run` defaults.
- CLI survivors change two path-name cases or remove argparse's equivalent
  `None` default.
- Generation survivors change rejection text or JSON formatting; four path-case
  variants alias on the case-folded macOS volume and remain unverified as
  individual mutations on case-sensitive Linux. Ordinary tests exercise the
  activation and cleanup outcomes on the native controller jobs.

The wider coordinator and benchmark sweeps are advisory. Their earlier 950
and 1,355 identity selections are not comparable: the final 950 coordinator
selection caught 900 with 50 survivors, while the separate 1,355 selection
caught 1,108 with 247 survivors. Admission, locked inputs, report provenance,
measurement validation, publication and cleanup have ordinary boundary tests;
the remaining individual advisory identities were not retained for complete
behavior grouping. Known private names, equivalent defaults and incidental
diagnostic text need no new tests. Case-only path variants require a
case-sensitive replay; no replay is claimed. Other unexamined coordinator,
qualification, build and platform-specific regions remain incomplete, not
passes. The broad draft mutation matrix in PR #54 is not a mandatory CI gate.
The initial broad CLI trial exceeded its local CPU guard; its unrun outcomes
are incomplete. No new mutation trial was run for this closure: 0 aggregate
runner-minutes. No new behavior or product defect was found in this closure.

The earlier tests also fixed malformed benchmark samples, overflowing even
medians, mismatched JUnit counts, a network listener leak and reproduction
cleanup after one worktree removal fails. Native branch coverage was measured
in [run 44403063173](https://github.com/laputa-systems/cmake-build/actions/runs/44403063173):
1,995/3,161 statements and 534/972 branches across `build.py` and `buildsys/`.
It locates unrun code and is not a quality threshold. The current warm sealed
suite cost and its change against the original baseline were not measured in
this closure. Historical trial details remain in Git history.

**Dead code scan**

[CMake #31](https://github.com/laputa-systems/cmake-build/pull/31) removed
three fields from the decoded bootstrap record. The controller and its
tracked profiling scripts read the image indexes and ordered target inputs.
The Alpine release, image manifest reference and repository metadata still
pass through the existing lock validation. The 24 input and 22 sandbox
cases passed locally, and hosted native controller CI passed.

Ruff `F401,F841` passed. Deptry 0.25.1 passed with
`--package-module-name-map laputa-buildlib=buildlib`. Vulture 2.16
`--min-confidence 60` checked tracked Python files. Its findings represent
five live uses. Typed report schemas describe keys read with subscripts or
written to evidence. The signal handlers receive their frame argument from
`signal.signal`. HTTP fixture handlers and `daemon_threads` are used by the
standard library. `TarInfo` serializes the two device number fields in the
archive fixture. The Linux profiling script passes its `Event` fields by
reference to the kernel. Keep these uses during the remaining structural
review under DSLP-5.

At `23e6d5a`, Ruff F401/F841 and deptry 0.25.1 passed. Vulture 2.16
on `buildsys/ build.py scripts/` at confidence 60 reported 30 individual
findings; these remain discovery only, not a whitelist. They include record
fields, a signal callback argument, and four functions referenced by test or
qualification runners outside that scan. Each was traced and is a false
positive: the fields are serialized into JSON records, budgets and reports
(for example `loader_sha256`, `release_target_commit`, `rss_scope`), `frame`
is the required `signal` handler parameter, and `check_link_trace`,
`check_host_vendored`, `build_client` and `interleaved_orders` are called by
the provenance, TLS and benchmark runners. A whitelist would exceed five
entries, so vulture stays discovery-only and out of `make lint`. DSLP-5 is
done: the earlier removals (#31, #33) stand, and this review found nothing
further to remove.

The structural review checked `build.py` parser registrations and dispatch,
Makefile targets, workflow invocations, `scripts/controller_coverage.py`,
benchmark, TLS and provenance runners, and controller tests. The coverage
script is invoked by `make coverage`; the benchmark runner and its ordering
function are used by `benchmark`; the TLS and provenance helpers are invoked
by their runners and exercised by controller tests. Target selection covers
both supported Linux musl architectures; native execution of those paths was
not repeated on this macOS host. Small path and sandbox wrappers still have
callers, and the historical profiling scripts support documented studies. No
branch or script was established as safely removable, so there are no removal
records and no live-behavior tests were deleted. Local `make test` at the
base ran 335 tests with only `test_audit.py` (native clang missing) and
`test_tls.py` (offline rustls source missing) failing; `make lint` passed.
