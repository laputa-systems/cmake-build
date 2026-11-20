Prefix: CMKB
Next: 5

# Open work
### CMKB-1 · P3 · Cover user-visible timing regressions with valid gates

- **Area:** Performance measurement
- **Where:** buildsys/benchmark.py:224; buildsys/budgets.py:115; release-budgets.json
- **Problem:** The coordinator enforces size and image RSS but does not gate wall or CPU timing; existing x86 timing limits are unused and ARM lacks them. A configure or startup regression can pass release. Host load alone does not establish validity.
- **Recommendation:** Establish representative interleaved timing gates and host readiness with an accepted anchor; review obsolete timing limits.
- **Fix with:** bench-pyramid
- **Effort:** L

### CMKB-2 · P3 · Add attribution for configure and memory regressions

- **Area:** Performance observability
- **Where:** tests/benchmark/run.py:142; buildsys/benchmark.py:217
- **Problem:** The untimed syscall summary covers unchanged reconfigure, but CPU sampling, allocation attribution, operation traces and I/O byte counters are absent; image RSS excludes child memory. Regressions cannot reliably be attributed.
- **Recommendation:** Add separate opt-in CPU sampling and scoped memory or allocation diagnostics, then evaluate I/O tracing.
- **Fix with:** bench-pyramid
- **Effort:** M

### CMKB-3 · P3 · Clarify superseded historical performance studies

- **Area:** Performance documentation
- **Where:** docs/performance-legacy-x86_64.md:3; docs/performance-legacy-aarch64.md:3; docs/performance-rust-release.md:3; docs/performance-o2.md:3; docs/performance-oz.md:3; docs/performance-thinlto.md:3; docs/performance-gc.md:3
- **Problem:** Legacy and Rustls study RSS is invalid and superseded by corrected image RSS baselines; O2, Oz, ThinLTO and GC are historical experiments, not current release gates. Readers can mistake old comparisons for current evidence.
- **Recommendation:** Index the studies by artifact and explicitly distinguish superseded findings and current gates without deleting history.
- **Fix with:** technical-writing
- **Effort:** S

### CMKB-4 · P3 · Improve benchmark admission and workload coverage

- **Area:** Performance operability
- **Where:** buildsys/benchmark.py:224; tests/benchmark/run.py:23; docs/building.md:73
- **Problem:** The coordinator requires a complete matrix and finds some prerequisites after preparation; no short production workload is selectable. Configure and startup cover real work but package, install, CTest, CPack and network journeys lack performance measurements.
- **Recommendation:** Add a short supported production path and early read-only admission, then assess representative missing journeys.
- **Fix with:** bench-pyramid
- **Effort:** L

