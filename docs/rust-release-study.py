import shutil
import subprocess
from pathlib import Path

from buildsys import sandbox
from buildsys.inputs import load_bootstrap
from buildsys.targets import target

root = Path.cwd()
work = root / '.work/tmp/rust-release-comparison'
work.mkdir(parents=True, exist_ok=False)
suite = work / 'suite'
suite.mkdir()
source = (root / 'tests/benchmark/run.py').read_text()
old = "variants = ('product', 'musl', 'kitware')"
assert source.count(old) == 1
(suite / 'run.py').write_text(source.replace(old, "variants = ('product', 'musl')"))
scratch = work / 'work'
scratch.mkdir()
trace = scratch / 'trace'
(trace / 'lib').mkdir(parents=True)
strace = shutil.which('strace')
if strace is None:
    raise SystemExit('strace is required')
tracer = Path(strace)
shutil.copy2(tracer, trace / 'strace')
dependencies = subprocess.run(['ldd', str(tracer)], capture_output=True, text=True, check=True).stdout.splitlines()
loaders = [Path(line.strip().split(' ', 1)[0]) for line in dependencies if line.strip().startswith('/') and '=>' not in line]
assert len(loaders) == 1
shutil.copy2(loaders[0], trace / 'loader')
for line in dependencies:
    if '=>' in line:
        name, value = line.strip().split('=>', 1)
        shutil.copy2(Path(value.strip().split(' ', 1)[0]), trace / 'lib' / name.strip())
t = target('x86_64-unknown-linux-musl')
lock = load_bootstrap(root / 'bootstrap.lock.json')
runtime = work / 'runtime'
sandbox.copy_reference_runtime(sandbox.image_tag(lock, t, root / 'docker/builder.Dockerfile'), t, runtime)
phases = root / '.work/build' / t.triple / 'phases'
baseline = (root / '.work/generations' / t.triple / 'active/usr').resolve()
candidate = root / '.work/tmp/rust-release-candidate/usr'
mounts = [(scratch, '/benchmark'), (suite, '/suite'), (root / 'buildsys', '/controller/buildsys'),
          (candidate, '/variants/product'), (baseline, '/variants/musl'), (runtime, '/opt/alpine'),
          (runtime / 'lib' / Path(t.musl_loader).name, t.musl_loader),
          (runtime / 'etc' / f'ld-musl-{t.machine}.path', f'/etc/ld-musl-{t.machine}.path'),
          (runtime / 'usr/make', '/usr/bin/make'),
          (phases / 'prepare', f'/src/.work/build/{t.triple}/phases/prepare'),
          (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
          (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja')]
for name in ('fmt-source', 'zstd-source', 'libjpeg-turbo-source', 'llvm-project-source'):
    mounts.append((phases / f'project-{name}/source', f'/inputs/{name}'))
result = sandbox.run_sealed(lock.reference_image, ['/opt/alpine/usr/python3', '/suite/run.py', '5'],
                            target=t, mounts=mounts, env={'PYTHONHOME': '/opt/alpine/usr', 'TMPDIR': '/benchmark'},
                            workdir='/benchmark', timeout=28800,
                            read_only=frozenset(destination for _, destination in mounts if destination != '/benchmark'))
(work / 'runner.out').write_text(result.stdout)
(work / 'runner.err').write_text(result.stderr)
if result.returncode:
    raise RuntimeError(f'comparison failed ({result.returncode}): {result.stderr[-4000:]}')
print(work / 'work/results.json')
