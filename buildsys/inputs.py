"""Verified content-addressed acquisition of locked build inputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from buildlib import hashing, locks
from buildlib.hashing import digest_file
from buildlib.locks import FetchError, Input, LockError

from .buildlib_wheel import object_path
from .targets import TARGETS

ROLES = ("source", "build-source", "reference", "test")
ALL_TARGETS = "all"


class InputError(Exception):
    """A lock is malformed or input bytes do not match it."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def identity(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repository_input(item: Input, source: str) -> Input:
    if item.role not in ROLES:
        raise InputError(f"{item.name}: unknown role {item.role!r}")
    if item.target != ALL_TARGETS and item.target not in TARGETS:
        raise InputError(f"{item.name}: unknown target {item.target!r}")
    if item.size is None:
        raise InputError(f"{source}: {item.name} must pin a size")
    return item


def load_sources(path: Path) -> list[Input]:
    try:
        lock = locks.load_sources(path)
    except LockError as error:
        raise InputError(str(error)) from error
    return [_repository_input(item, str(path)) for item in lock.inputs]


@dataclass(frozen=True)
class BootstrapLock:
    image_index_digest: str
    reference_image: str
    targets: dict[str, tuple[Input, ...]]


def _entry(entry: object, source: str, index: int) -> dict[str, object]:
    if not isinstance(entry, dict):
        raise InputError(f"{source}: entry #{index} is not an object")
    fields: dict[str, object] = {}
    for key, value in entry.items():
        if not isinstance(key, str):
            raise InputError(f"{source}: entry #{index} has a non-string key")
        fields[key] = value
    return fields


def _bootstrap_input(entry: dict[str, object], source: str, index: int) -> Input:
    strings: dict[str, str] = {}
    for field in ("name", "version", "url", "sha256", "role", "target"):
        if field not in entry:
            raise InputError(f"{source}: entry #{index} missing {field}")
        value = entry[field]
        if not isinstance(value, str) or not value:
            raise InputError(f"{entry['name']}: {field} must be a nonempty string")
        strings[field] = value
    if not hashing.is_sha256(strings["sha256"]):
        raise InputError(f"{entry['name']}: sha256 must be lowercase hex")
    size = entry.get("size")
    if size is not None and (type(size) is not int or size < 0):
        raise InputError(f"{entry['name']}: size must be a nonnegative integer")
    license_name = entry.get("license")
    purpose = entry.get("purpose")
    if license_name is not None and not isinstance(license_name, str):
        raise InputError(f"{entry['name']}: license must be a string")
    if purpose is not None and not isinstance(purpose, str):
        raise InputError(f"{entry['name']}: purpose must be a string")
    item = Input(
        name=strings["name"],
        version=strings["version"],
        sha256=strings["sha256"],
        urls=(strings["url"],),
        size=size,
        role=strings["role"],
        target=strings["target"],
        license=license_name,
        purpose=purpose,
    )
    return _repository_input(item, source)


def load_bootstrap(path: Path) -> BootstrapLock:
    path = Path(path)
    try:
        document = locks.load_bootstrap(path)
    except LockError as error:
        raise InputError(str(error)) from error
    reference_image = document.get("reference_image")
    prefix = "debian@sha256:"
    if not isinstance(reference_image, str) or not reference_image.startswith(prefix) or not hashing.is_sha256(reference_image[len(prefix):]):
        raise InputError(f"{path}: reference_image must pin a Debian image index by sha256")
    alpine = document.get("alpine")
    if not isinstance(alpine, dict):
        raise InputError(f"{path}: expected 'alpine' object")
    for field in ("release", "image_index_digest", "image_manifest_reference"):
        if not isinstance(alpine.get(field), str) or not alpine[field]:
            raise InputError(f"{path}: alpine.{field} must be a nonempty string")
    release = re.fullmatch(r"([0-9]+\.[0-9]+)\.[0-9]+", alpine["release"])
    if release is None:
        raise InputError(f"{path}: alpine.release must be a stable patch release")
    stable_repository = f"https://dl-cdn.alpinelinux.org/alpine/v{release[1]}/main"
    if not alpine["image_index_digest"].startswith("sha256:") or not hashing.is_sha256(
        alpine["image_index_digest"].removeprefix("sha256:")
    ):
        raise InputError(f"{path}: alpine.image_index_digest must be a sha256 index digest")
    repositories = alpine.get("repositories")
    if not isinstance(repositories, dict):
        raise InputError(f"{path}: alpine.repositories must be an object")
    for triple in TARGETS:
        if repositories.get(triple) != [stable_repository]:
            raise InputError(f"{path}: alpine.repositories.{triple} must use {stable_repository}")
    targets = document.get("targets")
    if not isinstance(targets, dict):
        raise InputError(f"{path}: expected 'targets' object")
    target_inputs: dict[str, tuple[Input, ...]] = {}
    for triple, section in targets.items():
        if triple not in TARGETS:
            raise InputError(f"{path}: unknown target section {triple}")
        if not isinstance(section, dict):
            raise InputError(f"{path}: target section {triple} is not an object")
        packages = section.get("packages", [])
        if not isinstance(packages, list):
            raise InputError(f"{path}: {triple}.packages must be a list")
        inputs: list[Input] = []
        for index, raw in enumerate(packages):
            entry = _entry(raw, f"{path}:{triple}.packages", index)
            item = _bootstrap_input(entry, f"{path}:{triple}.packages", index)
            if item.target not in (triple, ALL_TARGETS):
                raise InputError(f"{path}: {item.name} target {item.target} is not {triple}")
            filename = f"{item.name}-{item.version}.apk"
            if item.url != f"{stable_repository}/{TARGETS[triple].alpine_arch}/{filename}":
                raise InputError(f"{path}: {item.name} must use the stable APK URL for {triple}")
            inputs.append(item)
        rust = section.get("rust")
        if rust is not None:
            if not isinstance(rust, dict) or not isinstance(rust.get("components"), list):
                raise InputError(f"{path}: {triple}.rust.components must be a list")
            for index, raw in enumerate(rust["components"]):
                entry = _entry(raw, f"{path}:{triple}.rust.components", index)
                if "role" not in entry:
                    entry = {"target": ALL_TARGETS, **entry, "role": "build-source"}
                inputs.append(_bootstrap_input(entry, f"{path}:{triple}.rust.components", index))
        target_inputs[triple] = tuple(inputs)
    return BootstrapLock(
        image_index_digest=alpine["image_index_digest"],
        reference_image=reference_image,
        targets=target_inputs,
    )


def bootstrap_inputs(lock: BootstrapLock, triple: str) -> list[Input]:
    return list(lock.targets.get(triple, ()))


class Cache:
    """Content-addressed cache; every read and every publication is verified."""

    def __init__(self, root: Path, *, offline: bool = False) -> None:
        self.root = Path(root)
        self.offline = offline

    def _object(self, item: Input) -> Path:
        return object_path(self.root, item.sha256)

    def require(self, item: Input) -> Path:
        path = self._object(item)
        if path.is_symlink() or not path.is_file():
            raise InputError(f"{item.name}: absent from cache ({path})")
        try:
            locks.verify_file(path, item)
        except FetchError as error:
            raise InputError(f"cache object {error}") from error
        return path

    def store(self, source: Path, item: Input) -> Path:
        try:
            locks.verify_file(source, item)
        except FetchError as error:
            raise InputError(str(error)) from error
        target = self._object(item)
        try:
            return self.require(item)
        except InputError:
            pass
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".store-", dir=target.parent) as staging:
            temporary = Path(staging) / target.name
            shutil.copyfile(source, temporary)
            try:
                locks.verify_file(temporary, item)
            except FetchError as error:
                raise InputError(f"{item.name}: bytes changed during publication: {error}") from error
            os.replace(temporary, target)
        return self.require(item)

    def fetch(self, item: Input, timeout: float = 120.0) -> Path:
        if self.offline:
            raise InputError(f"{item.name}: offline phase cannot fetch from the network")
        try:
            return self.require(item)
        except InputError:
            pass
        try:
            return locks.fetch_input(item, self._object(item), timeout=timeout)
        except FetchError as error:
            raise InputError(str(error)) from error


def _reject(name: str, reason: str) -> None:
    raise InputError(f"unsafe archive entry ({reason}): {name!r}")


def _check_member(member: tarfile.TarInfo, destination: Path, regular: set[str]) -> None:
    name = member.name
    if not name or Path(name).is_absolute():
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
    elif not member.isdir() and not member.isreg():
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
                record(digest_file(entry)[0])
            else:
                record("special", path)

    visit(root, "")
    return digest.hexdigest()
