"""Admit the pinned laputa-buildlib wheel where the vendored bootstrap cannot run.

Every execution context reaches `buildlib` through the `buildsys` package: host Python, the
offline Alpine builder containers, and the benchmark runtime. `bootstrap/buildlib-run` supplies
the wheel on hosts that run the controller through it, but the sealed containers run
`python3 build.py` with a fixed `PYTHONPATH`, and the benchmark runtime mounts only
`buildsys/`. This module is that bootstrap boundary: it admits the wheel from the
content-addressed input cache after checking its size and SHA-256 against the pin, and it
provisions a missing wheel by asking the shared shim for the copy it already verified rather
than downloading a second one.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
SOURCES_LOCK = ROOT / "sources.lock.json"
SHIM = ROOT / "bootstrap" / "buildlib-run"
INPUT_NAME = "buildlib-wheel"

_COPY_WHEEL = (
    "import pathlib, shutil, sys, buildlib\n"
    "wheel = pathlib.Path(buildlib.__file__).parent.parent\n"
    "if not wheel.is_file():\n"
    "    raise SystemExit(f'buildlib was imported from {wheel}, which is not a verified wheel')\n"
    "shutil.copyfile(wheel, sys.argv[1])\n"
)


class WheelPin(TypedDict):
    url: str
    sha256: str
    size: int


def cache_root(root: Path) -> Path:
    return root / ".work" / "cache"


def object_path(root: Path, sha256: str) -> Path:
    return root / "objects" / f"{sha256}.blob"


def _pin() -> WheelPin:
    try:
        document = json.loads(SOURCES_LOCK.read_text())
        pin = next(item for item in document["inputs"] if item["name"] == INPUT_NAME)
        url, sha256, size = pin["url"], pin["sha256"], pin["size"]
        if not isinstance(url, str) or not url:
            raise ValueError("url must be a nonempty string")
        if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise ValueError("sha256 must be a lowercase hexadecimal digest")
        if type(size) is not int or size < 0:
            raise ValueError("size must be a nonnegative integer")
        return {"url": url, "sha256": sha256, "size": size}
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as error:
        raise ImportError(f"{SOURCES_LOCK} does not pin {INPUT_NAME}: {error!r}") from error


def _matches(data: bytes, pin: WheelPin) -> bool:
    return len(data) == pin["size"] and hashlib.sha256(data).hexdigest() == pin["sha256"]


def _provision(destination: Path) -> None:
    pin = _pin()
    staging = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            ["sh", str(SHIM), "--", "-c", _COPY_WHEEL, str(staging)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ImportError(f"{INPUT_NAME}: cannot run {SHIM}: {error}") from error
    try:
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise ImportError(
                f"{INPUT_NAME} is absent from {destination.parent} and {SHIM} could not "
                f"provision it ({result.returncode}): {detail}"
            )
        if not _matches(staging.read_bytes(), pin):
            raise ImportError(f"{INPUT_NAME}: the bootstrap shim copied bytes that do not match the pin")
        os.replace(staging, destination)
    finally:
        staging.unlink(missing_ok=True)


def locate() -> Path:
    """Return the verified cached wheel, provisioning it through the shim when absent."""
    pin = _pin()
    path = object_path(cache_root(ROOT), pin["sha256"])
    if path.is_symlink():
        raise ImportError(f"{INPUT_NAME}: refusing cache symlink {path}")
    if not path.is_file() or not _matches(path.read_bytes(), pin):
        _provision(path)
    return path


def wheel_path() -> Path:
    """The cache object the pinned wheel must occupy, without provisioning it."""
    return object_path(cache_root(ROOT), _pin()["sha256"])


def admit() -> Path:
    """Verify the cache object and put it on `sys.path` when `buildlib` is not importable.

    The cache object is admitted even when `buildlib` is already importable, because the sealed
    builder containers and the benchmark runtime mount this cache and cannot fetch their own copy.
    """
    wheel = locate()
    if importlib.util.find_spec("buildlib") is None:
        sys.path.insert(0, str(wheel))
    return wheel


ADMITTED = admit()
