"""Admit the pinned laputa-buildlib wheel where the vendored bootstrap cannot run.

Every execution context reaches `buildlib` through the `buildsys` package: host Python, the
offline Alpine builder containers, and the benchmark runtime. `bootstrap/buildlib-run` supplies
the wheel on hosts that run the controller through it, but the sealed containers run
`python3 build.py` with a fixed `PYTHONPATH`, and the benchmark runtime mounts only
`buildsys/`. This module is that bootstrap boundary: it admits the wheel from the
content-addressed input cache after checking its size and SHA-256 against the pin, and it
provisions a missing wheel by asking the shared shim for the copy it already verified rather
than downloading a second one. The admitted wheel is placed first on `sys.path`, and admission
fails unless `buildlib` resolves to it, so a repository-local or installed package cannot run in
its place.
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import zipimport
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
SOURCES_LOCK = ROOT / "sources.lock.json"
SHIM = ROOT / "bootstrap" / "buildlib-run"
INPUT_NAME = "buildlib-wheel"

# The shim exports its verified wheel as the whole of PYTHONPATH when the caller's is removed.
# The copy runs isolated and never imports buildlib, so no package near the caller executes.
_COPY_WHEEL = "import os, shutil, sys; shutil.copyfile(os.environ['PYTHONPATH'], sys.argv[1])"


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
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.", suffix=".part")
    os.close(descriptor)
    staging = Path(name)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    try:
        try:
            result = subprocess.run(
                ["sh", str(SHIM), "--", "-I", "-c", _COPY_WHEEL, str(staging)],
                cwd=destination.parent,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            raise ImportError(f"{INPUT_NAME}: cannot run {SHIM}: {error}") from error
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise ImportError(
                f"{INPUT_NAME} is absent from {destination.parent} and {SHIM} could not "
                f"provision it ({result.returncode}): {detail}"
            )
        if not _matches(staging.read_bytes(), pin):
            raise ImportError(f"{INPUT_NAME}: the bootstrap shim copied bytes that do not match the pin")
        staging.chmod(0o644)
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


def _archive(spec: importlib.machinery.ModuleSpec | None) -> Path | None:
    loader = spec.loader if spec is not None else None
    return Path(loader.archive) if isinstance(loader, zipimport.zipimporter) else None


def _require_admitted(name: str, spec: importlib.machinery.ModuleSpec | None, wheel: Path) -> None:
    archive = _archive(spec)
    if archive is None or archive.is_symlink() or not archive.is_file():
        origin = spec.origin if spec is not None else None
        raise ImportError(f"{INPUT_NAME}: {name} resolves to {origin}, not the pinned wheel {wheel}")
    if archive != wheel and not _matches(archive.read_bytes(), _pin()):
        raise ImportError(f"{INPUT_NAME}: {name} was imported from {archive}, which does not match the pin")


def admit() -> Path:
    """Put the verified cache object first on `sys.path` and require `buildlib` to resolve to it.

    The cache object is admitted even when another `buildlib` is importable, because the sealed
    builder containers and the benchmark runtime mount this cache and cannot fetch their own copy.
    A `buildlib` that is already imported must come from a wheel whose bytes match the pin.
    """
    wheel = locate()
    loaded = {name: module for name, module in sys.modules.items() if name == "buildlib" or name.startswith("buildlib.")}
    if loaded:
        for name, module in loaded.items():
            _require_admitted(name, getattr(module, "__spec__", None), wheel)
        return wheel
    entry = str(wheel)
    sys.path[:] = [entry, *(item for item in sys.path if item != entry)]
    importlib.invalidate_caches()
    _require_admitted("buildlib", importlib.util.find_spec("buildlib"), wheel)
    return wheel


ADMITTED = admit()
