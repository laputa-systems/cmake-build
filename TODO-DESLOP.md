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
DSLP-3 and DSLP-4 retain the strict typing and mutation work.

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
bootstrap metadata. DSLP-4 retains the wider controller mutation work.

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
corresponding fixture checks. The native release and the wider
controller mutation scope retain their separate verification.


**Package archive tests**

The macOS ARM64 archive suite exercised the same 327 `buildsys.package.*`
mutations at `5f81386`. Mutmut 3.8.1 with Python 3.15.2 and pytest 9.2.0
used the same copied controller and verified Buildlib wheel as the phase
trial, with `tests/controller/test_package_archive.py` as its selection.
The baseline caught 260 and missed 67. The eight-case candidate caught
284 and missed 43. The identity list and outcomes are recorded by
mutmut in `mutants/buildsys/package.py.meta`.

The new cases check staging and generated inventory ownership,
normalization of payload modes, root record exclusion, special-file
rejection, same-size payload changes and unreadable manifests. The
remaining archive mutations and whole-change gate stay in DSLP-4.

The follow-up rebuilt semantically identical metadata with both top-level
and nested keys in a different order. The archive bytes matched. It also
exercises multiple missing destination directories and a payload with only
the other-execute bit set. At `c533a06` the same 327 identities moved from
284 caught and 43 missed to 291 caught and 36 missed.

**Native controller cache**

[CMake #29](https://github.com/laputa-systems/cmake-build/pull/29) leaves
`tests/controller/` out of the native phase cache key. Recompute the key
from the `fingerprint` step in `.github/actions/native-setup/action.yml`. A controller
case edit leaves it unchanged. A native C fixture or builder source
edit changes it. The controller suite still runs in full after phase
preparation.

[Run 44377892313](https://github.com/laputa-systems/cmake-build/actions/runs/44377892313)
compared two attempts at the same PR revision. Native phase preparation
took 541 seconds cold and 24 seconds after restoring the audited native
and Rust caches. Both attempts passed all 128 tests in 21 modules. The
job key was `aebba13c014c06b5b334b0f7a2d0779c810f4260ed2a3584af9d496cea0d4756`.


**Phase record tests**

On macOS ARM64, mutmut 3.8.1 with Python 3.15.2 and pytest 9.2.0
selected the same 184 `buildsys.phases.*` identities at `0fdd7b9`.
The original suite caught 129 and missed 55. The candidate caught
169 and missed 15. Copy the controller, locks and verified Buildlib
wheel cache as for the bootstrap trial, and select
`tests/controller/test_phases.py` with one mutmut child. The identity
and status list is in `mutants/buildsys/phases.py.meta`.

The eight phase tests cover fingerprint identity and input order,
invalid cache records, the state visible during and after interruption,
and the metadata returned when a phase is reused. The 15 remaining
mutations involve text encoding, missing state during cleanup, or
private JSON write paths and formatting. Their disposition and the
whole-change gate remain in DSLP-4.


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


**Whole-change mutation trial**

The complete `buildsys.inputs.*` scope contains 568 identities at
`a6ac0d1`. With `test_inputs.py` alone, mutmut caught 432, missed 126
and marked ten identities as unexercised. The ten belong to
`canonical_json` and `identity`. Adding their consumers in
`test_phases.py` produced 446 caught and 122 surviving with every
identity exercised. Use the pinned macOS ARM64, Python 3.15.2 and
mutmut 3.8.1 setup from the phase trial.

Buildlib `1497970` parses NUL-delimited Git changes and reconciles the
mutmut metadata and generated spans. A local CMake selector using those
readers selected inputs, phases and archive work for a change to
`buildsys/phases.py` mixed with deletion of
`test_deterministic_archive_and_inventory`. The production control
assigned `self.root / name` to a local before returning it. Removing
the test reopened exactly three package mutation identities,
`buildsys.package.x_create__mutmut_34`, `__mutmut_37` and
`__mutmut_41`. The same package scope moved from 291 to 288 caught.
The docs-only control selected nothing. The unknown-production and
missing-result controls failed.

Use whole modules with the fixtures that exercise their callers.
Keep the full native controller check for platform-dependent behavior.
The remaining survivor dispositions, complete path selection and hosted
controls remain open under DSLP-4.


The tree-digest fixtures now isolate content changes, execute-bit changes,
and symlink retargeting. The phase case excludes the root record and
checks that nested records and relative paths still affect the digest.
The same 568 identities with both input and phase fixtures moved from
446 caught and 122 surviving to 455 caught and 113 surviving. All 25
input cases passed with the pinned controller tools.

A concurrent cache-store fixture pauses both writers before their real
atomic replace. With the shared staging filename at `e524954`, one writer
raised `FileNotFoundError` after the other moved the file. Each store now
uses its own staging directory in the cache filesystem. Both writers return
the same verified object and leave only that object behind. A second fixture
changes the source during the copy and verifies refusal, staging cleanup and
a successful retry. The input and phase suite passed 35 tests and 38 subtests.

The rename fixture also checks that staged files are under the destination's
object directory. Removing that directory argument leaked staging to the
default temporary filesystem on two Mutmut identities. With the same
`613bf9d` production source, Mutmut 3.8.1 and pytest 9.2.0 moved from
32 catches and six survivors to 34 catches and four survivors across
the same 38 `Cache.store` identities. The four remaining edits only
change the prefix of the private temporary directory.

Use the input trial layout with `only_mutate = ["buildsys/inputs.py"]`
and `pytest_add_cli_args_test_selection = ["tests/controller/test_inputs.py::CacheTests"]`.
Run `mutmut run --max-children 1 'buildsys.inputs.*Cache*store*'` in both
copies with the same locked wheel. Compare store identities in
`mutants/buildsys/inputs.py.meta`.

**Sealed controller branch coverage**

[Run 44403063173](https://github.com/laputa-systems/cmake-build/actions/runs/44403063173)
exercised the ordinary 137 tests in 21 modules without failures on
native x86-64 Alpine 3.24.2 with Python 3.14.10. The tracked controller
inputs match `096a0df`. Coverage.py 7.17.3 combined data from the parent
and subprocesses, and the report includes the cache publication line
executed in the input-test child.

| Scope | Covered statements | Covered branches |
| --- | ---: | ---: |
| `build.py` and `buildsys/`, 26 files | 1,995 / 3,161 | 534 / 972 |
| `build.py` | 275 / 601 | 59 / 162 |
| `buildsys/inputs.py` | 239 / 250 | 97 / 110 |
| `buildsys/phases.py` | 71 / 71 | 18 / 18 |
| `buildsys/package.py` | 118 / 125 | 44 / 50 |
| `buildsys/sandbox.py` | 136 / 181 | 15 / 30 |

Reproduce with the [pinned trial workflow](https://github.com/laputa-systems/cmake-build/blob/c1b6397b72c671e5bfeff61a32e0f82cb7ac961e/.github/workflows/native-coverage-trial.yml).
Prepare the verified native build, then verify and unpack the upstream
pure-Python wheel into the temporary Python user site. Start the regular
controller command under branch coverage in the network-sealed builder,
combine the subprocess data, and inspect the JSON report. The wheel's
SHA-256 is `21745c08f2835b847a16887b748d3084dddeb0571ae2a0d62e33644413568b99`.
The configured mirror rejected reads of the pure-Python and CPython 3.14
musl variants with HTTP 404. The retained coverage entry point needs a
compatible mirrored wheel. The native artifact trial above covers the
packaged runtime. Wider controller mutation remains open.

**Bootstrap input metadata**

The matched `_bootstrap_input` selection at `ca0cc4c` contains 99
identities. The original lock tests caught 81 and missed 18. The new
tests caught all 99 with the same production file and identity set.
The tests preserve a zero-byte pin, license and purpose, reject invalid
string, digest and size values, and require the package or lock location
in the diagnostic. All 29 input cases and 32 subtests passed.

Use the sealed input trial setup with
`pytest_add_cli_args_test_selection = ["tests/controller/test_inputs.py::LockTests"]`
and select `buildsys.inputs.x__bootstrap_input__mutmut_*` under Mutmut
3.8.1 and pytest 9.2.0. Compare the selected keys and exit codes in
`mutants/buildsys/inputs.py.meta`. Other input functions and the
whole-change workflow still need qualification.

**Persisted phase tree identity**

At `a645b17`, the original input and phase tests caught 44 of 72
`tree_digest` identities. The new fixture caught 70 with the same
production code and selected keys. It verifies a fixed digest for a
directory, regular and executable files, a symbolic link and a FIFO.
It builds the same tree in two orders and omits a metadata file that
sorts before every included root entry.

Use the sealed input trial setup with `tests/controller/test_inputs.py`
and `tests/controller/test_phases.py` as the pytest selection. Run
`mutmut run --max-children 1 'buildsys.inputs.x_tree_digest__mutmut_*'`
on Python 3.15.2 with Mutmut 3.8.1 and pytest 9.2.0. Compare the selected
keys and outcomes in `mutants/buildsys/inputs.py.meta`. The only survivors,
10 and 12, sort by the full path instead of its name. All compared paths
are children of the same directory on the supported POSIX platforms.

**Input lock and fetch boundaries**

At `fc472b1`, the complete input selection had 571 identities.
The original input and phase tests caught 503. The new cases caught
512 with the same source and selected keys. They verify the source
lock path in missing-size diagnostics, reject an unknown source
target, preserve an empty lookup for an absent bootstrap target,
and check offline refusal and the caller's timeout. A second fetch
uses the verified cached object after the local source is removed.

Use the same sealed input trial with
`only_mutate = ["buildsys/inputs.py"]`. Select `buildsys.inputs.*`
and compare the full identity keys and outcome codes in
`mutants/buildsys/inputs.py.meta`. Of the 59 survivors, 51 are
in archive extraction. The four staging-prefix edits and the two
sibling ordering edits retain their earlier dispositions. The
non-string JSON object key diagnostic is unreachable through the
JSON lock reader. The remaining fetch edit changes the default
timeout from 120 to 121 seconds.

## Tickets



### DSLP-4 · P2 · Tests: coverage, boundary gaps, mutation

- **Area:** deslop · tests
- **Where:** test suites and CI
- **Problem:** The native branch coverage baseline and scoped input, phase and package mutation results are recorded above. A compatible mirrored coverage wheel, remaining critical decisions and the retained whole-change lane remain open.
- **Recommendation:** Run the deslop Tests step. Accept: no undispositioned survivor in critical code, the test cost budget holds, and the lane is green where the tools are mirrored.
- **Fix with:** deslop
- **Effort:** M

### DSLP-5 · P2 · Dead code: tools and debloat

- **Area:** deslop · dead code
- **Where:** whole repository
- **Problem:** The dead-code tools ran and the bootstrap record projection was reduced. The remaining structural review is open.
- **Recommendation:** Run the deslop Dead code step. Accept: tools clean or allowlisted with reasons; walk-backs filed as Needs owner tickets.
- **Fix with:** deslop
- **Effort:** M
