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

## Tickets

### DSLP-2 · P2 · Diagnose: ultrareview into this backlog

- **Area:** deslop · diagnose
- **Where:** whole repository
- **Problem:** No review has ranked this repository's risks for the deslop pass.
- **Recommendation:** Run the deslop Diagnose step. Accept: the diff touches only docs, comments, and this file, and every finding names its Fix with.
- **Fix with:** deslop
- **Effort:** S

### DSLP-3 · P2 · Types: strict profile and typing findings

- **Area:** deslop · types
- **Where:** type checker and lint configuration; Python sources
- **Problem:** The strict-profile candidates in the deslop skill's tools reference have not been measured here.
- **Recommendation:** Run the deslop Types step. Accept: clean at the adopted profile, escape hatches not increased, witnesses recorded.
- **Fix with:** deslop
- **Effort:** M

### DSLP-4 · P2 · Tests: coverage, boundary gaps, mutation

- **Area:** deslop · tests
- **Where:** test suites and CI
- **Problem:** Coverage and mutation results are unmeasured; no deslop mutation lane exists.
- **Recommendation:** Run the deslop Tests step. Accept: no undispositioned survivor in critical code, the test cost budget holds, and the lane is green where the tools are mirrored.
- **Fix with:** deslop
- **Effort:** M

### DSLP-5 · P2 · Dead code: tools and debloat

- **Area:** deslop · dead code
- **Where:** whole repository
- **Problem:** No dead-code scan has run.
- **Recommendation:** Run the deslop Dead code step. Accept: tools clean or allowlisted with reasons; walk-backs filed as Needs owner tickets.
- **Fix with:** deslop
- **Effort:** M
