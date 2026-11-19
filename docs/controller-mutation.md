# Controller mutation gate

The 18-scope native head `c5c89e0ff` passed all 38 jobs,
including both distribution scopes on both Linux architectures.
[Native run](https://github.com/laputa-systems/cmake-build/actions/runs/44516789463)

The trial now uses the same `make mutants-diff MUTATION_BASE=<commit>`
command as the local check. `MUTATION_SCOPE` selects one member of
the computed change union. The Buildlib reader is archived from the
pinned revision in `.github/mutation-buildlib-revision`. Set
`MUTATION_BUILDLIB` to a checkout containing that commit when it
is outside the default local path. Every invocation uses fresh
scratch for the selected scopes.

## Hosted whole-change controls

- A documentation-only change selected no modules. The plan and
  final check passed with the controller matrix skipped.
  [Documentation control](https://github.com/laputa-systems/cmake-build/actions/runs/44518341877)
- The input branch with no witness reopened five identities on both
  Linux hosts and failed the aggregate.
  [Uncovered branch](https://github.com/laputa-systems/cmake-build/actions/runs/44518353110)
- Removing the license witness passed ordinary CI and reopened the
  same three identities on both Linux hosts. Adding an unrelated
  covered bootstrap edit retained those failures and selected bootstrap.
  Both bootstrap jobs caught all 268 identities. The corresponding
  macOS deletion trial also left two capitalization variants alive.
  [Test deletion](https://github.com/laputa-systems/cmake-build/actions/runs/44518364284) ·
  [Mixed diff](https://github.com/laputa-systems/cmake-build/actions/runs/44518378427)
- The x86-64 license job exhausted a one-second budget. The ARM64
  license job rejected absent results, and the x86-64 stage job
  rejected an absent scope. Those three jobs and the aggregate failed.
  [Incomplete results and budget](https://github.com/laputa-systems/cmake-build/actions/runs/44518766634)

The clean 18-scope Make runs at `08d86c45b` and `e03d6d515` passed all
38 jobs each. GitHub job timestamps show per-run medians of 33 and
35 seconds among 36 native jobs in each run. The maximums were 163
and 150 seconds. The runs used 1,648 and 1,583 runner seconds including
plan and final jobs, with 227 and 469 wall seconds including queueing.
The second runs mutmut under the shared 600-second deadline. Neither
sample exceeds the campaign's ten-minute per-job median target.
[Make trial](https://github.com/laputa-systems/cmake-build/actions/runs/44517720657) ·
[Budgeted Make trial](https://github.com/laputa-systems/cmake-build/actions/runs/44518717818)

The 21-scope head `753f55a06` passed all 44 jobs. Both Linux
process-accounting jobs caught 192 of 193. The 42 native jobs had
a 31-second median and 149-second maximum. GitHub job timestamps
show 264 elapsed seconds and 1,706 runner seconds including plan
and aggregate verification.
[Native process accounting](https://github.com/laputa-systems/cmake-build/actions/runs/44522562421)

## Whole qualification controller

At `b0256cdba`, a fresh macOS ARM64 archive ran the three
controller suites in the trial's `qualify` case with CPython
3.15.2, mutmut 3.8.1, and pytest 9.2.0. All 1,215 variants
ran. The suites caught 1,157, and the checker verified all 58
survivors against the controller and generated-body hashes.

The dispositions above cover temporary names, default falsey
arguments, local-only cache access, the single managed report
heading, and the existing scratch parent. The 18 case-only path
changes are allowed on Darwin's case-folded trial volume. Both
Linux jobs caught 1,175 of 1,215 variants, including all 18
case-only changes. Both installed the locked native `jaq` for
the XML cases. [Native trial](https://github.com/laputa-systems/cmake-build/actions/runs/44487514643)
