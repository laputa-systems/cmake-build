"""Shared fixtures for controller tests."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / ".work" / "tmp"


@contextlib.contextmanager
def workspace():
    TMP.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="test-", dir=TMP))
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def write_lock(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps({"schema_version": 1, "inputs": entries}))
    return path


def archive(path: Path, members: list[tuple[str, bytes | None, str | None]]) -> Path:
    """Create a tar; each member is (name, content, link target)."""
    with tarfile.open(path, "w:gz") as tar:
        for name, content, link in members:
            info = tarfile.TarInfo(name)
            if link is not None:
                info.type = tarfile.SYMTYPE
                info.linkname = link
                tar.addfile(info)
            elif content is None:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            else:
                info.size = len(content)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(content))
    return path
