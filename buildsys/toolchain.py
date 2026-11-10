"""Pinned LLVM/musl toolchain installation and identity checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .inputs import safe_extract
from .targets import Target

CLANG_VERSION = "clang version 23.1.5"
LLD_VERSION = "LLD 23.1.5"
LLVM_RELEASE = "llvm-musl-23.1.5-dc0d9b9"
LLVM_COMMIT = "dc0d9b96ab4c5ddb11e308303e0129a559f2235d"
TOOLS = (
    "clang",
    "clang++",
    "ld.lld",
    "llvm-ar",
    "llvm-ranlib",
    "llvm-nm",
    "llvm-strip",
    "llvm-objcopy",
    "llvm-objdump",
    "llvm-readelf",
)
PATH_CHECKED = ("clang", "clang++", "ld.lld", "llvm-ar")


class ToolchainError(Exception):
    """The toolchain is absent, misidentified, or shadowed."""


def install(archive: Path, destination: Path) -> Path:
    destination = Path(destination)
    if destination.exists():
        raise ToolchainError(f"{destination}: already exists")
    staging = destination.parent / f".{destination.name}.extract"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        safe_extract(archive, staging)
        entries = list(staging.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            os.replace(entries[0], destination)
        else:
            os.replace(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def _run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=60,
        )
    except OSError as error:
        raise ToolchainError(f"{command[0]}: cannot execute: {error}") from error
    if result.returncode != 0:
        raise ToolchainError(f"{command[0]}: exit {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def verify(toolchain: Path, target: Target, *, environ: dict[str, str] | None = None) -> dict:
    toolchain = Path(toolchain)
    environment = dict(os.environ if environ is None else environ)
    bin_directory = toolchain / "bin"
    if not bin_directory.is_dir():
        raise ToolchainError(f"{toolchain}: missing bin directory")
    report: dict[str, str] = {}
    for name in TOOLS:
        path = bin_directory / name
        if not path.is_file():
            raise ToolchainError(f"{path}: missing")
        if not os.access(path, os.X_OK):
            raise ToolchainError(f"{path}: not executable")
        resolved = path.resolve()
        if toolchain.resolve() not in resolved.parents:
            raise ToolchainError(f"{path}: resolves outside {toolchain} ({resolved})")
        report[name] = str(resolved)
    clang_first = _run([str(bin_directory / "clang"), "--version"], env=environment).splitlines()
    if not clang_first or clang_first[0] != CLANG_VERSION:
        raise ToolchainError(
            f"clang version {clang_first[0] if clang_first else 'missing'!r} != {CLANG_VERSION!r}"
        )
    lld_first = _run([str(bin_directory / "ld.lld"), "--version"], env=environment).splitlines()
    if not lld_first or not lld_first[0].startswith(LLD_VERSION):
        raise ToolchainError(
            f"ld.lld version {lld_first[0] if lld_first else 'missing'!r} != {LLD_VERSION!r}"
        )
    for name in PATH_CHECKED:
        found = shutil.which(name, path=environment.get("PATH"))
        if found is None:
            continue
        resolved = Path(found).resolve()
        if toolchain.resolve() not in resolved.parents:
            raise ToolchainError(
                f"{name} resolves outside the pinned toolchain: {resolved}"
            )
    return {
        "release": LLVM_RELEASE,
        "commit": LLVM_COMMIT,
        "clang": clang_first[0],
        "lld": lld_first[0],
        "target": target.triple,
        "tools": report,
    }


def flags(target: Target, sysroot: Path) -> list[str]:
    return [
        f"--target={target.triple}",
        f"--sysroot={Path(sysroot)}",
        "-fuse-ld=lld",
        "--rtlib=compiler-rt",
        "--unwindlib=libunwind",
    ]


def cxx_flags(target: Target, sysroot: Path) -> list[str]:
    return [*flags(target, sysroot), "-stdlib=libc++"]


def environment(toolchain: Path, target: Target) -> dict[str, str]:
    toolchain = Path(toolchain)
    bin_directory = toolchain / "bin"
    return {
        "CC": str(bin_directory / "clang"),
        "CXX": str(bin_directory / "clang++"),
        "AR": str(bin_directory / "llvm-ar"),
        "RANLIB": str(bin_directory / "llvm-ranlib"),
        "NM": str(bin_directory / "llvm-nm"),
        "STRIP": str(bin_directory / "llvm-strip"),
        "OBJCOPY": str(bin_directory / "llvm-objcopy"),
        "READELF": str(bin_directory / "llvm-readelf"),
        "TARGET": target.triple,
    }
