"""P3 sysroot: musl headers, Linux UAPI headers, and one link-time loader."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .inputs import digest_bytes, safe_extract
from .targets import Target


class SysrootError(Exception):
    """The sysroot could not be built or does not match the target."""


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    if result.returncode != 0:
        raise SysrootError(
            f"{' '.join(command)} failed ({result.returncode}):\n"
            f"{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
        )


def elf_machine(path: Path) -> int:
    data = Path(path).read_bytes()[:20]
    if len(data) < 20 or data[:4] != b"\x7fELF":
        raise SysrootError(f"{path}: not an ELF file")
    order = "little" if data[5] == 1 else "big"
    return int.from_bytes(data[18:20], order)


def check_machine(path: Path, target: Target) -> None:
    found = elf_machine(path)
    if found != target.elf_machine:
        raise SysrootError(
            f"{path}: e_machine {found} != {target.elf_machine} for {target.triple}"
        )


def _readelf(toolchain: Path, *arguments: str) -> str:
    result = subprocess.run(
        [str(Path(toolchain) / "bin" / "llvm-readelf"), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise SysrootError(f"llvm-readelf {' '.join(arguments)}: {result.stderr.strip()}")
    return result.stdout


def _soname(toolchain: Path, path: Path) -> str:
    output = _readelf(toolchain, "-d", str(path))
    match = re.search(r"\(SONAME\)\s+Library soname: \[([^\]]+)\]", output)
    if not match:
        raise SysrootError(f"{path}: no SONAME")
    return match.group(1)


def _comment(toolchain: Path, path: Path) -> list[str]:
    output = _readelf(toolchain, "-p", ".comment", str(path))
    return [line.split("] ", 1)[1].strip() for line in output.splitlines() if "] " in line]


def build(
    musl_archive: Path,
    linux_headers_apk: Path,
    toolchain: Path,
    target: Target,
    destination: Path,
    work: Path,
) -> Path:
    destination = Path(destination)
    work = Path(work)
    toolchain = Path(toolchain)
    if destination.exists():
        raise SysrootError(f"{destination}: already exists")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    source = work / "musl"
    safe_extract(musl_archive, source)
    entries = list(source.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        root = entries[0]
    else:
        root = source
    bin_directory = toolchain / "bin"
    clang = bin_directory / "clang"
    libcc = subprocess.run(
        [str(clang), "-print-libgcc-file-name"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()
    if not Path(libcc).is_file():
        raise SysrootError(f"clang printed a missing compiler runtime: {libcc}")
    environment = {
        **os.environ,
        "CC": f"{clang} --target={target.triple}",
        "AR": str(bin_directory / "llvm-ar"),
        "RANLIB": str(bin_directory / "llvm-ranlib"),
        "NM": str(bin_directory / "llvm-nm"),
        "LIBCC": libcc,
    }
    jobs = str(max(1, min(8, os.cpu_count() or 1)))
    _run(
        [str(root / "configure"), f"--target={target.machine}", "--prefix=/usr"],
        cwd=root,
        env=environment,
    )
    destination.mkdir(parents=True)
    _run(
        ["make", f"-j{jobs}", "install-headers", f"DESTDIR={destination}"],
        cwd=root,
        env=environment,
    )
    _run(
        [
            "make",
            f"-j{jobs}",
            "lib/libc.so",
            f"LDFLAGS=-Wl,-soname,libc.musl-{target.machine}.so.1",
        ],
        cwd=root,
        env=environment,
    )
    loader = destination / target.musl_loader.lstrip("/")
    loader.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "lib" / "libc.so", loader)
    loader.chmod(0o755)
    headers = work / "linux-headers"
    safe_extract(linux_headers_apk, headers)
    source_headers = headers / "usr" / "include"
    if not source_headers.is_dir():
        raise SysrootError(f"{linux_headers_apk}: no usr/include tree")
    shutil.copytree(
        source_headers, destination / "usr" / "include", dirs_exist_ok=True
    )
    for required in ("stdio.h", "linux/fs.h", "asm/unistd.h"):
        if not (destination / "usr" / "include" / required).is_file():
            raise SysrootError(f"{destination}: missing header {required}")
    check_machine(loader, target)
    expected_soname = f"libc.musl-{target.machine}.so.1"
    soname = _soname(toolchain, loader)
    if soname != expected_soname:
        raise SysrootError(f"{loader}: SONAME {soname!r} != {expected_soname!r}")
    comments = _comment(toolchain, loader)
    if any(comment.startswith("GCC:") for comment in comments):
        raise SysrootError(f"{loader}: GCC compiled into the loader: {comments}")
    if not comments:
        raise SysrootError(f"{loader}: missing .comment provenance")
    shutil.rmtree(work, ignore_errors=True)
    return destination


def trace_paths(text: str) -> list[str]:
    paths = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("/"):
            continue
        paths.append(line.split("(", 1)[0].strip())
    return paths


def check_link_trace(
    trace: str, toolchain: Path, sysroot: Path, work: Path, target: Target
) -> None:
    toolchain = Path(toolchain).resolve()
    sysroot = Path(sysroot).resolve()
    work = Path(work).resolve()
    loader = (sysroot / target.musl_loader.lstrip("/")).resolve()
    for raw in trace_paths(trace):
        try:
            resolved = Path(raw).resolve()
        except OSError as error:
            raise SysrootError(f"cannot resolve link input {raw}: {error}") from error
        if resolved == loader:
            continue
        if sysroot in resolved.parents:
            raise SysrootError(f"{raw}: resolved from the sysroot")
        if toolchain in resolved.parents:
            continue
        if work in resolved.parents:
            continue
        raise SysrootError(f"{raw}: resolved outside the pinned toolchain")


def verify(destination: Path, target: Target, toolchain: Path) -> dict:
    destination = Path(destination)
    loader = destination / target.musl_loader.lstrip("/")
    if not loader.is_file():
        raise SysrootError(f"{loader}: missing loader")
    check_machine(loader, target)
    return {
        "root": str(destination),
        "loader": str(loader),
        "loader_sha256": digest_bytes(loader)[0],
        "soname": _soname(toolchain, loader),
        "comment": _comment(toolchain, loader),
    }
