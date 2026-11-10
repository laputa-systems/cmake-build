from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

root = Path('/qualification')
triple = f'{os.uname().machine}-unknown-linux-musl'
phase = os.environ['UPSTREAM_PHASE']
if phase not in ('cmake', 'reference'):
    raise RuntimeError(f'invalid upstream phase: {phase}')
build = Path(f'/src/.work/build/{triple}/phases/{phase}/build')
ctest = build / 'bin/ctest'
patterns = [line.strip() for line in Path('/selection/upstream-subset.txt').read_text().splitlines() if line.strip()]
if not patterns:
    raise RuntimeError('upstream test selection is empty')
expression = '|'.join(f'({pattern})' for pattern in patterns)
report = root / 'upstream.xml'
command = [str(ctest), '--test-dir', str(build), '--output-on-failure', '--no-tests=error',
           '--parallel', '8', '--timeout', '1200', '--output-junit', str(report), '-R', expression]
result = subprocess.run(command, cwd=root, env=os.environ, text=True, capture_output=True, timeout=1200)
output = result.stdout + result.stderr
(root / 'upstream.txt').write_text(output)
match = re.search(r'(?:\d+% tests passed(?:, \d+ tests failed)? out of )(\d+)', output)
if not report.is_file() or report.stat().st_size == 0 or not match or int(match.group(1)) == 0:
    raise RuntimeError(f'upstream subset produced no valid report:\n{output[-12000:]}')
print(f'upstream subset: {match.group(1)} tests executed')
if result.returncode:
    raise RuntimeError(f'upstream subset failed ({result.returncode}):\n{output[-12000:]}')
