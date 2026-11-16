from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FOOTER = '''Maintained by Joshua Li: https://github.com/laputa-systems/cmake-build
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md
'''


def check(cmake: Path) -> None:
    def invoke(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(cmake), *args], text=True, capture_output=True, check=True, timeout=30)

    for flag in ('--help', '-h', '-H', '-help', '-usage', '/?'):
        result = invoke(flag)
        if not result.stdout.endswith(FOOTER) or result.stdout.count('Maintained by Joshua Li:') != 1 or result.stderr:
            raise RuntimeError(f'{flag}: primary help footer is missing, repeated, or not last')
    for args in ((), ('--version',), ('--version=json-v1',), ('-E', 'capabilities'),
                 ('-E', 'echo', 'qualified'), ('--help-command-list',),
                 ('--help-command', 'add_executable')):
        result = invoke(*args)
        if 'Maintained by Joshua Li:' in result.stdout + result.stderr:
            raise RuntimeError(f'{args}: footer leaked into non-primary output')
        if args == ('--version',):
            if result.stdout.splitlines()[0] != 'cmake version 4.4.5':
                raise RuntimeError('upstream version token changed')
        elif args in (('--version=json-v1',), ('-E', 'capabilities')):
            data = json.loads(result.stdout)
            version = data['program']['version'] if args == ('--version=json-v1',) else data['version']
            if version['string'] != '4.4.5':
                raise RuntimeError(f'{args}: upstream JSON version changed')
        elif args == ('-E', 'echo', 'qualified') and result.stdout != 'qualified\n':
            raise RuntimeError('normal command output changed')


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
    print('built CMake help contract passed')
