from __future__ import annotations

import re
from pathlib import Path


class LicenseError(Exception):
    pass


def verify_closure(rustls: str, std: str, root: Path) -> None:
    for group, tree in (('rustls', rustls), ('rust-std', std)):
        names = set()
        for line in tree.splitlines():
            match = re.match(r'^([A-Za-z0-9_-]+) v([A-Za-z0-9.+_-]+)(?:\s|$)', line)
            if match is None:
                raise LicenseError(f'invalid {group} dependency entry: {line!r}')
            names.add(f'{match.group(1)}-{match.group(2)}')
        if not names:
            raise LicenseError(f'{group} dependency closure is empty')
        base = (root / group).resolve()
        for name in sorted(names):
            directory = base / name
            if not directory.is_dir() or not directory.resolve().is_relative_to(base) or not any(directory.iterdir()):
                raise LicenseError(f'{group} dependency lacks license texts: {name}')
