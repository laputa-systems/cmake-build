from pathlib import Path

from buildsys import sandbox
from buildsys.inputs import load_bootstrap
from buildsys.targets import target

root = Path.cwd()
study = root / '.work/tmp/perf-study'
work = root / '.work/tmp/rust-release-comparison'
phases = root / '.work/build/x86_64-unknown-linux-musl/phases'
t = target('x86_64-unknown-linux-musl')
lock = load_bootstrap(root / 'bootstrap.lock.json')
runtime = work / 'runtime'
mounts = [(work / 'work', '/benchmark'), (study, '/profile'),
          (root / '.work/tmp/rust-release-candidate/usr', '/variants/product'),
          (runtime, '/opt/alpine'), (runtime / 'lib' / Path(t.musl_loader).name, t.musl_loader),
          (runtime / 'etc' / f'ld-musl-{t.machine}.path', f'/etc/ld-musl-{t.machine}.path'),
          (runtime / 'usr/make', '/usr/bin/make'),
          (phases / 'prepare', f'/src/.work/build/{t.triple}/phases/prepare'),
          (phases / 'bootstrap/toolchain.cmake', '/tools/toolchain.cmake'),
          (phases / 'bootstrap/ninja-build/ninja', '/tools/ninja')]
result = sandbox.run_sealed(lock.reference_image, ['/opt/alpine/usr/python3', '/profile/profile.py'],
                            target=t, mounts=mounts,
                            env={'PYTHONHOME': '/opt/alpine/usr', 'TMPDIR': '/benchmark',
                                 'HOME': '/benchmark', 'PATH': '/usr/bin:/bin'},
                            workdir='/benchmark', timeout=1200,
                            read_only=frozenset(destination for _, destination in mounts if destination != '/benchmark'))
(study / 'cmake.out').write_text(result.stdout)
(study / 'cmake.err').write_text(result.stderr)
print(f'cmake_exit={result.returncode}')
if result.returncode:
    raise SystemExit(result.stderr[-4000:])
