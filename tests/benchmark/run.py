from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, '/controller')
from buildsys.benchmark import interleaved_orders

root = Path('/benchmark')
repetitions = int(sys.argv[1])
variants = ('product', 'musl', 'kitware')
cpus = sorted(os.sched_getaffinity(0))[:4]
os.sched_setaffinity(0, cpus)
records = []
profiles = []
base_env = {**os.environ, 'PATH': '/usr/bin:/bin', 'HOME': str(root), 'TMPDIR': str(root)}
workloads = {
    'fmt': ('fmt-source', '', ['-DFMT_TEST=OFF', '-DFMT_DOC=OFF']),
    'zstd': ('zstd-source', 'build/cmake', ['-DZSTD_BUILD_PROGRAMS=ON', '-DZSTD_BUILD_SHARED=OFF']),
    'libjpeg-turbo': ('libjpeg-turbo-source', '', ['-DWITH_SIMD=OFF', '-DENABLE_SHARED=OFF']),
    'llvm-clang': ('llvm-project-source', 'llvm', ['-DLLVM_ENABLE_PROJECTS=clang', '-DPython3_EXECUTABLE=/opt/alpine/usr/python3']),
}


def invoke(command: list[str], workload: str, scenario: str, variant: str, iteration: int, measured: bool = True) -> str:
    output = root / 'output.txt'
    before = os.getloadavg()[0]
    with output.open('wb') as stream:
        started = time.perf_counter()
        process = subprocess.Popen(command, cwd=root, env=base_env, stdout=stream, stderr=subprocess.STDOUT)
        try:
            _, status, usage = os.wait4(process.pid, 0)
        except BaseException:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.wait()
            raise
        duration = time.perf_counter() - started
        process.returncode = os.waitstatus_to_exitcode(status)
    text = output.read_text(errors='replace')
    if process.returncode != 0:
        raise RuntimeError(f'{variant} {workload} {scenario} failed ({process.returncode}):\n{text[-6000:]}')
    if measured:
        records.append({'variant': variant, 'workload': workload, 'scenario': scenario, 'iteration': iteration,
                        'seconds': duration, 'max_rss_kib': usage.ru_maxrss, 'exit_code': process.returncode,
                        'cpu_seconds': usage.ru_utime + usage.ru_stime,
                        'load_before': before, 'load_after': os.getloadavg()[0]})
    return text


def verify_graph(build: Path, workload: str, variant: str, iteration: int) -> None:
    if not (build / 'build.ninja').is_file() or not (build / 'CMakeCache.txt').is_file():
        raise RuntimeError(f'{variant} {workload}: missing generated graph')
    targets = invoke(['/tools/ninja', '-C', str(build), '-t', 'targets'], workload, 'graph-check', variant, iteration, False)
    if 'all:' not in targets:
        raise RuntimeError(f'{variant} {workload}: missing all target')
    invoke(['/tools/ninja', '-C', str(build), '-n'], workload, 'graph-dry-run', variant, iteration, False)


script = root / 'script.cmake'
script.write_text('math(EXPR result "6 * 7")\nmessage(STATUS "script-result=${result}")\n')
for variant in variants:
    executable = f'/variants/{variant}/bin/cmake'
    invoke([executable, '--version'], 'process', 'warmup-version', variant, 0, False)
    invoke([executable, '-P', str(script)], 'process', 'warmup-script', variant, 0, False)
for iteration, order in enumerate(interleaved_orders(variants, repetitions)):
    for variant in order:
        executable = f'/variants/{variant}/bin/cmake'
        version = invoke([executable, '--version'], 'process', 'version', variant, iteration)
        if not version.startswith('cmake version 4.4.5\n'):
            raise RuntimeError(f'{variant}: wrong CMake version')
        result = invoke([executable, '-P', str(script)], 'process', 'script', variant, iteration)
        if 'script-result=42' not in result:
            raise RuntimeError(f'{variant}: script did not produce the expected result')

for workload, (input_name, subdirectory, options) in workloads.items():
    entries = list((Path('/inputs') / input_name).iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise RuntimeError(f'{input_name}: invalid source layout')
    for variant in variants:
        print(f'{workload}: warmup, {variant}', flush=True)
        workspace = root / variant / workload
        workspace.mkdir(parents=True)
        shutil.copytree(entries[0], workspace / 'source', symlinks=True)
        source = workspace / 'source' / subdirectory
        build = workspace / 'build'
        warmup = [f'/variants/{variant}/bin/cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                  '-DCMAKE_MAKE_PROGRAM=/tools/ninja', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake',
                  '-DCMAKE_BUILD_TYPE=Release', *options]
        invoke(warmup, workload, 'warmup', variant, 0, False)
        verify_graph(build, workload, variant, 0)
    for iteration, order in enumerate(interleaved_orders(variants, repetitions)):
        for variant in order:
            print(f'{workload}: repetition {iteration + 1}/{repetitions}, {variant}', flush=True)
            workspace = root / variant / workload
            source = workspace / 'source' / subdirectory
            build = workspace / 'build'
            shutil.rmtree(build, ignore_errors=True)
            cmakelists = source / 'CMakeLists.txt'
            original = cmakelists.read_bytes()
            executable = f'/variants/{variant}/bin/cmake'
            command = [executable, '-S', str(source), '-B', str(build), '-G', 'Ninja',
                       '-DCMAKE_MAKE_PROGRAM=/tools/ninja', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake',
                       '-DCMAKE_BUILD_TYPE=Release', *options]
            try:
                invoke(command, workload, 'initial', variant, iteration)
                verify_graph(build, workload, variant, iteration)
                invoke(command, workload, 'unchanged', variant, iteration)
                cmakelists.write_bytes(original + b'\nset(CMAKE_VERBOSE_MAKEFILE ON CACHE BOOL "" FORCE)\n')
                invoke(command, workload, 'cmakelists-edit', variant, iteration)
                if 'CMAKE_VERBOSE_MAKEFILE:BOOL=ON' not in (build / 'CMakeCache.txt').read_text():
                    raise RuntimeError(f'{variant} {workload}: CMakeLists edit had no effect')
                cmakelists.write_bytes(original)
                invoke(command, workload, 'restore-cmakelists', variant, iteration, False)
                invoke([*command, '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'], workload, 'option-change', variant, iteration)
                if not (build / 'compile_commands.json').is_file():
                    raise RuntimeError(f'{variant} {workload}: option change produced no compile commands')
                verify_graph(build, workload, variant, iteration)
            finally:
                cmakelists.write_bytes(original)
    for variant in variants:
        workspace = root / variant / workload
        source = workspace / 'source' / subdirectory
        build = workspace / 'build'
        profile = root / f'profile-{workload}-{variant}.txt'
        command = ['/benchmark/trace/loader', '--library-path', '/benchmark/trace/lib', '/benchmark/trace/strace',
                   '-f', '-c', '-e', 'trace=%file,%process', '-o', str(profile),
                   f'/variants/{variant}/bin/cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                   '-DCMAKE_MAKE_PROGRAM=/tools/ninja', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake',
                   '-DCMAKE_BUILD_TYPE=Release', *options, '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON']
        invoke(command, workload, 'syscall-profile', variant, 0, False)
        summary = profile.read_text()
        if 'total' not in summary:
            raise RuntimeError(f'{variant} {workload}: empty syscall profile')
        profiles.append({'workload': workload, 'variant': variant, 'summary': summary})
        if workload != 'llvm-clang':
            target = {'fmt': 'fmt', 'zstd': 'zstd', 'libjpeg-turbo': 'tjunittest-static'}[workload]
            invoke(['/tools/ninja', '-C', str(build), '-j', str(len(cpus)), target],
                   workload, 'graph-build', variant, 0, False)

(root / 'results.json').write_text(json.dumps({'cpus': cpus, 'records': records, 'profiles': profiles}, indent=2) + '\n')
