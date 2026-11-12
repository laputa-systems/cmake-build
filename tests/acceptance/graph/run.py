from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

root = Path('/qualification')
cmake = root / 'relocated cmake/bin/cmake'
work = root / 'graph suite'
source = work / 'source'
work.mkdir(parents=True, exist_ok=True)
shutil.copytree('/suite', source)
env = {**os.environ, 'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)}


def run(*args: str | Path, cwd: Path = work, environment: dict[str, str] = env) -> str:
    result = subprocess.run([str(cmake), *map(str, args)], cwd=cwd, env=environment, text=True, capture_output=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def run_binary(path: Path) -> None:
    subprocess.run([str(path)], cwd=work, env=env, check=True, timeout=30)


for generator, label in [('Ninja', 'ninja'), ('Unix Makefiles', 'make')]:
    build = work / f'{label} build'
    install = work / f'{label} install'
    query = build / '.cmake/api/v1/query'
    query.mkdir(parents=True)
    (query / 'codemodel-v2').touch()
    (query / 'cache-v2').touch()
    arguments = ['-S', source, '-B', build, '-G', generator, '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake', f'-DCMAKE_INSTALL_PREFIX={install}']
    if generator == 'Ninja':
        arguments.append('-DCMAKE_MAKE_PROGRAM=/tools/ninja')
    run(*arguments)
    reply = build / '.cmake/api/v1/reply'
    index = json.loads(next(reply.glob('index-*.json')).read_text())
    api = {}
    for name, response in index['reply'].items():
        data = json.loads((reply / response['jsonFile']).read_text())
        if data['kind'] == 'codemodel':
            for configuration in data['configurations']:
                configuration['targetReplies'] = [json.loads((reply / item['jsonFile']).read_text()) for item in configuration['targets']]
        api[name] = data
    (work / f'{label}-file-api.json').write_text(json.dumps(api, indent=2, sort_keys=True) + '\n')
    run('--build', build, '--parallel', '2')
    run_binary(build / 'graph')
    object_file = build / 'CMakeFiles/base.dir/base.c.o'
    for changed in (source / 'base.c', source / 'include/graph.h'):
        before = object_file.stat().st_mtime_ns
        os.utime(changed, None)
        run('--build', build, '--parallel', '2')
        if object_file.stat().st_mtime_ns <= before:
            raise RuntimeError(f'{generator}: changing {changed.name} did not rebuild base.c')
    os.utime(source / 'CMakeLists.txt', None)
    output = run('--build', build, '--parallel', '2')
    if 'Configuring done' not in output:
        raise RuntimeError(f'{generator}: changing CMakeLists.txt did not reconfigure')
    run('--install', build)
    downstream = work / f'{label} downstream'
    downstream_args = ['-S', source / 'downstream', '-B', downstream, '-G', generator, '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake', f'-DCMAKE_PREFIX_PATH={install}']
    if generator == 'Ninja':
        downstream_args.append('-DCMAKE_MAKE_PROGRAM=/tools/ninja')
    run(*downstream_args)
    run('--build', downstream, '--parallel', '2')
    run_binary(downstream / 'downstream')
presets = {
    'version': 6,
    'configurePresets': [{
        'name': 'ninja-check', 'generator': 'Ninja', 'binaryDir': '${sourceDir}/preset-build',
        'cacheVariables': {'CMAKE_BUILD_TYPE': 'Release', 'CMAKE_MAKE_PROGRAM': '/tools/ninja',
                           'CMAKE_TOOLCHAIN_FILE': '/tools/toolchain.cmake'},
    }],
    'buildPresets': [{'name': 'build-check', 'configurePreset': 'ninja-check'}],
}
(source / 'CMakePresets.json').write_text(json.dumps(presets))
if 'ninja-check' not in run('--list-presets', '-S', source):
    raise RuntimeError('configure preset was not listed')
run('--preset', 'ninja-check', '-S', source)
run('--build', '--preset', 'build-check', '--parallel', '2', cwd=source)
run_binary(source / 'preset-build/graph')
machine = os.uname().machine
prepared = f'/src/.work/build/{machine}-unknown-linux-musl/phases/prepare'
compiler_flags = f'--target={machine}-unknown-linux-musl --sysroot={prepared}/sysroot'
system_env = {**env, 'CC': f'{prepared}/toolchain/bin/clang {compiler_flags}',
              'CXX': f'{prepared}/toolchain/bin/clang++ {compiler_flags} -stdlib=libc++'}
system_info = work / 'system-information.txt'
run('--system-information', system_info, '-G', 'Unix Makefiles', environment=system_env)
keys = ('CMAKE_SYSTEM_NAME ', 'CMAKE_SYSTEM_PROCESSOR ', 'CMAKE_HOST_SYSTEM_NAME ',
        'CMAKE_HOST_SYSTEM_PROCESSOR ', 'CMAKE_C_COMPILER_ID ', 'CMAKE_CXX_COMPILER_ID ')
subset = sorted(line for line in system_info.read_text().splitlines() if line.startswith(keys))
if not all(any(line.startswith(key) for line in subset) for key in keys):
    raise RuntimeError('system information lacks an expected field')
(work / 'system-information-subset.txt').write_text('\n'.join(subset) + '\n')
print('graph qualification: transitive and imported targets, generation, compiler checks, incremental builds, and installed exports passed')
