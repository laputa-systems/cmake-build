"""Make the locked laputa-buildlib wheel importable from the content-addressed input cache.

Every execution context reaches `buildlib` through the `buildsys` package: host Python, the
offline Alpine builder containers, and the benchmark runtime. The wheel is the `buildlib-wheel`
input of `sources.lock.json`. Importing this module verifies the cached file against that pin,
downloads it when it is absent and the network allows, and puts the wheel on `sys.path`.
This module is the only code that runs before `buildlib` can be imported, so it uses the
standard library alone and reads the lock as plain JSON.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_LOCK = ROOT / "sources.lock.json"
INPUT_NAME = "buildlib-wheel"


def cache_root(root: Path) -> Path:
    return root / ".work" / "cache"


def object_path(root: Path, sha256: str) -> Path:
    return root / "objects" / f"{sha256}.blob"


def _pin() -> dict:
    try:
        document = json.loads(SOURCES_LOCK.read_text())
        pin = next(item for item in document["inputs"] if item["name"] == INPUT_NAME)
        return {key: pin[key] for key in ("url", "sha256", "size")}
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as error:
        raise ImportError(f"{SOURCES_LOCK} does not pin {INPUT_NAME}: {error!r}") from error


def _matches(data: bytes, pin: dict) -> bool:
    return len(data) == pin["size"] and hashlib.sha256(data).hexdigest() == pin["sha256"]


def _download(pin: dict, destination: Path) -> None:
    request = urllib.request.Request(pin["url"], headers={"User-Agent": "cmake-build/1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(pin["size"] + 1)
    except OSError as error:
        raise ImportError(
            f"{INPUT_NAME} is absent from {destination.parent.parent} and cannot be downloaded "
            f"from {pin['url']}: {error}; run `python3 build.py fetch` with network access first"
        ) from error
    if not _matches(data, pin):
        raise ImportError(f"{INPUT_NAME}: {pin['url']} did not serve the pinned bytes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".buildlib-wheel.", suffix=".part", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)


def locate() -> Path:
    pin = _pin()
    path = object_path(cache_root(ROOT), pin["sha256"])
    if path.is_symlink() or not path.is_file() or not _matches(path.read_bytes(), pin):
        _download(pin, path)
    return path


WHEEL = locate()
sys.path.insert(0, str(WHEEL))
