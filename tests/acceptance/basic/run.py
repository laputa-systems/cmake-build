from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from pathlib import Path

root = Path('/qualification')
prefix = root / 'relocated cmake'
cmake = prefix / 'bin/cmake'
work = root / 'work with spaces'
work.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)}


def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(cmake), *map(str, args)], cwd=work, env=env, text=True, capture_output=True, timeout=300)
    if (result.returncode == 0) != ok:
        raise RuntimeError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result


def contains(text: str, expected: str) -> None:
    if expected not in text:
        raise RuntimeError(f'expected {expected!r} in {text!r}')


contains(run('--version').stdout, 'cmake version 4.4.5')
contains(run('--help').stdout, 'Usage')
contains(run('-E', 'echo', 'qualified').stdout, 'qualified')
script = work / 'root.cmake'
script.write_text('message(STATUS "ROOT=${CMAKE_ROOT}")\n')
contains(run('-P', script).stdout, f'ROOT={prefix}/share/cmake-4.4')
if not (prefix / 'share/cmake/Modules/CMake.cmake').is_file():
    raise RuntimeError('Laputa module-tree path is missing')
source = work / 'project'
source.mkdir()
(source / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.20)
project(Relocation VERSION 1.2.3 LANGUAGES C CXX)
add_executable(c_test main.c)
add_executable(cxx_test main.cxx)
install(TARGETS c_test cxx_test RUNTIME DESTINATION bin)
enable_testing()
add_test(NAME relocated-test COMMAND "${CMAKE_COMMAND}" -E echo relocated-test-passed)
include(CPack)
''')
(source / 'main.c').write_text('int main(void) { return 0; }\n')
(source / 'main.cxx').write_text('int main() { return 0; }\n')
for generator, label in [('Ninja', 'ninja'), ('Unix Makefiles', 'make')]:
    build = work / label
    install = work / f'{label} install'
    arguments = ['-S', source, '-B', build, '-G', generator, '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake', f'-DCMAKE_INSTALL_PREFIX={install}', '-DREMOVE_ME:STRING=present']
    if generator == 'Ninja':
        arguments.append('-DCMAKE_MAKE_PROGRAM=/tools/ninja')
    run(*arguments)
    contains(run('-N', '-L', build).stdout, 'REMOVE_ME:STRING=present')
    run('-U', 'REMOVE_ME', '-S', source, '-B', build)
    if 'REMOVE_ME:' in run('-N', '-L', build).stdout:
        raise RuntimeError('cache -U did not remove the entry')
    run('--build', build, '--parallel', '2')
    run('--install', build)
    for name in ('c_test', 'cxx_test'):
        subprocess.run([str(install / 'bin' / name)], cwd=work, env=env, check=True, timeout=30)
    if generator == 'Ninja':
        test = subprocess.run([str(prefix / 'bin/ctest'), '--test-dir', str(build), '--output-on-failure'],
                              cwd=work, env=env, text=True, capture_output=True, timeout=120, check=True)
        contains(test.stdout, '100% tests passed')
        contains(test.stdout, 'relocated-test')
        packages = work / 'packages'
        packages.mkdir()
        subprocess.run([str(prefix / 'bin/cpack'), '--config', str(build / 'CPackConfig.cmake'),
                        '-G', 'TGZ', '-B', str(packages)], cwd=work, env=env, check=True, timeout=120)
        archives = list(packages.glob('*.tar.gz'))
        if len(archives) != 1:
            raise RuntimeError('CPack did not create exactly one TGZ archive')
        with tarfile.open(archives[0], 'r:gz') as archive:
            if not any(name.endswith('/bin/c_test') for name in archive.getnames()):
                raise RuntimeError('CPack archive is missing the installed executable')

missing = root / 'missing resource'
shutil.copytree(prefix, missing, symlinks=True)
(missing / 'share/cmake-4.4/Modules/CMakeDetermineCCompiler.cmake').unlink()
result = subprocess.run([str(missing / 'bin/cmake'), '-S', str(source), '-B', str(work / 'missing-build'), '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake'], cwd=work, env=env, text=True, capture_output=True, timeout=120)
if result.returncode == 0 or 'CMakeDetermineCCompiler.cmake' not in result.stdout + result.stderr:
    raise RuntimeError('missing compiler module did not produce a missing-resource error')
broken = root / 'broken relocation'
shutil.copytree(prefix, broken, symlinks=True)
(broken / 'share').rename(root / 'moved share')
result = subprocess.run([str(broken / 'bin/cmake'), '-P', str(script)], cwd=work, env=env, text=True, capture_output=True, timeout=120)
if result.returncode == 0:
    raise RuntimeError('broken relocation unexpectedly succeeded')
print('basic qualification: CLI, C/C++ builds, generators, relocation and negative controls passed')
