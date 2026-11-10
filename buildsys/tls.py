"""Checks for the selected Rustls dependency closure."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .rust import RustError, _run


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
    cargo = cargo.resolve()
    manifest = manifest.resolve()
    command = [
        str(cargo), "tree", "--manifest-path", str(manifest), "--locked", "--offline",
        "--no-default-features", "--features", "graviola", "--target", target,
        "-e", "normal", "--prefix", "none", "--format", "{p}",
    ]
    try:
        output = _run(command, cwd=manifest.parent, env=env)
    except RustError as error:
        raise TlsError(str(error)) from error
    check_tree(output)


def check_vendored(vendored: Path, tools: Path, target: str, scratch: Path) -> None:
    projects = list((vendored / "source").iterdir())
    if len(projects) != 1 or not projects[0].is_dir():
        raise TlsError("vendored Rustls source has an invalid layout")
    with tempfile.TemporaryDirectory(prefix="cargo-check-", dir=scratch) as temporary:
        cargo_home = Path(temporary)
        (cargo_home / "config.toml").write_text(
            '[source.crates-io]\nreplace-with = "vendored-sources"\n'
            '[source.vendored-sources]\ndirectory = ' + json.dumps(str(vendored / "vendor")) + '\n'
        )
        env = {**os.environ, "CARGO_HOME": str(cargo_home), "TMPDIR": str(scratch),
               "RUSTC_WRAPPER": "", "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}"}
        check_dependencies(tools / "cargo", projects[0] / "Cargo.toml", target, env)
