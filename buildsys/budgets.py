from __future__ import annotations

import json
import math
import statistics
from pathlib import Path


class BudgetError(Exception):
    pass


def _targets(document: dict) -> dict:
    if (not isinstance(document, dict) or type(document.get('schema_version')) is not int
        or document['schema_version'] != 1 or not isinstance(document.get('targets'), dict)):
        raise BudgetError('release budgets have an invalid schema')
    return document['targets']


def load(path: Path) -> dict:
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise BudgetError(f'cannot read release budgets: {error}') from error
    _targets(document)
    return document


def _metric_values(metrics: dict, target: str, name: str) -> tuple[float, float]:
    metric = metrics.get(name)
    if not isinstance(metric, dict):
        raise BudgetError(f'release budgets lack {target} {name}')
    values = (metric.get('value'), metric.get('allowed_regression'))
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values):
        raise BudgetError(f'release budget is invalid: {target} {name}')
    return values


def check_size(document: dict, target: str, tree: Path, archive: Path) -> dict[str, int]:
    entry = _targets(document).get(target)
    if not isinstance(entry, dict) or not isinstance(entry.get('metrics'), dict):
        raise BudgetError(f'release budgets lack target {target}')
    limits = {}
    for name in ('executable_bytes', 'unpacked_bytes', 'archive_bytes'):
        limits[name] = sum(_metric_values(entry['metrics'], target, name))
    executable = tree / 'usr/bin/cmake'
    if executable.is_symlink() or not executable.is_file():
        raise BudgetError('packaged CMake executable is missing or not a regular file')
    measurements = {
        'executable_bytes': executable.stat().st_size,
        'unpacked_bytes': sum(path.stat().st_size for path in tree.rglob('*') if path.is_file() and not path.is_symlink()),
        'archive_bytes': archive.stat().st_size,
    }
    exceeded = [f'{name}: {value} > {limits[name]:g}' for name, value in measurements.items() if value > limits[name]]
    if exceeded:
        raise BudgetError(f'{target} size budget exceeded: {", ".join(exceeded)}')
    return measurements


def memory_baseline(records: list[dict]) -> dict[str, dict]:
    metrics = {}
    for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang'):
        name = f'{workload}_initial_rss_kib'
        samples = [record['max_rss_kib'] for record in records
                   if record.get('variant') == 'product' and record.get('workload') == workload
                   and record.get('scenario') == 'initial']
        if len(samples) < 5 or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in samples):
            raise BudgetError(f'insufficient memory samples: {workload}')
        measured = statistics.median(samples)
        spread = max(samples) - min(samples)
        lower, _, upper = statistics.quantiles(samples, n=4, method='inclusive')
        metrics[name] = {'value': measured, 'spread': spread, 'central_spread': upper - lower,
                         'allowed_regression': max(measured * 0.03, 2 * spread)}
    return metrics


def check_memory(document: dict, target: str, records: list[dict]) -> dict[str, float]:
    entry = _targets(document).get(target)
    if not isinstance(entry, dict) or not isinstance(entry.get('metrics'), dict):
        raise BudgetError(f'release budgets lack target {target}')
    measurements = {}
    for name, sample in memory_baseline(records).items():
        baseline, allowance = _metric_values(entry['metrics'], target, name)
        measured = sample['value']
        limit = baseline + max(allowance, 2 * sample['central_spread'])
        if measured > limit:
            raise BudgetError(f'{target} memory budget exceeded: {name}: {measured:g} > {limit:g}')
        measurements[name] = measured
    return measurements


def validate_memory_source(document: dict, target: str, archive_sha256: str) -> str:
    entry = _targets(document).get(target)
    if not isinstance(entry, dict) or not isinstance(entry.get('metrics'), dict):
        raise BudgetError(f'release budgets lack target {target}')
    status = entry.get('memory_status')
    if status == 'measured':
        for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang'):
            _metric_values(entry['metrics'], target, f'{workload}_initial_rss_kib')
    elif status == 'unmeasured' and entry.get('archive_sha256') == archive_sha256:
        if any(name.endswith('_initial_rss_kib') for name in entry['metrics']):
            raise BudgetError(f'partial memory baseline is invalid: {target}')
    else:
        raise BudgetError(f'memory baseline must be measured on the recorded {target} archive')
    return status


def apply_memory(document: dict, target: str, archive_sha256: str, records: list[dict]) -> bool:
    status = validate_memory_source(document, target, archive_sha256)
    if status == 'measured':
        check_memory(document, target, records)
        return False
    entry = document['targets'][target]
    entry['metrics'].update(memory_baseline(records))
    entry['memory_status'] = 'measured'
    return True
