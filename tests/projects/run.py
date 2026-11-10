from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

root = Path('/qualification')
cmake = root / 'relocated cmake/bin/cmake'
ctest = root / 'relocated cmake/bin/ctest'
work = root / 'real projects'
work.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)}


def run(command: list[str], *, cwd: Path = work, timeout: int = 1800) -> str:
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{command}: exit {result.returncode}\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}')
    return result.stdout + result.stderr


def source(name: str) -> Path:
    entries = list((Path('/inputs') / name).iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise RuntimeError(f'{name}: invalid source layout')
    return entries[0]


def configure(name: str, project: Path, *options: str) -> Path:
    build = work / name
    run([cmake, '-S', project, '-B', build, '-G', 'Ninja', '-DCMAKE_MAKE_PROGRAM=/tools/ninja',
         '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake', '-DCMAKE_BUILD_TYPE=Release', *options])
    return build


def test_fmt() -> str:
    fmt_source = work / 'fmt-source'
    if fmt_source.exists():
        shutil.rmtree(fmt_source)
    shutil.copytree(source('fmt-source'), fmt_source)
    run(['patch', '--batch', '--forward', '-p1', '-i', '/suite/fmt-missing-locale.patch'], cwd=fmt_source)
    build = configure('fmt', fmt_source, '-DFMT_TEST=ON', '-DFMT_DOC=OFF')
    run([cmake, '--build', build, '--parallel', '8'])
    report = run([ctest, '--test-dir', build, '--output-on-failure', '--parallel', '8', '--timeout', '120'])
    match = re.search(r'100% tests passed out of (\d+)', report)
    if not match or int(match.group(1)) == 0:
        raise RuntimeError(f'fmt ran no passing tests:\n{report}')
    locale = '' if env.get('MUSL_LOCPATH') else '; locale-specific assertions skipped without locale data'
    return f'fmt: built and passed {match.group(1)} tests{locale}'


def test_zstd() -> str:
    build = configure('zstd', source('zstd-source') / 'build/cmake', '-DZSTD_BUILD_PROGRAMS=ON', '-DZSTD_BUILD_SHARED=OFF')
    run([cmake, '--build', build, '--parallel', '8', '--target', 'zstd'])
    program = build / 'programs/zstd'
    payload = work / 'zstd-input'
    payload.write_bytes(b'locked real-project compression fixture\n' * 100)
    compressed = work / 'zstd-output.zst'
    restored = work / 'zstd-restored'
    run([program, '-f', payload, '-o', compressed])
    run([program, '-d', '-f', compressed, '-o', restored])
    if restored.read_bytes() != payload.read_bytes():
        raise RuntimeError('zstd round trip changed the payload')
    return 'zstd: built and passed a compression round trip'


def test_jpeg() -> str:
    build = configure('jpeg', source('libjpeg-turbo-source'), '-DWITH_SIMD=OFF', '-DENABLE_SHARED=OFF')
    run([cmake, '--build', build, '--parallel', '8', '--target', 'tjunittest-static'])
    report = run([build / 'tjunittest-static'], cwd=build, timeout=600)
    if 'Testing 8-bit precision' not in report or 'Done.' not in report:
        raise RuntimeError(f'tjunittest did not report exercised checks:\n{report[-6000:]}')
    return 'libjpeg-turbo: built and passed tjunittest'


def test_llvm() -> str:
    configure('llvm', source('llvm-project-source') / 'llvm', '-DLLVM_ENABLE_PROJECTS=clang')
    return 'LLVM with Clang: configured and generated'


failures = []
for test in (test_fmt, test_zstd, test_jpeg, test_llvm):
    try:
        print(test(), flush=True)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as error:
        failures.append(f'{test.__name__}: {error}')
        print(f'{test.__name__}: failed; continuing with other projects', flush=True)
if failures:
    raise RuntimeError('\n'.join(failures))
