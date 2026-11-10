"""Verified content-addressed acquisition of locked build inputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .targets import TARGETS

SCHEMA_VERSION = 1
ROLES = ("source", "build-source", "reference", "test")
ALL_TARGETS = "all"
_CHUNK = 1 << 20


class InputError(Exception):
    """A lock is malformed or input bytes do not match it."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def identity(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_bytes(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class Input:
    name: str
    version: str
    url: str
    sha256: str
    role: str
    target: str
    size: int | None = None
    license: str | None = None
    purpose: str | None = None

    def __post_init__(self) -> None:
        for field in ("name", "version", "url", "sha256", "role", "target"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value:
                raise InputError(f"{self.name}: {field} must be a nonempty string")
        if not _valid_sha256(self.sha256):
            raise InputError(f"{self.name}: sha256 must be lowercase hex")
        if self.size is not None and (type(self.size) is not int or self.size < 0):
            raise InputError(f"{self.name}: size must be a nonnegative integer")
        if self.role not in ROLES:
            raise InputError(f"{self.name}: unknown role {self.role!r}")
        if self.target != ALL_TARGETS and self.target not in TARGETS:
            raise InputError(f"{self.name}: unknown target {self.target!r}")

    def identity(self) -> str:
        material = canonical_json(
            {
                "name": self.name,
                "version": self.version,
                "url": self.url,
                "sha256": self.sha256,
                "role": self.role,
                "target": self.target,
                "size": self.size,
            }
        )
        return identity(material.encode())


def _read_json(path: Path) -> dict:
    try:
        document = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read lock {path}: {error}") from error
    if not isinstance(document, dict):
        raise InputError(f"{path}: expected a JSON object")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise InputError(f"{path}: unsupported schema_version {document.get('schema_version')!r}")
    return document


def _entry(entry: object, source: str, index: int) -> dict:
    if not isinstance(entry, dict):
        raise InputError(f"{source}: entry #{index} is not an object")
    return entry


def _input(entry: dict, source: str, index: int, *, require_size: bool) -> Input:
    required = ("name", "version", "url", "sha256", "role", "target")
    for field in required:
        if field not in entry:
            raise InputError(f"{source}: entry #{index} missing {field}")
    item = Input(
        name=entry["name"],
        version=entry["version"],
        url=entry["url"],
        sha256=entry["sha256"],
        role=entry["role"],
        target=entry["target"],
        size=entry.get("size"),
        license=entry.get("license"),
        purpose=entry.get("purpose"),
    )
    if require_size and item.size is None:
        raise InputError(f"{source}: {item.name} must pin a size")
    return item


def load_sources(path: Path) -> list[Input]:
    path = Path(path)
    document = _read_json(path)
    entries = document.get("inputs")
    if not isinstance(entries, list):
        raise InputError(f"{path}: expected 'inputs' list")
    inputs: list[Input] = []
    seen: set[str] = set()
    for index, raw in enumerate(entries):
        item = _input(_entry(raw, str(path), index), str(path), index, require_size=True)
        if item.role == "build-source" and item.size is None:
            raise InputError(f"{path}: {item.name} must pin a size")
        if item.name in seen:
            raise InputError(f"{path}: duplicate input {item.name}")
        seen.add(item.name)
        inputs.append(item)
    return inputs


@dataclass(frozen=True)
class BootstrapLock:
    alpine_release: str
    image_index_digest: str
    image_manifest_reference: str
    repositories: dict[str, list[str]]
    targets: dict[str, dict]
    keys: list[Input]


def load_bootstrap(path: Path) -> BootstrapLock:
    path = Path(path)
    document = _read_json(path)
    alpine = document.get("alpine")
    if not isinstance(alpine, dict):
        raise InputError(f"{path}: expected 'alpine' object")
    for field in ("release", "image_index_digest", "image_manifest_reference"):
        if not isinstance(alpine.get(field), str) or not alpine[field]:
            raise InputError(f"{path}: alpine.{field} must be a nonempty string")
    if not alpine["image_index_digest"].startswith("sha256:"):
        raise InputError(f"{path}: alpine.image_index_digest must be a sha256 index digest")
    repositories = alpine.get("repositories")
    if not isinstance(repositories, dict):
        raise InputError(f"{path}: alpine.repositories must be an object")
    for triple in TARGETS:
        urls = repositories.get(triple)
        if not isinstance(urls, list) or not urls or not all(
            isinstance(url, str) and url.startswith("https://") for url in urls
        ):
            raise InputError(f"{path}: alpine.repositories.{triple} must list https URLs")
    targets = document.get("targets")
    if not isinstance(targets, dict):
        raise InputError(f"{path}: expected 'targets' object")
    keys: list[Input] = []
    for index, raw in enumerate(alpine.get("keys", [])):
        entry = _entry(raw, f"{path}:alpine.keys", index)
        keys.append(_input(entry, f"{path}:alpine.keys", index, require_size=True))
    for triple, section in targets.items():
        if triple not in TARGETS:
            raise InputError(f"{path}: unknown target section {triple}")
        if not isinstance(section, dict):
            raise InputError(f"{path}: target section {triple} is not an object")
        packages = section.get("packages", [])
        if not isinstance(packages, list):
            raise InputError(f"{path}: {triple}.packages must be a list")
        for index, raw in enumerate(packages):
            entry = _entry(raw, f"{path}:{triple}.packages", index)
            item = _input(entry, f"{path}:{triple}.packages", index, require_size=True)
            if item.target not in (triple, ALL_TARGETS):
                raise InputError(f"{path}: {item.name} target {item.target} is not {triple}")
        rust = section.get("rust")
        if rust is not None:
            if not isinstance(rust, dict) or not isinstance(rust.get("components"), list):
                raise InputError(f"{path}: {triple}.rust.components must be a list")
            for index, raw in enumerate(rust["components"]):
                entry = _entry(raw, f"{path}:{triple}.rust.components", index)
                if "role" not in entry:
                    entry = {**entry, "role": "build-source", "target": ALL_TARGETS}
                _input(entry, f"{path}:{triple}.rust.components", index, require_size=True)
    return BootstrapLock(
        alpine_release=alpine["release"],
        image_index_digest=alpine["image_index_digest"],
        image_manifest_reference=alpine["image_manifest_reference"],
        repositories=repositories,
        targets=targets,
        keys=keys,
    )


def bootstrap_inputs(lock: BootstrapLock, triple: str) -> list[Input]:
    section = lock.targets.get(triple)
    inputs = list(lock.keys)
    if section is None:
        return inputs
    inputs.extend(
        _input(entry, "bootstrap", index, require_size=True)
        for index, entry in enumerate(section.get("packages", []))
    )
    rust = section.get("rust")
    if rust:
        name_prefix = rust.get("name_prefix", "rust")
        for index, entry in enumerate(rust["components"]):
            entry = {"role": "build-source", "target": ALL_TARGETS, **entry}
            entry.setdefault("name", f"{name_prefix}-{index}")
            if "version" not in entry:
                entry["version"] = rust.get("channel", "unknown")
            inputs.append(
                _input(entry, "bootstrap", index, require_size=True)
            )
    return inputs


class Cache:
    """Content-addressed cache; every read and every publication is verified."""

    def __init__(self, root: Path, *, offline: bool = False) -> None:
        self.root = Path(root)
        self.offline = offline

    def _object(self, item: Input) -> Path:
        return self.root / "objects" / f"{item.sha256}.blob"

    def require(self, item: Input) -> Path:
        path = self._object(item)
        if path.is_symlink() or not path.is_file():
            raise InputError(f"{item.name}: absent from cache ({path})")
        found, size = digest_bytes(path)
        if found != item.sha256:
            raise InputError(f"{item.name}: cache object digest {found} != pinned {item.sha256}")
        if item.size is not None and size != item.size:
            raise InputError(f"{item.name}: cache size {size} != pinned {item.size}")
        return path

    def store(self, source: Path, item: Input) -> Path:
        found, size = digest_bytes(source)
        if found != item.sha256:
            raise InputError(f"{item.name}: digest {found} != pinned {item.sha256}")
        if item.size is not None and size != item.size:
            raise InputError(f"{item.name}: size {size} != pinned {item.size}")
        target = self._object(item)
        try:
            return self.require(item)
        except InputError:
            pass
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".part")
        try:
            shutil.copyfile(source, temporary)
            if digest_bytes(temporary) != (found, size):
                raise InputError(f"{item.name}: bytes changed during publication")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return self.require(item)

    def fetch(self, item: Input, timeout: float = 120.0) -> Path:
        if self.offline:
            raise InputError(f"{item.name}: offline phase cannot fetch from the network")
        try:
            return self.require(item)
        except InputError:
            pass
        self.root.mkdir(parents=True, exist_ok=True)
        staged = self.root / f".{item.sha256}.download"
        try:
            request = urllib.request.Request(item.url, headers={"User-Agent": "cmake-build/1"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response, staged.open(
                    "wb"
                ) as out:
                    shutil.copyfileobj(response, out, _CHUNK)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                raise InputError(f"{item.name}: cannot download {item.url}: {error}") from error
            return self.store(staged, item)
        finally:
            staged.unlink(missing_ok=True)


def _reject(name: str, reason: str) -> None:
    raise InputError(f"unsafe archive entry ({reason}): {name!r}")


def _check_member(member: tarfile.TarInfo, destination: Path, regular: set[str]) -> None:
    name = member.name
    if not name or name.startswith("/") or Path(name).is_absolute():
        _reject(name, "absolute")
    parts = Path(name).parts
    if ".." in parts:
        _reject(name, "traversal")
    if member.issym():
        link = Path(member.linkname)
        if link.is_absolute():
            _reject(name, "link-escape")
        target = os.path.normpath(os.path.join(destination, os.path.dirname(name), member.linkname))
        root = os.path.normpath(destination)
        if target != root and not target.startswith(root + os.sep):
            _reject(name, "link-escape")
    elif member.islnk():
        link = Path(member.linkname)
        if link.is_absolute() or ".." in link.parts:
            _reject(name, "link-escape")
        if member.linkname not in regular:
            _reject(name, "dangling hardlink")
    elif member.isdir():
        if name.rstrip("/") == ".":
            return
    elif not member.isreg():
        _reject(name, "special")


def safe_extract(archive: Path, destination: Path) -> Path:
    """Extract a verified tar archive, rejecting every member that escapes the tree."""
    destination = Path(destination)
    if destination.exists():
        raise InputError(f"{destination}: already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=destination.parent))
    try:
        with tarfile.open(archive, "r:*") as tar:
            members = tar.getmembers()
            regular = {member.name for member in members if member.isreg()}
            for member in members:
                _check_member(member, staging, regular)
            tar.extractall(staging, members=members, filter="data")
        os.replace(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def tree_digest(root: Path, *, exclude: set[str] | None = None) -> str:
    """Digest a tree's paths, types, executable bits, link targets, and file contents."""
    root = Path(root)
    excluded = exclude or set()
    digest = hashlib.sha256()

    def record(*parts: str) -> None:
        for part in parts:
            digest.update(part.encode())
            digest.update(b"\0")

    def visit(directory: Path, relative: str) -> None:
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            name = entry.name
            if relative == "" and name in excluded:
                continue
            path = f"{relative}/{name}" if relative else name
            if entry.is_symlink():
                record("link", path, os.readlink(entry))
            elif entry.is_dir():
                record("dir", path)
                visit(entry, path)
            elif entry.is_file():
                record("file", path, "x" if os.access(entry, os.X_OK) else "-")
                record(digest_bytes(entry)[0])
            else:
                record("special", path)

    visit(root, "")
    return digest.hexdigest()
