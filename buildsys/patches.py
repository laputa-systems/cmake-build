"""Verify the ordered patch inventory and its exact bytes."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class PatchError(Exception):
    pass


@dataclass(frozen=True)
class Patch:
    name: str
    sha256: str
    content: bytes


def _read(root: Path, name: str) -> bytes:
    relative = PurePosixPath(name)
    if relative.is_absolute() or not relative.parts or any(part in (".", "..") for part in relative.parts) or "\\" in name:
        raise PatchError(f"invalid patch inventory path: {name!r}")
    descriptors = []
    try:
        descriptors.append(os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
        for part in relative.parts[:-1]:
            descriptors.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptors[-1]))
        descriptor = os.open(relative.parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptors[-1])
        descriptors.append(descriptor)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PatchError(f"patch inventory path is not a regular file: {name}")
        with os.fdopen(os.dup(descriptor), "rb") as file:
            return file.read()
    except OSError as error:
        raise PatchError(f"cannot read patch inventory path {name!r}: {error}") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def verify_inventory(root: Path) -> tuple[Patch, ...]:
    root = Path(root)
    try:
        text = _read(root, "README.md").decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchError("patch inventory is not UTF-8") from error
    pattern = re.compile(r"\| ([0-9]+) \| `([^`]+)` \| `([0-9a-f]{64})` \| ([^|]+) \|")
    patches = []
    for line in text.splitlines():
        if not re.match(r"\|\s*[0-9]", line):
            continue
        match = pattern.fullmatch(line)
        if match is None:
            raise PatchError(f"malformed patch inventory row: {line!r}")
        order, name, expected, purpose = match.groups()
        if int(order) != len(patches) + 1 or not name.endswith(".patch") or not purpose.strip():
            raise PatchError(f"invalid patch inventory order or entry: {name!r}")
        content = _read(root, name)
        found = hashlib.sha256(content).hexdigest()
        if found != expected:
            raise PatchError(f"patch digest mismatch for {name}: {found} != {expected}")
        patches.append(Patch(name, found, content))
    names = [patch.name for patch in patches]
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*.patch")}
    if not names or len(names) != len(set(names)) or set(names) != actual:
        raise PatchError("patch inventory does not match the patch files")
    return tuple(patches)
