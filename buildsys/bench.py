from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIERS = ('edit', 'change', 'scenario', 'full')
WORKLOADS = {
    'controller': ('edit', 'harness', 'benchmark accounting and admission tests', 'seconds', (sys.executable, 'build.py', 'controller-test', '-k', 'benchmark')),
    'release-matrix': ('full', 'cmake', 'startup and project configure matrix with release budgets', 'over 10 minutes', (sys.executable, 'build.py', 'benchmark')),
}


def select(tier: str, names: list[str], areas: list[str], skips: list[str]) -> tuple[list[str], dict[str, str]]:
    for values, valid, label in ((names, WORKLOADS, 'workload'), (skips, WORKLOADS, 'skip'),
                                 (areas, {item[1] for item in WORKLOADS.values()}, 'area')):
        unknown = set(values) - set(valid)
        if unknown:
            raise ValueError(f'unknown {label}: {", ".join(sorted(unknown))}')
    selected = []
    excluded = {}
    for name, (level, area, *_rest) in WORKLOADS.items():
        reason = ('above tier ceiling' if TIERS.index(level) > TIERS.index(tier) else
                  'not selected by workload' if names and name not in names else
                  'not selected by area' if areas and area not in areas else
                  'explicitly skipped' if name in skips else '')
        if reason:
            excluded[name] = reason
        else:
            selected.append(name)
    if not selected:
        raise ValueError('selection matches no workloads')
    return selected, excluded


def preflight(selected: list[str], target: str | None) -> list[str]:
    failures = []
    if 'release-matrix' in selected:
        from buildsys import benchmark, targets

        machine = {'x86_64': 'x86_64', 'aarch64': 'aarch64', 'arm64': 'aarch64'}.get(platform.machine())
        native = f'{machine}-unknown-linux-musl' if machine else None
        triple = target or native
        if platform.system() != 'Linux' or not native or triple != native:
            failures.append('release-matrix: use a native Linux host matching --target; no emulation')
        for tool in ('docker', 'strace'):
            if not shutil.which(tool):
                failures.append(f'release-matrix: install {tool} on the native host')
        if triple:
            try:
                benchmark.admit(ROOT, targets.target(triple))
            except (benchmark.BenchmarkError, OSError, ValueError) as error:
                failures.append(f'release-matrix: admission failed: {error}; prepare or qualify the named input')
        else:
            failures.append('release-matrix: specify a supported native --target')
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description='Select and run benchmark workloads')
    parser.add_argument('--tier', choices=TIERS, default='full')
    parser.add_argument('--workload', action='append', default=[])
    parser.add_argument('--area', action='append', default=[])
    parser.add_argument('--skip', action='append', default=[])
    parser.add_argument('--target')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.list:
        for name, (tier, area, purpose, cost, command) in WORKLOADS.items():
            print(f'{name}: {tier}; area={area}; {purpose}; estimated {cost}; {shlex.join(command)}')
        return 0
    try:
        selected, excluded = select(args.tier, args.workload, args.area, args.skip)
    except ValueError as error:
        parser.error(str(error))
    for name, reason in excluded.items():
        print(f'excluded {name}: {reason}')
    for name in selected:
        command = list(WORKLOADS[name][4])
        if name == 'release-matrix' and args.target:
            command += ['--target', args.target]
        print(f'{name}: {shlex.join(command)}')
    if args.dry_run:
        return 0
    failures = preflight(selected, args.target)
    print(f'host: {platform.platform()}; load average: {os.getloadavg() if hasattr(os, "getloadavg") else "unavailable"}; readiness not established')
    if failures:
        for failure in failures:
            print(f'preflight: {failure}', file=sys.stderr)
        return 1
    print('preflight: selected requirements and coordinator admission passed; later preparation may require additional inputs')
    if args.check:
        return 0
    directory = ROOT / '.work/benchmark-results' / datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%S.%fZ')
    directory.mkdir(parents=True)
    results = {}
    for name in selected:
        command = list(WORKLOADS[name][4])
        if name == 'release-matrix' and args.target:
            command += ['--target', args.target]
        start = time.monotonic()
        with (directory / f'{name}.log').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        results[name] = {'exit_status': result.returncode, 'duration_seconds': time.monotonic() - start,
                         'timing_validity': 'inconclusive: host readiness not established' if name == 'release-matrix' else 'not a timing measurement',
                         'verdict': 'see coordinator report and budget checks' if name == 'release-matrix' else 'completion is not a performance verdict'}
        if name == 'release-matrix' and result.returncode == 0:
            shutil.copy2(ROOT / 'docs/performance.md', directory / 'performance.md')
    (directory / 'summary.json').write_text(json.dumps({'workloads': results, 'exclusions': excluded}, indent=2) + '\n')
    print(f'results: {directory}')
    return int(any(item['exit_status'] != 0 for item in results.values()))


if __name__ == '__main__':
    sys.exit(main())
