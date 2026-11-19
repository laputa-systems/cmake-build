Prefix: DSLP
Next: 11

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier A). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

## Report

DSLP-1 base: `dfd9c86c33e52bf56c0eb699d1d8a166817c82e4`, the
parent of Ground squash PR #10 (`cc8296d`). Completion review compares that
base through `16aa3d643c3014b6258d793b4c49014f71d7e1a5`.

**Scorecard.** Tracked Python lines (`build.py` and `buildsys/`; all `tests/`
Python): source 4,567 → 4,955; tests 3,293 → 10,260. The same file scopes
contain 1 → 3 and 2 → 2 escape-hatch matches respectively; an increase is
not a proof of a weaker type contract. Warm sealed `make test`: 9.17/9.41 s
at Ground; current comparable cost not recorded. Whole-controller coverage:
before not recorded; after 1,995/3,161 statements and 534/972 branches
([native run](https://github.com/laputa-systems/cmake-build/actions/runs/44403063173)).
Bootstrap parser coverage: 221 → 235/254 statements and 80 → 93/110 branches.

Required mutation selections recorded caught/total: inputs 535/565, phases
169/178, tree digest 70/72, cache store 34/38, package 314/319, toolchain
223/225, generation 121/141, CLI 373/376, atomic writer 21/21. Misses include
equivalent private naming, formatting or diagnostics; four case-only generation
variants remain individually unverified on case-sensitive Linux. Timeout and
unviable counts and historical runner-minutes were not retained. Advisory
coordinator selections recorded 900/950 and 1,108/1,355; these are different
scopes and remaining identities were not fully grouped. The DSLP-4 closure
used 0 new runner-minutes. These numbers describe trials, not a mandatory gate;
the protected behaviors are lock and cache integrity, safe extraction, phase
reuse, archive admission, atomic activation and failure reporting. Five named
test-slice defects were fixed: malformed benchmark samples, median overflow,
JUnit count mismatch, listener leak and reproduction cleanup. The bootstrap
trial protected input ordering, explicit Rust roles and Alpine diagnostics.

Dead code: three unused bootstrap fields, six source lines removed (#31); no
dependencies removed. Findings: DSLP-6 P2 fixed; DSLP-7 P2 remains open and
environment-blocked (perf-gate-ready reports a busy host); DSLP-8–10 P3 open.
Aggregate historical filed/fixed counts by priority were not retained. No
completion-review defect demonstrated; escaped regressions: none established,
not a claim of absence. Size and memory gates passed the exact two-platform
qualification ([run](https://github.com/laputa-systems/cmake-build/actions/runs/44354687939));
timing performance verdict deferred: host busy, no valid interleaved gate.

**Steps and cost.** Ground (#10) mapped boundaries and measured the sealed
113-test baseline; lint 1.22 s cold/1.18 s warm on macOS. Diagnose reproduced
stale generation evidence; DSLP-6 refreshed results atomically (#12). Types
adopted missing generic argument, unsound return and unused ignore checks;
witnesses and malformed-input fixes closed the strict inventory. Tests (#127)
added boundary witnesses and the scoped trials above. Dead code (#128) traced
Vulture's 30 findings to live uses after the bootstrap cut; Ruff and deptry
passed. Bench (#129) added a tiered entrypoint and early admission; the native
matrix was not run locally. Report reviewed the cumulative change; no new
finding was established. Per-step wall times and CI runner-minutes beyond the
measurements above were not retained. Historical detail is in the merged PRs
and this file's Git history.

**Method feedback.** Assert exact report counts and cleanup after failure: the
campaign found mismatched JUnit counts and incomplete worktree cleanup. Vulture
flagged serialized fields and callbacks as unused; its 30 hits were discovery,
not a safe deletion list. The final dead-code structural review found no further
cut. The broad CLI mutation trial exceeded its CPU guard, and advisory survivor
grouping remains incomplete.

**Shared-file gaps.** The deslop report template requests mutant outcomes and
runner cost, but older trials did not retain full outcome classes or times;
shared campaign tooling should retain scope type, behavior dispositions and
runner-minutes with each result. The template also needs the revised policy's
behavior and defect counts. No shared files were changed here.

## Tickets

### DSLP-7 · P2 · Cover user-visible timing regressions with valid gates

- **Area:** Performance measurement
- **Where:** buildsys/benchmark.py:224; buildsys/budgets.py:115; release-budgets.json
- **Problem:** The coordinator enforces size and image RSS but does not gate wall or CPU timing; existing x86 timing limits are unused and ARM lacks them. A configure or startup regression can pass release. Host load alone does not establish validity.
- **Recommendation:** Establish representative interleaved timing gates and host readiness with an accepted anchor; review obsolete timing limits.
- **Fix with:** bench-pyramid
- **Effort:** L


### DSLP-8 · P3 · Add attribution for configure and memory regressions

- **Area:** Performance observability
- **Where:** tests/benchmark/run.py:142; buildsys/benchmark.py:217
- **Problem:** The untimed syscall summary covers unchanged reconfigure, but CPU sampling, allocation attribution, operation traces and I/O byte counters are absent; image RSS excludes child memory. Regressions cannot reliably be attributed.
- **Recommendation:** Add separate opt-in CPU sampling and scoped memory or allocation diagnostics, then evaluate I/O tracing.
- **Fix with:** bench-pyramid
- **Effort:** M


### DSLP-9 · P3 · Clarify superseded historical performance studies

- **Area:** Performance documentation
- **Where:** docs/performance-legacy-x86_64.md:3; docs/performance-legacy-aarch64.md:3; docs/performance-rust-release.md:3; docs/performance-o2.md:3; docs/performance-oz.md:3; docs/performance-thinlto.md:3; docs/performance-gc.md:3
- **Problem:** Legacy and Rustls study RSS is invalid and superseded by corrected image RSS baselines; O2, Oz, ThinLTO and GC are historical experiments, not current release gates. Readers can mistake old comparisons for current evidence.
- **Recommendation:** Index the studies by artifact and explicitly distinguish superseded findings and current gates without deleting history.
- **Fix with:** technical-writing
- **Effort:** S


### DSLP-10 · P3 · Improve benchmark admission and workload coverage

- **Area:** Performance operability
- **Where:** buildsys/benchmark.py:224; tests/benchmark/run.py:23; docs/building.md:73
- **Problem:** The coordinator requires a complete matrix and finds some prerequisites after preparation; no short production workload is selectable. Configure and startup cover real work but package, install, CTest, CPack and network journeys lack performance measurements.
- **Recommendation:** Add a short supported production path and early read-only admission, then assess representative missing journeys.
- **Fix with:** bench-pyramid
- **Effort:** L
