"""Run basic acceptance against a relocated staged distribution."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import sandbox
from .inputs import Cache, load_sources, safe_extract
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
