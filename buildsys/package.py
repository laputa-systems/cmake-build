from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Literal, TypedDict, TypeGuard

from buildlib import release
from buildlib.hashing import digest_file

ARTIFACT = 'usr/share/doc/cmake-build/artifact.json'


class PackageError(Exception):
    pass


class _DirectoryEntry(TypedDict):
    type: Literal['directory']
    mode: int


class _FileEntry(TypedDict):
    type: Literal['file']
    mode: int
    size: int
    sha256: str


class _SymlinkEntry(TypedDict):
    type: Literal['symlink']
    mode: int
    target: str


type _InventoryEntry = _DirectoryEntry | _FileEntry | _SymlinkEntry


def _safe_link(name: str, target: str) -> None:
    if not target or PurePosixPath(target).is_absolute():
        raise PackageError(f'unsafe symlink {name}: {target}')
    depth = len(PurePosixPath(name).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == '..':
            depth -= 1
            if depth < 1:
                raise PackageError(f'escaping symlink {name}: {target}')
        elif part != '.':
            depth += 1


def _materialize(stage: Path, tree: Path) -> dict[str, _InventoryEntry]:
    files: dict[str, _InventoryEntry] = {'usr': {'type': 'directory', 'mode': 0o755}}
    pending = [(stage, tree, 'usr')]
    while pending:
        directory, copy, prefix = pending.pop()
        for path in sorted(directory.iterdir(), key=lambda value: value.name):
            name = f'{prefix}/{path.name}'
            if name == ARTIFACT or (prefix == 'usr' and path.name in {'phase.json', 'state.json'}):
                continue
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                files[name] = {'type': 'directory', 'mode': 0o755}
                (copy / path.name).mkdir()
                pending.append((path, copy / path.name, name))
            elif stat.S_ISREG(mode):
                shutil.copy2(path, copy / path.name)
                sha256, size = digest_file(copy / path.name)
                files[name] = {'type': 'file', 'mode': 0o755 if mode & 0o111 else 0o644, 'size': size, 'sha256': sha256}
            elif stat.S_ISLNK(mode):
                target = os.readlink(path)
                _safe_link(name, target)
                os.symlink(target, copy / path.name)
                files[name] = {'type': 'symlink', 'mode': 0o777, 'target': target}
            else:
                raise PackageError(f'unsupported file type: {name}')
    for parent in ('usr/share', 'usr/share/doc', 'usr/share/doc/cmake-build'):
        if parent in files and files[parent]['type'] != 'directory':
            raise PackageError(f'artifact parent is not a directory: {parent}')
        files.setdefault(parent, {'type': 'directory', 'mode': 0o755})
    (tree / ARTIFACT.removeprefix('usr/')).parent.mkdir(parents=True, exist_ok=True)
    return dict(sorted(files.items()))


def create(stage: Path, destination: Path, metadata: Mapping[str, object], epoch: int) -> None:
    if stage.is_symlink() or not stage.is_dir():
        raise PackageError('staging directory is missing or a symlink')
    if 'files' in metadata:
        raise PackageError('metadata must not supply its own file inventory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.package-', dir=destination.parent) as scratch:
        tree = Path(scratch)
        files = _materialize(stage, tree)
        content = json.dumps({**metadata, 'files': files}, sort_keys=True, indent=2).encode() + b'\n'
        (tree / ARTIFACT.removeprefix('usr/')).write_bytes(content)
        try:
            release.create_archive(tree, destination, mtime=epoch, prefix='usr')
        except release.ReleaseError as error:
            raise PackageError(str(error)) from error


def _is_metadata(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _matches_inventory(declared: object, actual: dict[str, _InventoryEntry]) -> bool:
    if not isinstance(declared, dict) or declared != actual:
        return False
    # Python compares booleans and floats equal to some integers.
    return all(
        type(entry['mode']) is int and (entry['type'] != 'file' or type(entry['size']) is int)
        for entry in declared.values()
    )


def inspect(archive_path: Path) -> dict[str, object]:
    actual: dict[str, _InventoryEntry] = {}
    artifact: dict[str, object] | None = None
    try:
        with tarfile.open(archive_path, 'r:xz') as archive:
            for member in archive:
                name = member.name
                parts = PurePosixPath(name).parts
                if not parts or parts[0] != 'usr' or '..' in parts or name.startswith('/') or name in actual or name == ARTIFACT and artifact is not None:
                    raise PackageError(f'invalid or duplicate archive member: {name}')
                item: _InventoryEntry
                if member.isdir():
                    item = {'type': 'directory', 'mode': member.mode}
                elif member.issym():
                    _safe_link(name, member.linkname)
                    item = {'type': 'symlink', 'mode': member.mode, 'target': member.linkname}
                elif member.isfile():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise PackageError(f'missing archive data: {name}')
                    content = stream.read()
                    if name == ARTIFACT:
                        decoded: object = json.loads(content)
                        if not _is_metadata(decoded):
                            raise PackageError('package inventory does not match its contents')
                        artifact = decoded
                        continue
                    item = {'type': 'file', 'mode': member.mode, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                else:
                    raise PackageError(f'unsupported archive member: {name}')
                actual[name] = item
    except (tarfile.TarError, OSError, ValueError, UnicodeError) as error:
        raise PackageError(f'invalid package: {error}') from error
    if artifact is None or not _matches_inventory(artifact.get('files'), actual):
        raise PackageError('package inventory does not match its contents')
    return artifact
