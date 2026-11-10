"""Content-fingerprinted phase records with crash-consistent completion."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .inputs import canonical_json, identity, tree_digest

RECORD = "phase.json"
STATE = "state.json"
SCHEMA_VERSION = 1


class PhaseError(Exception):
    """A phase record is unreadable or inconsistent with its inputs."""


@dataclass(frozen=True)
class PhaseResult:
    name: str
    fingerprint: str
    status: str
    reused: bool
    directory: Path


class PhaseCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def directory(self, name: str) -> Path:
        return self.root / name

    def fingerprint(self, name: str, inputs: Mapping[str, str]) -> str:
        if not name or "/" in name or name.startswith("."):
            raise PhaseError(f"invalid phase name {name!r}")
        if not inputs:
            raise PhaseError(f"{name}: a phase needs at least one input")
        for key, value in inputs.items():
            if not isinstance(key, str) or not key:
                raise PhaseError(f"{name}: invalid input name {key!r}")
            if not isinstance(value, str) or len(value) != 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise PhaseError(f"{name}: {key} must be a sha256 digest")
        material = {"phase": name, "inputs": dict(sorted(inputs.items()))}
        return identity(canonical_json(material).encode())

    def _record_path(self, name: str) -> Path:
        return self.directory(name) / RECORD

    def _read(self, path: Path) -> dict | None:
        if not path.is_file():
            return None
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(document, dict):
            return None
        if document.get("schema_version") != SCHEMA_VERSION:
            return None
        return document

    def status(self, name: str) -> str:
        directory = self.directory(name)
        if not directory.exists():
            return "absent"
        if self._read(directory / STATE) is not None:
            return "interrupted"
        record = self._read(self._record_path(name))
        return "complete" if record is not None else "incomplete"

    def run(
        self,
        name: str,
        inputs: Mapping[str, str],
        action: Callable[[Path], None],
    ) -> PhaseResult:
        fingerprint = self.fingerprint(name, inputs)
        directory = self.directory(name)
        record = self._read(self._record_path(name))
        if (
            record is not None
            and record.get("fingerprint") == fingerprint
            and record.get("inputs") == dict(sorted(inputs.items()))
            and record.get("output_digest") == tree_digest(directory, exclude={RECORD, STATE})
        ):
            return PhaseResult(name, fingerprint, "complete", True, directory)

        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)
        _write_json(
            directory / STATE,
            {
                "schema_version": SCHEMA_VERSION,
                "phase": name,
                "fingerprint": fingerprint,
                "status": "running",
            },
        )
        try:
            action(directory)
        except BaseException:
            _write_json(
                directory / STATE,
                {
                    "schema_version": SCHEMA_VERSION,
                    "phase": name,
                    "fingerprint": fingerprint,
                    "status": "interrupted",
                },
            )
            raise
        output_digest = tree_digest(directory, exclude={RECORD, STATE})
        _write_json(
            directory / RECORD,
            {
                "schema_version": SCHEMA_VERSION,
                "phase": name,
                "fingerprint": fingerprint,
                "inputs": dict(sorted(inputs.items())),
                "output_digest": output_digest,
            },
        )
        (directory / STATE).unlink(missing_ok=True)
        return PhaseResult(name, fingerprint, "complete", False, directory)


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)
