"""Run basic acceptance against a relocated staged distribution."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import sandbox
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
