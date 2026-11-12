"""Run basic acceptance against a relocated staged distribution."""

from __future__ import annotations

import difflib
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import sandbox, toolchain
from .inputs import Cache, digest_bytes, load_bootstrap, load_sources, safe_extract
from .phases import PhaseCache
from .targets import Target


class QualificationError(Exception):
    pass


def _write_section(root: Path, marker: str, content: str) -> None:
    report = root / 'docs/qualification.md'
    scratch = root / '.work/tmp'
    original = report.read_text()
    before, found, after = original.partition(marker)
    if found:
        _, separator, following = after.partition('\n## ')
        suffix = f'\n## {following}' if separator else ''
    else:
        before = original
        suffix = ''
    updated = before.rstrip() + '\n\n' + marker + '\n\n' + content.rstrip() + '\n' + suffix
    with tempfile.NamedTemporaryFile(mode='w', prefix='qualification-report-', dir=scratch, delete=False) as temporary_report:
        temporary_path = Path(temporary_report.name)
        try:
            temporary_report.write(updated)
            temporary_report.flush()
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    try:
        temporary_path.replace(report)
    finally:
        temporary_path.unlink(missing_ok=True)


def basic(*, root: Path, phase: Path, image: str, target: Target) -> None:
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    phases = root / '.work/build' / target.triple / 'phases'
    with tempfile.TemporaryDirectory(prefix='qualification-', dir=scratch) as temporary:
        qualification = Path(temporary)
        shutil.copytree(phase, qualification / 'relocated cmake', symlinks=True, ignore=shutil.ignore_patterns('phase.json', 'state.json'))
        result = sandbox.run_sealed(
            image, ['python3', '/suite/run.py'], target=target,
            mounts=[
                (qualification, '/qualification'),
                (qualification / 'relocated cmake', '/qualification/relocated cmake'),
                (root / 'tests/acceptance/basic', '/suite'),
                (phases / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
                (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
                (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja'),
            ],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1800,
            read_only=frozenset({'/qualification/relocated cmake', '/suite', f'/src/.work/build/{target.triple}/phases/prepare',
                                 '/tools/toolchain.cmake', '/tools/ninja'}),
        )
        print(result.stdout, end='')
        if result.returncode:
            raise QualificationError(f'basic qualification failed ({result.returncode}):\n{result.stderr}')


def network(*, root: Path, phase: Path, image: str, target: Target) -> None:
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    sources = {item.name: item for item in load_sources(root / 'sources.lock.json') if item.target in ('all', target.triple)}
    openssl = sources.get(f'openssl-test-{target.machine}')
    cmake_source = sources.get('cmake-source')
    if openssl is None or cmake_source is None:
        raise QualificationError('network qualification inputs are missing from the lock')
    with tempfile.TemporaryDirectory(prefix='network-qualification-', dir=scratch) as temporary:
        directory = Path(temporary)
        qualification = directory / 'qualification'
        qualification.mkdir()
        shutil.copytree(phase, qualification / 'relocated cmake', symlinks=True,
                        ignore=shutil.ignore_patterns('phase.json', 'state.json'))
        tools = safe_extract(Cache(root / '.work/cache', offline=True).require(openssl), directory / 'openssl')
        suite = root / 'tests/acceptance/network'
        local = sandbox.run_sealed(
            image, ['python3', '/suite/run.py'], target=target,
            mounts=[(qualification, '/qualification'), (qualification / 'relocated cmake', '/qualification/relocated cmake'),
                    (suite, '/suite'), (tools / 'usr/bin/openssl', '/tools/openssl')],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1800,
            read_only=frozenset({'/qualification/relocated cmake', '/suite', '/tools/openssl'}),
        )
        print(local.stdout, end='')
        if local.returncode or 'local HTTPS qualification: 11 cases passed' not in local.stdout:
            raise QualificationError(f'local network qualification failed ({local.returncode}):\n{local.stderr}')
        internet = sandbox.run_networked(
            image, ['python3', '/suite/run.py', cmake_source.url, cmake_source.sha256], target=target,
            mounts=[(qualification, '/qualification'), (qualification / 'relocated cmake', '/qualification/relocated cmake'),
                    (suite / 'internet', '/suite')],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1200,
            read_only=frozenset({'/qualification/relocated cmake', '/suite'}),
        )
        print(internet.stdout, end='')
        if internet.returncode:
            raise QualificationError(f'internet network qualification failed ({internet.returncode}):\n{internet.stderr}')
        if 'skipped: no network' in internet.stdout:
            raise QualificationError('internet network qualification skipped: no network')
        if 'internet FetchContent: locked CMake source downloaded and verified' not in internet.stdout:
            raise QualificationError('internet network qualification produced no result')


def projects(*, root: Path, phase: Path, image: str, target: Target) -> None:
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    phase_root = root / '.work/build' / target.triple / 'phases'
    cache = Cache(root / '.work/cache', offline=True)
    sources = {item.name: item for item in load_sources(root / 'sources.lock.json') if item.target in ('all', target.triple)}
    names = ('fmt-source', 'zstd-source', 'libjpeg-turbo-source', 'llvm-project-source')
    phases = PhaseCache(phase_root)
    inputs = []
    for name in names:
        item = sources.get(name)
        if item is None:
            raise QualificationError(f'project source {name} is missing from the lock')
        archive = cache.require(item)
        result = phases.run(f'project-{name}', {'source': item.sha256, 'implementation': digest_bytes(Path(__file__))[0]},
                            lambda directory, archive=archive: safe_extract(archive, directory / 'source'))
        inputs.append((result.directory / 'source', f'/inputs/{name}'))
    with tempfile.TemporaryDirectory(prefix='project-qualification-', dir=scratch) as temporary:
        qualification = Path(temporary)
        prefix = qualification / 'relocated cmake'
        shutil.copytree(phase, prefix, symlinks=True, ignore=shutil.ignore_patterns('phase.json', 'state.json'))
        result = sandbox.run_sealed(
            image, ['python3', '/suite/run.py'], target=target,
            mounts=[(qualification, '/qualification'), (prefix, '/qualification/relocated cmake'),
                    (root / 'tests/projects', '/suite'), *inputs,
                    (phase_root / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
                    (phase_root / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
                    (phase_root / 'bootstrap/ninja-build/ninja', '/tools/ninja')],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=7200,
            read_only=frozenset({'/qualification/relocated cmake', '/suite', f'/src/.work/build/{target.triple}/phases/prepare',
                                 '/tools/toolchain.cmake', '/tools/ninja', *(destination for _, destination in inputs)}),
        )
        print(result.stdout, end='')
        if result.returncode:
            raise QualificationError(f'real project qualification failed ({result.returncode}):\n{result.stderr}')
        for marker in ('fmt: built and passed ', 'zstd: built and passed ',
                       'libjpeg-turbo: built and passed ', 'LLVM with Clang: configured and generated'):
            if marker not in result.stdout:
                raise QualificationError(f'real project qualification missing result: {marker}')


def _junit(report: Path) -> dict[str, str]:
    expression = ('[.[] | select(type == "object" and .t == "testsuite") | .c[] | '
                  'select(type == "object" and .t == "testcase") | {name: .a.name, status: .a.status}]')
    try:
        result = subprocess.run(['jaq', '--from', 'xml', '--slurp', expression, str(report)],
                                text=True, capture_output=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise QualificationError(f'cannot run jaq for upstream report: {error}') from error
    if result.returncode:
        raise QualificationError(f'cannot parse upstream report: {result.stderr}')
    try:
        cases = json.loads(result.stdout)
        names = {item['name']: item['status'] for item in cases}
    except (ValueError, TypeError, KeyError) as error:
        raise QualificationError('upstream report has invalid test cases') from error
    if not names or len(names) != len(cases) or any(status not in ('run', 'fail') for status in names.values()):
        raise QualificationError('upstream report is empty, duplicated, or contains skipped tests')
    return names


def _check_baseline_failures(failures: set[str], baseline: dict[str, str]) -> None:
    baseline_failures = {name for name, status in baseline.items() if status == 'fail'}
    if set(baseline) != failures or baseline_failures != failures:
        raise QualificationError(f'candidate-only upstream failures: {sorted(failures - baseline_failures)}')


def upstream(*, root: Path, phase: Path, image: str, target: Target) -> None:
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    phases = root / '.work/build' / target.triple / 'phases'
    executable_digest = digest_bytes(phase / 'bin/cmake')[0]
    with tempfile.TemporaryDirectory(prefix='upstream-qualification-', dir=scratch) as temporary:
        directory = Path(temporary)
        base = Path('/src/.work/build') / target.triple / 'phases/prepare'
        env = {**toolchain.environment(base / 'toolchain', target),
               'CFLAGS': shlex.join(toolchain.flags(target, base / 'sysroot')),
               'CXXFLAGS': shlex.join(toolchain.cxx_flags(target, base / 'sysroot')),
               'PATH': f'{base}/toolchain/bin:/src/.work/build/{target.triple}/phases/bootstrap/ninja-build:/usr/bin:/bin',
               'CMAKE_BUILD_PARALLEL_LEVEL': '8', 'TMPDIR': '/qualification/tmp'}

        def run_phase(name: str, selection: Path) -> dict[str, str]:
            copied = directory / f'{name}-phase'
            shutil.copytree(phases / name, copied, symlinks=True)
            if name == 'cmake':
                shutil.copy2(phase / 'bin/cmake', copied / 'build/bin/cmake')
                if digest_bytes(copied / 'build/bin/cmake')[0] != executable_digest:
                    raise QualificationError('upstream test executable differs from the candidate')
            results = directory / f'{name}-results'
            results.mkdir()
            (results / 'tmp').mkdir()
            mounts = [(results, '/qualification'), (copied, f'/src/.work/build/{target.triple}/phases/{name}'),
                      (phases / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
                      (phases / 'bootstrap', f'/src/.work/build/{target.triple}/phases/bootstrap'),
                      (root / '.work/rust' / target.triple / 'phases/staticlib', f'/src/.work/rust/{target.triple}/phases/staticlib'),
                      (root / 'tests/projects', '/suite'), (selection, '/selection/upstream-subset.txt')]
            if name == 'cmake':
                mounts.append((phase / 'bin/cmake', f'/src/.work/build/{target.triple}/phases/{name}/build/bin/cmake'))
            result = sandbox.run_sealed(image, ['python3', '/suite/upstream.py'], target=target, mounts=mounts,
                                        env={**env, 'UPSTREAM_PHASE': name}, workdir='/qualification', timeout=1260,
                                        read_only=frozenset(destination for _, destination in mounts
                                                            if destination not in ('/qualification', f'/src/.work/build/{target.triple}/phases/{name}')))
            print(result.stdout, end='')
            report = results / 'upstream.xml'
            if 'upstream subset:' not in result.stdout or not report.is_file():
                raise QualificationError(f'{name} upstream subset produced no report:\n{result.stderr}')
            cases = _junit(report)
            failed = {case for case, status in cases.items() if status == 'fail'}
            if result.returncode != (1 if failed else 0):
                raise QualificationError(f'{name} upstream result disagrees with its report:\n{result.stderr}')
            return cases

        candidate = run_phase('cmake', root / 'tests/upstream-subset.txt')
        failures = {name for name, status in candidate.items() if status == 'fail'}
        if failures:
            selection = directory / 'reference-selection.txt'
            selection.write_text(''.join(f'^{re.escape(name)}$\n' for name in sorted(failures)))
            baseline = run_phase('reference', selection)
            _check_baseline_failures(failures, baseline)
        marker = f'## Latest upstream subset: {target.triple}'
        summary = [f'Executable SHA-256: `{executable_digest}`.',
                   f'Executed {len(candidate)} tests. {len(candidate) - len(failures)} passed.']
        if failures:
            summary.append('The following failures also occurred in the unmodified static-PIE baseline:')
            summary.extend(f'- `{name}`' for name in sorted(failures))
        else:
            summary.append('No failures were observed.')
        _write_section(root, marker, '\n\n'.join(summary))
        print(f'upstream: {len(candidate)} tests, {len(failures)} shared baseline failures\n')


def parity(*, root: Path, phase: Path, image: str, target: Target) -> None:
    scratch = root / '.work/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    lock = load_bootstrap(root / 'bootstrap.lock.json')
    sources = load_sources(root / 'sources.lock.json')
    reference = next((item for item in sources if item.name == f'cmake-reference-{target.machine}'), None)
    if reference is None:
        raise QualificationError('reference CMake is missing from the source lock')
    phases = root / '.work/build' / target.triple / 'phases'
    with tempfile.TemporaryDirectory(prefix='parity-qualification-', dir=scratch) as temporary:
        directory = Path(temporary)
        candidate = directory / 'candidate'
        baseline = directory / 'reference'
        candidate.mkdir()
        baseline.mkdir()
        shutil.copytree(phase, candidate / 'relocated cmake', symlinks=True,
                        ignore=shutil.ignore_patterns('phase.json', 'state.json'))
        extracted = safe_extract(Cache(root / '.work/cache', offline=True).require(reference), directory / 'reference-source')
        entries = list(extracted.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise QualificationError('reference CMake archive has an invalid layout')
        runtime = directory / 'runtime'
        sandbox.copy_reference_runtime(image, target, runtime)
        common = [
            (phases / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
            (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
            (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja'),
        ]
        runtime_mounts = [
            (runtime, '/opt/alpine'),
            (runtime / 'lib' / Path(target.musl_loader).name, target.musl_loader),
            (runtime / 'etc' / f'ld-musl-{target.machine}.path', f'/etc/ld-musl-{target.machine}.path'),
            (runtime / 'usr/make', '/usr/bin/make'),
        ]
        for suite in ('graph', 'archive'):
            fixture = root / 'tests/acceptance' / suite
            for label, image_name, location, prefix, interpreter, extra in (
                ('candidate', image, candidate, None, 'python3', []),
                ('reference', lock.reference_image, baseline, entries[0], '/opt/alpine/usr/python3', runtime_mounts),
            ):
                mounts = [(location, '/qualification'), (fixture, '/suite'), *common, *extra]
                mounts.append((prefix if prefix is not None else location / 'relocated cmake',
                               '/qualification/relocated cmake'))
                env = {'TMPDIR': '/qualification'}
                if label == 'reference':
                    env['PYTHONHOME'] = '/opt/alpine/usr'
                result = sandbox.run_sealed(image_name, [interpreter, '/suite/run.py'], target=target,
                                            mounts=mounts, env=env, workdir='/qualification', timeout=3600,
                                            read_only=frozenset(destination for _, destination in mounts if destination != '/qualification'))
                print(f'{label} {suite}: {result.stdout}', end='')
                if result.returncode or 'qualification:' not in result.stdout:
                    raise QualificationError(f'{label} {suite} qualification failed ({result.returncode}):\n{result.stderr}')
        files = ('ninja build/build.ninja', 'ninja-file-api.json', 'make-file-api.json', 'system-information-subset.txt')
        differences = []
        for name in files:
            before = (baseline / 'graph suite' / name).read_text().splitlines(keepends=True)
            after = (candidate / 'graph suite' / name).read_text().splitlines(keepends=True)
            diff = ''.join(difflib.unified_diff(before, after, fromfile=f'reference/{name}', tofile=f'candidate/{name}'))
            if diff:
                differences.append((name, diff))
        marker = f'## Latest automated parity differences: {target.triple}'
        sections = []
        for name, diff in differences:
            lines = [line if line != ' ' else '' for line in diff.rstrip().split('\n')]
            sections.extend([f'### {name}', '', '```diff', '\n'.join(lines), '```', ''])
        if not differences:
            sections.extend(['No differences were observed in the compared outputs.', ''])
        _write_section(root, marker, '\n'.join(sections))
        print(f'parity: compared {len(files)} outputs; {len(differences)} differ and are recorded in {root / "docs/qualification.md"}\n')
