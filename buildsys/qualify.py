"""Run basic acceptance against a relocated staged distribution."""

from __future__ import annotations

import shutil
import tempfile
import difflib
from pathlib import Path

from . import sandbox
from .inputs import Cache, load_bootstrap, load_sources, safe_extract
from .targets import Target


class QualificationError(Exception):
    pass


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
                (root / 'tests/acceptance/basic', '/suite'),
                (phases / 'prepare', f'/src/.work/build/{target.triple}/phases/prepare'),
                (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
                (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja'),
            ],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1800,
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
            mounts=[(qualification, '/qualification'), (suite, '/suite'), (tools / 'usr/bin/openssl', '/tools/openssl')],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1800,
        )
        print(local.stdout, end='')
        if local.returncode or 'local HTTPS qualification: 11 cases passed' not in local.stdout:
            raise QualificationError(f'local network qualification failed ({local.returncode}):\n{local.stderr}')
        internet = sandbox.run_networked(
            image, ['python3', '/suite/run.py', cmake_source.url, cmake_source.sha256], target=target,
            mounts=[(qualification, '/qualification'), (suite / 'internet', '/suite')],
            env={'TMPDIR': '/qualification'}, workdir='/qualification', timeout=1200,
        )
        print(internet.stdout, end='')
        if internet.returncode:
            raise QualificationError(f'internet network qualification failed ({internet.returncode}):\n{internet.stderr}')
        if 'skipped: no network' in internet.stdout:
            raise QualificationError('internet network qualification skipped: no network')
        if 'internet FetchContent: locked CMake source downloaded and verified' not in internet.stdout:
            raise QualificationError('internet network qualification produced no result')


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
                if prefix is not None:
                    mounts.append((prefix, '/qualification/relocated cmake'))
                env = {'TMPDIR': '/qualification'}
                if label == 'reference':
                    env['PYTHONHOME'] = '/opt/alpine/usr'
                result = sandbox.run_sealed(image_name, [interpreter, '/suite/run.py'], target=target,
                                            mounts=mounts, env=env, workdir='/qualification', timeout=3600)
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
        report = root / 'docs/qualification.md'
        marker = f'## Latest automated parity differences: {target.triple}'
        original = report.read_text()
        before, found, after = original.partition(marker)
        if found:
            _, separator, following = after.partition('\n## ')
            suffix = f'\n## {following}' if separator else ''
        else:
            before = original
            suffix = ''
        sections = [before.rstrip(), '', marker, '']
        for name, diff in differences:
            lines = [line if line != ' ' else '' for line in diff.rstrip().split('\n')]
            sections.extend([f'### {name}', '', '```diff', '\n'.join(lines), '```', ''])
        if not differences:
            sections.extend(['No differences were observed in the compared outputs.', ''])
        content = '\n'.join(sections).rstrip() + '\n' + suffix
        with tempfile.NamedTemporaryFile(mode='w', prefix='parity-report-', dir=scratch, delete=False) as temporary_report:
            temporary_path = Path(temporary_report.name)
            try:
                temporary_report.write(content)
                temporary_report.flush()
            except BaseException:
                temporary_path.unlink(missing_ok=True)
                raise
        try:
            temporary_path.replace(report)
        finally:
            temporary_path.unlink(missing_ok=True)
        print(f'parity: compared {len(files)} outputs; {len(differences)} differ and are recorded in {report}\n')
