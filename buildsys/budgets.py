from __future__ import annotations

import json
import math
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, TypedDict, TypeGuard

from buildlib import hashing, locks
from buildlib.locks import LockError


class BudgetError(Exception):
    pass


RSS_SCOPE = 'cmake-image-v1'


def _is_record(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def read(path: Path) -> dict[str, object]:
    try:
        locks.load_budgets(path)
        document: object = json.loads(Path(path).read_text())
    except (LockError, OSError, ValueError) as error:
        raise BudgetError(f'cannot read release budgets: {error}') from error
    if not _is_record(document):
        raise BudgetError('cannot read release budgets: expected a JSON object')
    return document


def _entry(document: Mapping[str, object], target: str) -> tuple[dict[str, object], dict[str, object]]:
    targets = document.get('targets')
    if _is_record(targets):
        entry = targets.get(target)
        if _is_record(entry):
            metrics = entry.get('metrics')
            if _is_record(metrics):
                return entry, metrics
    raise BudgetError(f'release budgets lack target {target}')


def _metric_value(value: object, target: str, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise BudgetError(f'release budget is invalid: {target} {name}')
    return value


def _metric_values(metrics: Mapping[str, object], target: str, name: str) -> tuple[float, float]:
    metric = metrics.get(name)
    if not _is_record(metric):
        raise BudgetError(f'release budgets lack {target} {name}')
    return (
        _metric_value(metric.get('value'), target, name),
        _metric_value(metric.get('allowed_regression'), target, name),
    )


def check_size(document: Mapping[str, object], target: str, tree: Path, archive: Path) -> dict[str, int]:
    _, metrics = _entry(document, target)
    limits = {}
    for name in ('executable_bytes', 'unpacked_bytes', 'archive_bytes'):
        limits[name] = sum(_metric_values(metrics, target, name))
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


class _MemoryMetric(TypedDict):
    value: float
    spread: int
    central_spread: float
    allowed_regression: float


def memory_baseline(records: Sequence[Mapping[str, object]]) -> dict[str, _MemoryMetric]:
    metrics: dict[str, _MemoryMetric] = {}
    sample_counts = set()
    for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang'):
        name = f'{workload}_initial_rss_kib'
        samples = []
        for record in records:
            if record.get('variant') != 'product' or record.get('workload') != workload or record.get('scenario') != 'initial':
                continue
            value = record.get('max_rss_kib')
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise BudgetError(f'insufficient memory samples: {workload}')
            samples.append(value)
        if len(samples) < 5:
            raise BudgetError(f'insufficient memory samples: {workload}')
        sample_counts.add(len(samples))
        measured = statistics.median(samples)
        spread = max(samples) - min(samples)
        lower, _, upper = statistics.quantiles(samples, n=4, method='inclusive')
        metrics[name] = {'value': measured, 'spread': spread, 'central_spread': upper - lower,
                         'allowed_regression': max(measured * 0.03, 2 * spread)}
    if len(sample_counts) != 1:
        raise BudgetError('memory workloads have different sample counts')
    return metrics


def check_memory(document: Mapping[str, object], target: str, records: Sequence[Mapping[str, object]]) -> dict[str, float]:
    entry, metrics = _entry(document, target)
    if entry.get('rss_scope') != RSS_SCOPE:
        raise BudgetError(f'{target} memory baseline has an incompatible RSS scope')
    measurements = {}
    for name, sample in memory_baseline(records).items():
        baseline, allowance = _metric_values(metrics, target, name)
        measured = sample['value']
        limit = baseline + max(allowance, 2 * sample['central_spread'])
        if measured > limit:
            raise BudgetError(f'{target} memory budget exceeded: {name}: {measured:g} > {limit:g}')
        measurements[name] = measured
    return measurements


def validate_memory_source(document: Mapping[str, object], target: str, archive_sha256: str, archive_size: int) -> Literal['measured', 'unmeasured']:
    entry, metrics = _entry(document, target)
    status = entry.get('memory_status')
    if status == 'measured':
        if entry.get('rss_scope') != RSS_SCOPE:
            raise BudgetError(f'{target} memory baseline has an incompatible RSS scope')
        repetitions = entry.get('memory_repetitions')
        if type(repetitions) is not int or repetitions < 5:
            raise BudgetError(f'{target} memory baseline has insufficient repetitions')
        baseline_sha = entry.get('archive_sha256')
        baseline_size = entry.get('memory_archive_bytes')
        if not hashing.is_sha256(baseline_sha) or type(baseline_size) is not int or baseline_size <= 0:
            raise BudgetError(f'{target} memory baseline has invalid archive identity')
        for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang'):
            _metric_values(metrics, target, f'{workload}_initial_rss_kib')
        return 'measured'
    if (status == 'unmeasured' and entry.get('archive_sha256') == archive_sha256
          and type(entry.get('memory_archive_bytes')) is int and entry['memory_archive_bytes'] == archive_size):
        if ('rss_scope' in entry or 'memory_repetitions' in entry
            or any(name.endswith('_initial_rss_kib') for name in metrics)):
            raise BudgetError(f'partial memory baseline is invalid: {target}')
        return 'unmeasured'
    raise BudgetError(f'memory baseline must be measured on the recorded {target} archive')


def apply_memory(document: Mapping[str, object], target: str, archive_sha256: str, archive_size: int, records: Sequence[Mapping[str, object]]) -> bool:
    status = validate_memory_source(document, target, archive_sha256, archive_size)
    if status == 'measured':
        check_memory(document, target, records)
        return False
    entry, metrics = _entry(document, target)
    metrics.update(memory_baseline(records))
    entry['rss_scope'] = RSS_SCOPE
    entry['memory_repetitions'] = sum(record.get('variant') == 'product' and record.get('workload') == 'fmt'
                                      and record.get('scenario') == 'initial' for record in records)
    entry['memory_status'] = 'measured'
    return True


class _MemoryEvidence(TypedDict):
    target: str
    archive_sha256: str
    archive_size: int
    budget_sha256: str
    repetitions: int
    rss_scope: str
    measurements: dict[str, float]
    result: Literal['passed']


def release_evidence(document: Mapping[str, object], target: str, archive_sha256: str, archive_size: int,
                     budget_sha256: str, repetitions: int, records: Sequence[Mapping[str, object]]) -> _MemoryEvidence:
    if repetitions < 5 or validate_memory_source(document, target, archive_sha256, archive_size) != 'measured':
        raise BudgetError('release memory acceptance requires a measured baseline and five repetitions')
    return {'target': target, 'archive_sha256': archive_sha256, 'archive_size': archive_size,
            'budget_sha256': budget_sha256, 'repetitions': repetitions,
            'rss_scope': RSS_SCOPE, 'measurements': check_memory(document, target, records), 'result': 'passed'}
