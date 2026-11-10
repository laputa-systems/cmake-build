"""Checks for the selected Rustls dependency closure."""

from __future__ import annotations

import subprocess
from pathlib import Path


class TlsError(Exception):
    pass


def check_tree(tree: str) -> None:
    packages = {line.split()[0] for line in tree.splitlines() if line.strip()}
    required = {"rustls-ffi", "rustls-graviola", "graviola"}
    forbidden = {"ring", "aws-lc-rs", "aws-lc-sys", "openssl", "openssl-sys", "native-tls"}
    missing = required - packages
    present = forbidden & packages
    if missing or present:
        raise TlsError(f"TLS dependency closure: missing {sorted(missing)}, forbidden {sorted(present)}")


def check_dependencies(cargo: Path, manifest: Path, target: str, env: dict[str, str]) -> None:
    command = [
        str(cargo), "tree", "--manifest-path", str(manifest), "--locked", "--offline",
        "--no-default-features", "--features", "graviola", "--target", target,
        "-e", "normal", "--prefix", "none", "--format", "{p}",
    ]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if result.returncode:
        raise TlsError(f"cargo tree failed ({result.returncode}): {result.stderr.strip()}")
    check_tree(result.stdout)
