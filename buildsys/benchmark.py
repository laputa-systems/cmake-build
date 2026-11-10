from __future__ import annotations

import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from . import package, sandbox, stage
from .inputs import Cache, bootstrap_inputs, digest_bytes, load_bootstrap, load_sources, safe_extract, tree_digest
from .phases import PhaseCache
from .targets import Target


class BenchmarkError(Exception):
    pass


def _write_atomic(path: Path, content: str, scratch: Path) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix='benchmark-report-', dir=scratch)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def interleaved_orders(variants: tuple[str, ...], repetitions: int):
    if not variants or len(set(variants)) != len(variants) or repetitions < 1:
        raise BenchmarkError('invalid benchmark variants or repetitions')
    for iteration in range(repetitions):
        offset = iteration % len(variants)
        yield variants[offset:] + variants[:offset]


def summarize(records: list[dict], repetitions: int) -> dict:
    if not records or repetitions < 1:
        raise BenchmarkError('benchmark produced no measurements')
    groups = defaultdict(list)
    for record in records:
        if (record.get('exit_code') != 0 or not isinstance(record.get('seconds'), (int, float))
            or not math.isfinite(record['seconds']) or record['seconds'] < 0 or record.get('max_rss_kib', -1) < 0):
            raise BenchmarkError('benchmark contains a failed or invalid measurement')
        groups[(record['workload'], record['scenario'], record['variant'])].append(record)
    variants = ('product', 'musl', 'kitware')
    expected = {(workload, scenario, variant)
                for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
                for scenario in ('initial', 'unchanged', 'cmakelists-edit', 'option-change')
                for variant in variants}
    expected.update(('process', scenario, variant) for scenario in ('version', 'script') for variant in variants)
    if set(groups) != expected:
        raise BenchmarkError(f'benchmark scenario coverage differs: missing {sorted(expected - set(groups))}')
    for key, samples in groups.items():
        if len(samples) != repetitions or {sample['iteration'] for sample in samples} != set(range(repetitions)):
            raise BenchmarkError(f'incomplete benchmark samples: {key}')
    return {
        key: {'median_seconds': statistics.median(sample['seconds'] for sample in samples),
              'median_cpu_seconds': statistics.median(sample['cpu_seconds'] for sample in samples),
              'min_seconds': min(sample['seconds'] for sample in samples),
              'max_seconds': max(sample['seconds'] for sample in samples),
              'max_rss_kib': max(sample['max_rss_kib'] for sample in samples)}
        for key, samples in groups.items()
    }


def render(records: list[dict], repetitions: int, metadata: dict) -> str:
    summary = summarize(records, repetitions)
    expected_profiles = {(workload, variant) for workload in ('fmt', 'zstd', 'libjpeg-turbo', 'llvm-clang')
                         for variant in ('product', 'musl', 'kitware')}
    if {(item['workload'], item['variant']) for item in metadata['profiles']} != expected_profiles or len(metadata['profiles']) != len(expected_profiles):
        raise BenchmarkError('file and process profiles are incomplete')
    lines = ['# CMake executable performance', '',
             f"Target: `{metadata['target']}`. Runs per variant: {repetitions}.", '',
             'All three binaries ran in the same native Debian container with the pinned musl toolchain.',
             'Kitware uses glibc while the product and unmodified baseline use musl; runtime and resource',
             'differences are part of the Kitware comparison. The musl baseline uses unmodified CMake with',
             'OpenSSL disabled; the product includes Rustls and patches. Their comparison includes those',
             'product differences and does not isolate an individual compiler flag.',
             'A warmup preceded measurement. Filesystem caches were not pinned; cold-cache results were not',
             'measured. Timings are not release gates.', '',
             f"Host: `{metadata['host']}`. Container: `{metadata['container']}`.",
             f"CPU affinity: `{metadata['cpus']}`. Product archive SHA-256: `{metadata['archive_sha256']}`.",
             f"Official archive SHA-256: `{metadata['official_sha256']}`. Baseline output digest: `{metadata['baseline_digest']}`.",
             f"Tracer: `{metadata['strace_version']}`. Runner SHA-256: `{metadata['runner_sha256']}`.", '',
             '| Project | Version | Source SHA-256 |', '| --- | --- | --- |']
    for item in metadata['projects']:
        lines.append(f"| {item.name} | {item.version} | `{item.sha256}` |")
    lines.extend(['',
             '## Size', '',
             'The official archive includes additional tools and resources, so total package sizes are not like-for-like.', '',
             '| Variant | CMake executable bytes | Regular-file bytes | Archive bytes |',
             '| --- | ---: | ---: | ---: |'])
    for variant in ('product', 'musl', 'kitware'):
        size = metadata['sizes'][variant]
        lines.append(f"| {variant} | {size['executable']} | {size['files']} | {size['archive']} |")
    lines.extend(['', '## Measurements', '',
             'RSS is the kernel-reported maximum for the process and its waited-for children, not the sum',
             'of simultaneous process memory.', '',
             '| Workload | Operation | Variant | Median seconds | Range seconds | Median CPU seconds | Maximum RSS KiB |',
             '| --- | --- | --- | ---: | ---: | ---: | ---: |'])
    for (workload, scenario, variant), value in sorted(summary.items()):
        lines.append(f"| {workload} | {scenario} | {variant} | {value['median_seconds']:.6f} | "
                     f"{value['min_seconds']:.6f}–{value['max_seconds']:.6f} | {value['median_cpu_seconds']:.6f} | {value['max_rss_kib']} |")
    lines.extend(['', '## Raw samples', '',
                  'Seconds, peak RSS in KiB, and one-minute host load before and after each invocation.', '',
                  '| Workload | Operation | Variant | Iteration | Seconds | CPU seconds | Peak RSS KiB | Load before | Load after |',
                  '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
    for record in records:
        lines.append(f"| {record['workload']} | {record['scenario']} | {record['variant']} | "
                     f"{record['iteration'] + 1} | {record['seconds']:.6f} | {record['cpu_seconds']:.6f} | {record['max_rss_kib']} | "
                     f"{record['load_before']:.2f} | {record['load_after']:.2f} |")
    lines.extend(['', '## File and process syscall profiles', '',
                  'These untimed `strace -f -c` profiles cover an unchanged reconfigure after the',
                  'measured runs. They include child processes and use a host tracer, not the release binary.',
                  'Kernel sampling with `perf` is not collected by this command.', ''])
    for profile in metadata['profiles']:
        lines.extend([f"### {profile['workload']}: {profile['variant']}", '', '```text', profile['summary'].rstrip(), '```', ''])
    return '\n'.join(lines) + '\n'


def run(root: Path, target: Target, repetitions: int = 10) -> None:
    if platform.system() != 'Linux':
        raise BenchmarkError('benchmarking requires a native Linux host')
    phases = root / '.work/build' / target.triple / 'phases'
    active = root / '.work/generations' / target.triple / 'active'
    if not active.is_symlink():
        raise BenchmarkError('qualify a candidate before benchmarking')
    generation = active.resolve().parent
    archive = generation / 'artifact.tar.xz'
    results = json.loads((generation / 'results.json').read_text())
    archive_sha256 = package.digest(archive)
    if results.get('archive_sha256') != archive_sha256 or results.get('archive_size') != archive.stat().st_size:
        raise BenchmarkError('qualified archive digest or size does not match results')
    try:
        artifact = package.inspect(archive)
    except package.PackageError as error:
        raise BenchmarkError(f'qualified archive is invalid: {error}') from error
    qualification = results.get('qualification', {})
    if artifact.get('target', {}).get('triple') != target.triple or artifact.get('build', {}).get('mode') != 'qualification' or any(
        qualification.get(name) != 'passed' for name in ('basic', 'parity', 'network', 'projects')
    ) or not qualification.get('upstream'):
        raise BenchmarkError('archive lacks qualification for the requested target')
    reference_phase = phases / 'reference'
    if not (reference_phase / 'build/bin/cmake').is_file():
        raise BenchmarkError('build the unmodified static-musl baseline with the upstream suite first')
    reference_record = json.loads((reference_phase / 'phase.json').read_text())
    if reference_record.get('output_digest') != tree_digest(reference_phase, exclude={'phase.json', 'state.json'}):
        raise BenchmarkError('unmodified baseline output does not match its phase record')
    sources = load_sources(root / 'sources.lock.json')
    lock = load_bootstrap(root / 'bootstrap.lock.json')
    locked = {item.name: item for item in sources if item.target in ('all', target.triple)}
    headers = next(item for item in bootstrap_inputs(lock, target.triple) if item.name == 'linux-headers')
    image_digest = sandbox.image_fingerprint(lock, target, root / 'docker/builder.Dockerfile')
    locked_inputs = {
        'prepare': {'toolchain': locked[f'llvm-toolchain-{target.machine}'].sha256,
                    'musl': locked['musl-source'].sha256, 'linux-headers': headers.sha256, 'image': image_digest},
        'bootstrap': {'cmake': locked['cmake-source'].sha256, 'ninja': locked['ninja-source'].sha256,
                      'samurai': locked['samurai-source'].sha256, 'image': image_digest},
    }
    if reference_record['inputs'].get('image') != image_digest:
        raise BenchmarkError('unmodified baseline builder image has changed')
    for name in ('prepare', 'bootstrap'):
        directory = phases / name
        record = json.loads((directory / 'phase.json').read_text())
        digest = tree_digest(directory, exclude={'phase.json', 'state.json'})
        if record.get('output_digest') != digest or reference_record['inputs'].get(name) != digest:
            raise BenchmarkError(f'unmodified baseline {name} input has changed')
        if any(record['inputs'].get(key) != value for key, value in locked_inputs[name].items()):
            raise BenchmarkError(f'unmodified baseline {name} lock inputs have changed')
    reference = next(item for item in sources if item.name == f'cmake-reference-{target.machine}')
    version = next(item.version for item in sources if item.name == 'cmake-source')
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='benchmark-', dir=scratch) as temporary:
        directory = Path(temporary)
        tracer = shutil.which('strace')
        if tracer is None:
            raise BenchmarkError('strace is required for file and process profiles')
        tracer_version = subprocess.run([tracer, '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
        trace_root = directory / 'trace'
        trace_lib = trace_root / 'lib'
        trace_lib.mkdir(parents=True)
        shutil.copy2(tracer, trace_root / 'strace')
        dependencies = subprocess.run(['ldd', tracer], capture_output=True, text=True, check=False)
        if dependencies.returncode:
            raise BenchmarkError(f'cannot identify strace libraries: {dependencies.stderr}')
        loaders = [Path(line.strip().split(' ', 1)[0]) for line in dependencies.stdout.splitlines()
                   if line.strip().startswith('/') and '=>' not in line]
        if len(loaders) != 1 or not loaders[0].is_file():
            raise BenchmarkError('cannot identify the host strace dynamic loader')
        shutil.copy2(loaders[0], trace_root / 'loader')
        for line in dependencies.stdout.splitlines():
            if '=>' in line:
                name, path = line.strip().split('=>', 1)
                library = Path(path.strip().split(' ', 1)[0])
                if not library.is_file():
                    raise BenchmarkError(f'strace library is missing: {name.strip()}')
                shutil.copy2(library, trace_lib / name.strip())
        candidate = safe_extract(archive, directory / 'candidate') / 'usr'
        official_source = safe_extract(Cache(root / '.work/cache', offline=True).require(reference), directory / 'official')
        official_entries = list(official_source.iterdir())
        if len(official_entries) != 1 or not official_entries[0].is_dir():
            raise BenchmarkError('official archive has an invalid layout')
        baseline = directory / 'baseline'
        baseline.mkdir()
        stage.stage(reference_phase, baseline, target.triple, version, root / 'licenses', root / 'NOTICE')
        def sizes(prefix: Path, compressed: int | str) -> dict:
            return {'executable': (prefix / 'bin/cmake').stat().st_size,
                    'files': sum(path.stat().st_size for path in prefix.rglob('*') if path.is_file() and not path.is_symlink()),
                    'archive': compressed}
        size_data = {'product': sizes(candidate, archive.stat().st_size), 'musl': sizes(baseline, 'not packaged'),
                     'kitware': sizes(official_entries[0], Cache(root / '.work/cache', offline=True).require(reference).stat().st_size)}
        runtime = directory / 'runtime'
        image = sandbox.image_tag(lock, target, root / 'docker/builder.Dockerfile')
        sandbox.copy_reference_runtime(image, target, runtime)
        names = ('fmt-source', 'zstd-source', 'libjpeg-turbo-source', 'llvm-project-source')
        input_cache = Cache(root / '.work/cache', offline=True)
        phase_cache = PhaseCache(phases)
        mounts = [(directory, '/benchmark'), (root / 'tests/benchmark', '/suite'),
                  (root / 'buildsys', '/controller/buildsys'),
                  (candidate, '/variants/product'), (baseline, '/variants/musl'),
                  (official_entries[0], '/variants/kitware'), (runtime, '/opt/alpine'),
                  (runtime / 'lib' / Path(target.musl_loader).name, target.musl_loader),
                  (runtime / 'etc' / f'ld-musl-{target.machine}.path', f'/etc/ld-musl-{target.machine}.path'),
                  (runtime / 'usr/make', '/usr/bin/make'),
                  (phases / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
                  (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
                  (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja')]
        for name in names:
            item = next(item for item in sources if item.name == name)
            source_archive = input_cache.require(item)
            source_phase = phase_cache.run(
                f'project-{name}', {'source': item.sha256, 'implementation': digest_bytes(root / 'buildsys/qualify.py')[0]},
                lambda output, source_archive=source_archive: safe_extract(source_archive, output / 'source'))
            source = source_phase.directory / 'source'
            mounts.append((source, f'/inputs/{name}'))
        runner_sha256 = digest_bytes(root / 'tests/benchmark/run.py')[0]
        implementation_sha256 = digest_bytes(Path(__file__))[0]
        result = sandbox.run_sealed(lock.reference_image, ['/opt/alpine/usr/python3', '/suite/run.py', str(repetitions)],
                                    target=target, mounts=mounts,
                                    env={'PYTHONHOME': '/opt/alpine/usr', 'TMPDIR': '/benchmark'},
                                    workdir='/benchmark', timeout=28800)
        if result.returncode:
            raise BenchmarkError(f'benchmark failed ({result.returncode}):\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}')
        if (digest_bytes(root / 'tests/benchmark/run.py')[0] != runner_sha256
            or digest_bytes(Path(__file__))[0] != implementation_sha256):
            raise BenchmarkError('benchmark implementation changed during measurement')
        data = json.loads((directory / 'results.json').read_text())
        document = render(data['records'], repetitions, {'target': target.triple, 'cpus': data['cpus'],
                                                         'archive_sha256': archive_sha256, 'profiles': data['profiles'],
                                                         'baseline_digest': reference_record['output_digest'],
                                                         'official_sha256': reference.sha256, 'sizes': size_data,
                                                         'strace_version': tracer_version, 'host': platform.platform(),
                                                         'container': lock.reference_image,
                                                         'projects': [locked[name] for name in names],
                                                         'runner_sha256': runner_sha256})
        _write_atomic(root / 'docs/performance.md', document, scratch)
        if repetitions >= 10:
            summary = summarize(data['records'], repetitions)
            metrics = {}
            for label, key in (('version_seconds', ('process', 'version', 'product')),
                               ('fmt_configure_seconds', ('fmt', 'initial', 'product'))):
                value = summary[key]
                spread = value['max_seconds'] - value['min_seconds']
                metrics[label] = {'value': value['median_seconds'], 'spread': spread,
                                  'allowed_regression': max(value['median_seconds'] * 0.03, spread * 2)}
            for label, value in (('executable_bytes', size_data['product']['executable']),
                                 ('unpacked_bytes', size_data['product']['files']),
                                 ('archive_bytes', size_data['product']['archive'])):
                metrics[label] = {'value': value, 'spread': 0, 'allowed_regression': value * 0.03}
            _write_atomic(root / 'release-budgets.json', json.dumps({'target': target.triple, 'archive_sha256': archive_sha256,
                                                                    'repetitions': repetitions, 'metrics': metrics}, indent=2, sort_keys=True) + '\n', scratch)
