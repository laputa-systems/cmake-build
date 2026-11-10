"""Build unmodified CMake for upstream-test comparison."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import toolchain
from .rust import _run
from .targets import Target


class ReferenceError(Exception):
    pass


def build(*, bootstrap: Path, prepared: Path, directory: Path, target: Target, version: str) -> None:
    entries = list((bootstrap / 'source').iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise ReferenceError('reference source has an invalid layout')
    source = directory / 'source'
    shutil.copytree(entries[0], source, symlinks=True)
    tc = prepared / 'toolchain'
    ninja = bootstrap / 'ninja-build/ninja'
    env = {key: value for key, value in os.environ.items() if key not in {'CFLAGS', 'CXXFLAGS', 'LDFLAGS'}}
    env.update(toolchain.environment(tc, target))
    build_tree = directory / 'build'
    _run(['/usr/bin/cmake', '-S', str(source), '-B', str(build_tree), '-G', 'Ninja',
          f'-DCMAKE_MAKE_PROGRAM={ninja}', f'-DCMAKE_TOOLCHAIN_FILE={bootstrap / "toolchain.cmake"}',
          '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_USE_OPENSSL=OFF', '-DBUILD_CursesDialog=OFF',
          '-DBUILD_QtDialog=OFF', '-DCMAKE_USE_SYSTEM_LIBRARIES=OFF', '-DCMake_ENABLE_DEBUGGER=ON'],
         cwd=directory, env=env)
    _run([str(ninja), '-C', str(build_tree), f'-j{os.process_cpu_count() or 1}'], cwd=directory, env=env)
    output = _run([str(build_tree / 'bin/cmake'), '--version'], cwd=directory, env=env)
    if not output.splitlines() or output.splitlines()[0] != f'cmake version {version}':
        raise ReferenceError(f'unmodified reference does not report CMake {version}')
