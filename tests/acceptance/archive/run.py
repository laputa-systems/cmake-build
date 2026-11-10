from __future__ import annotations

import os
import subprocess
from pathlib import Path

root = Path('/qualification')
cmake = root / 'relocated cmake/bin/cmake'
work = root / 'archive suite'
work.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)}
payload = work / 'payload'
payload.mkdir()
(payload / 'message.txt').write_text('CMake archive parity\n')


def run(*args: str, cwd: Path = work) -> None:
    result = subprocess.run([str(cmake), *map(str, args)], cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')


def check(directory: Path) -> None:
    if (directory / 'payload/message.txt').read_text() != 'CMake archive parity\n':
        raise RuntimeError(f'archive content differs in {directory}')


for name, flags, extra, format_name, compression in [
    ('gzip', 'czf', [], 'gnutar', 'GZip'),
    ('xz', 'cJf', [], 'gnutar', 'XZ'),
    ('bzip2', 'cjf', [], 'gnutar', 'BZip2'),
    ('zstd', 'cf', ['--zstd'], 'gnutar', 'Zstd'),
    ('zip', 'cf', ['--format=zip'], 'zip', None),
]:
    archive = work / f'command-{name}.archive'
    run('-E', 'tar', flags, archive, *extra, 'payload')
    extracted = work / f'command-{name}'
    extracted.mkdir()
    run('-E', 'tar', 'xf', archive, cwd=extracted)
    check(extracted)
    file_archive = work / f'file-{name}.archive'
    file_extracted = work / f'file-{name}'
    script = work / f'{name}.cmake'
    compression_option = f' COMPRESSION {compression}' if compression else ''
    script.write_text(f'file(ARCHIVE_CREATE OUTPUT "{file_archive}" PATHS "payload" FORMAT {format_name}{compression_option} WORKING_DIRECTORY "{work}")\n'
                      f'file(ARCHIVE_EXTRACT INPUT "{file_archive}" DESTINATION "{file_extracted}")\n')
    run('-P', script)
    check(file_extracted)
print('archive qualification: command and file create/extract passed for gzip, xz, bzip2, zstd, and zip')
