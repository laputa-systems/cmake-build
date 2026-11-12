from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from buildlib.hashing import digest_file

from .inputs import safe_extract


class ReproduceError(Exception):
    pass


def _entries(root: Path) -> dict[str, Path]:
    result = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            result[path.relative_to(root).as_posix()] = path
            if path.is_dir() and not path.is_symlink():
                pending.append(path)
    return result


def compare_trees(first: Path, second: Path) -> list[str]:
    left = _entries(first)
    right = _entries(second)
    differences = []
    for name in sorted(left.keys() | right.keys()):
        if name not in left:
            differences.append(f'{name}: missing from first build')
            continue
        if name not in right:
            differences.append(f'{name}: missing from second build')
            continue
        before, after = left[name], right[name]
        a, b = before.lstat().st_mode, after.lstat().st_mode
        if stat.S_IFMT(a) != stat.S_IFMT(b):
            differences.append(f'{name}: type differs')
        elif stat.S_IMODE(a) != stat.S_IMODE(b):
            differences.append(f'{name}: mode differs')
        elif stat.S_ISLNK(a) and os.readlink(before) != os.readlink(after):
            differences.append(f'{name}: symlink target differs')
        elif stat.S_ISREG(a) and digest_file(before)[0] != digest_file(after)[0]:
            differences.append(f'{name}: content differs')
        elif not (stat.S_ISLNK(a) or stat.S_ISREG(a) or stat.S_ISDIR(a)):
            differences.append(f'{name}: unsupported file type')
    return differences


def run(root: Path, target: str, version: str, commit: str) -> list[str]:
    work = root / '.work'
    worktrees = work / 'wt'
    worktrees.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reproduce-', dir=worktrees) as temporary:
        scratch = Path(temporary)
        trees = []
        archives = []
        created = []
        try:
            for index in (1, 2):
                checkout = scratch / f'build-{index}'
                result = subprocess.run(['git', 'worktree', 'add', '--detach', str(checkout), commit], cwd=root, check=False)
                if result.returncode:
                    raise ReproduceError(f'cannot create clean build worktree {checkout}')
                created.append(checkout)
                local = checkout / '.work'
                (local / 'tmp').mkdir(parents=True)
                shutil.copytree(work / 'cache', local / 'cache', symlinks=True, copy_function=os.link)
                for name in ('tools', 'vendor'):
                    source = work / 'rust' / target / 'phases' / name
                    destination = local / 'rust' / target / 'phases' / name
                    shutil.copytree(source, destination, symlinks=True, copy_function=os.link)
                env = {**os.environ, 'TMPDIR': str(local / 'tmp')}
                result = subprocess.run([sys.executable, 'build.py', 'package', '--target', target], cwd=checkout, env=env, check=False)
                if result.returncode:
                    raise ReproduceError(f'clean build {index} failed ({result.returncode})')
                archive = local / 'artifacts' / target / f'cmake-{version}-{target}.tar.xz'
                unpacked = safe_extract(archive, scratch / f'unpacked-{index}')
                trees.append(unpacked)
                archives.append(archive)
            differences = compare_trees(*trees)
            if digest_file(archives[0])[0] != digest_file(archives[1])[0]:
                differences.append('archive bytes differ')
            for index, tree in enumerate(trees, 1):
                executable = tree / 'usr/bin/cmake'
                if str(created[index - 1]).encode() in executable.read_bytes():
                    differences.append(f'build {index}: executable contains its checkout path')
            return differences
        finally:
            for checkout in reversed(created):
                result = subprocess.run(['git', 'worktree', 'remove', '--force', str(checkout)], cwd=root, check=False)
                if result.returncode:
                    raise ReproduceError(f'could not remove reproduction worktree {checkout}')
