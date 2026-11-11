"""Stage CMake tools and their relocatable resources."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


class StageError(Exception):
    pass


def stage(cmake_phase: Path, directory: Path, target: str, version: str, licenses: Path, notice: Path) -> None:
    source = cmake_phase / 'source'
    binary = directory / 'bin'
    binary.mkdir()
    for name in ('cmake', 'ctest', 'cpack'):
        executable = cmake_phase / 'build/bin' / name
        if not executable.is_file():
            raise StageError(f'built {name} executable is missing')
        shutil.copy2(executable, binary / name)
    resources = directory / 'share' / f'cmake-{version.rsplit(".", 1)[0]}'
    resources.mkdir(parents=True)
    (resources.parent / 'cmake').symlink_to(resources.name, target_is_directory=True)
    for name in ('Help', 'Modules', 'Templates'):
        shutil.copytree(source / name, resources / name, symlinks=True)
    notices = directory / 'share/doc/cmake-build'
    notices.mkdir(parents=True)
    for name in ('LICENSE.rst', 'CONTRIBUTORS.rst'):
        shutil.copy2(source / name, notices / name)
    shutil.copy2(notice, notices / 'NOTICE')
    shutil.copytree(licenses, notices / 'licenses', symlinks=True)
    (notices / 'artifact.json').write_text(json.dumps({
        'cmake_version': version, 'target': target, 'qualification': 'pending',
    }, indent=2, sort_keys=True) + '\n')
