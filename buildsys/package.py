from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


class PackageError(Exception):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def create(stage: Path, destination: Path, metadata: dict, epoch: int) -> None:
    if stage.is_symlink() or not stage.is_dir():
        raise PackageError('staging directory is missing or a symlink')
    if not isinstance(epoch, int) or epoch < 0:
        raise PackageError('invalid source date epoch')
    artifact_name = 'usr/share/doc/cmake-build/artifact.json'
    entries = {'usr': ('directory', 0o755, None)}
    pending = [(stage, 'usr')]
    while pending:
        directory, prefix = pending.pop()
        for path in sorted(directory.iterdir(), key=lambda value: value.name):
            name = f'{prefix}/{path.name}'
            if name == artifact_name or (prefix == 'usr' and path.name in {'phase.json', 'state.json'}):
                continue
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                entries[name] = ('directory', 0o755, None)
                pending.append((path, name))
            elif stat.S_ISREG(mode):
                entries[name] = ('file', 0o755 if mode & 0o111 else 0o644, path.read_bytes())
            elif stat.S_ISLNK(mode):
                target = os.readlink(path)
                _safe_link(name, target)
                entries[name] = ('symlink', 0o777, target)
            else:
                raise PackageError(f'unsupported file type: {name}')
    for parent in ('usr/share', 'usr/share/doc', 'usr/share/doc/cmake-build'):
        if parent in entries and entries[parent][0] != 'directory':
            raise PackageError(f'artifact parent is not a directory: {parent}')
        entries.setdefault(parent, ('directory', 0o755, None))
    files = {}
    for name, (kind, mode, data) in sorted(entries.items()):
        item = {'type': kind, 'mode': mode}
        if kind == 'file':
            item['size'] = len(data)
            item['sha256'] = hashlib.sha256(data).hexdigest()
        elif kind == 'symlink':
            item['target'] = data
        files[name] = item
    if 'files' in metadata:
        raise PackageError('metadata must not supply its own file inventory')
    content = json.dumps({**metadata, 'files': files}, sort_keys=True, indent=2).encode() + b'\n'
    entries[artifact_name] = ('file', 0o644, content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.package-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            with tarfile.open(fileobj=output, mode='w:xz', format=tarfile.PAX_FORMAT, preset=6) as archive:
                for name, (kind, mode, data) in sorted(entries.items()):
                    info = tarfile.TarInfo(name)
                    info.mode = mode
                    info.mtime = epoch
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    if kind == 'directory':
                        info.type = tarfile.DIRTYPE
                    elif kind == 'symlink':
                        info.type = tarfile.SYMTYPE
                        info.linkname = data
                    else:
                        info.size = len(data)
                    archive.addfile(info, io.BytesIO(data) if kind == 'file' else None)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def inspect(archive_path: Path) -> dict:
    artifact_name = 'usr/share/doc/cmake-build/artifact.json'
    actual = {}
    artifact = None
    try:
        with tarfile.open(archive_path, 'r:xz') as archive:
            for member in archive:
                name = member.name
                parts = PurePosixPath(name).parts
                if not parts or parts[0] != 'usr' or '..' in parts or name.startswith('/') or name in actual or name == artifact_name and artifact is not None:
                    raise PackageError(f'invalid or duplicate archive member: {name}')
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
                    if name == artifact_name:
                        artifact = json.loads(content)
                        continue
                    item = {'type': 'file', 'mode': member.mode, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                else:
                    raise PackageError(f'unsupported archive member: {name}')
                actual[name] = item
    except (tarfile.TarError, OSError, ValueError, UnicodeError) as error:
        raise PackageError(f'invalid package: {error}') from error
    if not isinstance(artifact, dict) or artifact.get('files') != actual:
        raise PackageError('package inventory does not match its contents')
    return artifact
