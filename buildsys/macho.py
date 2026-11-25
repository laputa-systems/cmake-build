"""Audit Mach-O linkage and verify a packaged CMake tree on macOS."""

from __future__ import annotations

import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from .targets import Target


class MachoError(Exception):
    pass


def _run(command: list[str], *, timeout: int = 120) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MachoError(f"{command[0]}: cannot execute: {error}") from error
    if result.returncode != 0:
        raise MachoError(f"{command[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def _otool(binary: Path, *arguments: str) -> str:
    return _run(["otool", *arguments, str(binary)])


def filetype(binary: Path) -> tuple[int, int]:
    output = _otool(binary, "-h")
    match = re.search(r"0x[0-9a-f]+\s+(\d+)\s+\d+\s+0x[0-9a-f]+\s+(\d+)", output)
    if match is None:
        raise MachoError(f"{binary}: not a Mach-O executable")
    return int(match.group(1)), int(match.group(2))


def audit(binary: Path, target: Target, *, build_root: Path | None = None) -> None:
    if target.executable_format != "mach-o":
        raise MachoError(f"{target.triple}: Mach-O audit requires a macOS target")
    if binary.is_symlink() or not binary.is_file():
        raise MachoError(f"{binary}: missing or not a regular file")
    cputype, filetype_value = filetype(binary)
    if cputype != 0x0100000C:
        raise MachoError(f"{binary}: cputype {cputype:#x} is not CPU_TYPE_ARM64")
    if filetype_value != 2:
        raise MachoError(f"{binary}: filetype {filetype_value} is not MH_EXECUTE")
    load = _otool(binary, "-L")
    dependencies = []
    for line in load.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"(\S+)\s", line)
        if match is None:
            raise MachoError(f"{binary}: unparseable load command {line!r}")
        dependencies.append(match.group(1))
    for name in dependencies:
        if name.startswith(("@rpath/", "@loader_path/", "@executable_path/")):
            raise MachoError(f"{binary}: non-system load path {name}")
        if not name.startswith(("/usr/lib/", "/System/Library/")):
            raise MachoError(f"{binary}: non-system dynamic dependency {name}")
    headers = _otool(binary, "-l")
    if "LC_RPATH" in headers:
        raise MachoError(f"{binary}: contains LC_RPATH")
    version = re.search(r"LC_BUILD_VERSION.*?minos (\d+)\.(\d+)", headers, re.DOTALL)
    if version is None:
        raise MachoError(f"{binary}: lacks LC_BUILD_VERSION")
    minos = (int(version.group(1)), int(version.group(2)))
    floor = tuple(int(part) for part in target.deployment_target.split("."))[:2]
    if minos != floor:
        raise MachoError(f"{binary}: minos {minos[0]}.{minos[1]} does not match deployment target {target.deployment_target}")
    symbols = _run(["nm", "-gU", str(binary)])
    if re.search(r"(?m)\b(?:OPENSSL_|SSL_|EVP_|BIO_|X509_|CRYPTO_|PEM_|ASN1_|ERR_get_error|ERR_error_string|ERR_peek_error|ERR_clear_error)[A-Za-z0-9_]*$", symbols):
        raise MachoError(f"{binary} contains OpenSSL API symbols")
    strings = _run(["strings", "-a", str(binary)])
    if re.search(r"/Users/|/home/|\.work/|/src/\.work", strings):
        raise MachoError(f"{binary} contains a build-host path")
    if build_root is not None:
        root_text = str(build_root)
        if root_text != "/" and root_text in strings:
            raise MachoError(f"{binary} contains the build root path")
    version_identifiers = {"openssl", "openssl/", "archive_openssl_version"}
    for line in strings.splitlines():
        remaining = re.sub(r"openssl[_-]probe|try_init_openssl_env_vars", "", line, flags=re.IGNORECASE)
        if "openssl" in remaining.lower() and line.lower() not in version_identifiers:
            raise MachoError(f"{binary} contains unapproved OpenSSL text")
    if re.search(r"(?m)\b(?:lib(?:gcc(?:_s)?|stdc\+\+|ssl|crypto))\.(?:so|a|dylib)", strings):
        raise MachoError(f"{binary} contains an unapproved runtime or OpenSSL library")


def audit_tree(root: Path, target: Target, *, build_root: Path | None = None) -> None:
    for name in ("cmake", "ctest", "cpack"):
        audit(Path(root) / "bin" / name, target, build_root=build_root)


def _safe_link(name: str, target: str) -> None:
    if not target or target.startswith("/"):
        raise MachoError(f"unsafe symlink {name}: {target}")
    parents = list(PurePosixPath(name).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == "..":
            if not parents:
                raise MachoError(f"escaping symlink {name}: {target}")
            parents.pop()
        else:
            parents.append(part)


def _extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        tops: set[str] = set()
        for member in members:
            name = member.name
            parts = name.split("/")
            if name.startswith("/") or ".." in parts or not name:
                raise MachoError(f"unsafe archive member: {name!r}")
            if member.issym():
                _safe_link(name, member.linkname)
            elif member.islnk():
                raise MachoError(f"archive member is a hard link: {name!r}")
            elif not (member.isdir() or member.isreg()):
                raise MachoError(f"unsupported archive member: {name!r}")
            tops.add(parts[0])
        tops.discard("")
        if len(tops) != 1:
            raise MachoError("archive members do not share a single top-level directory")
        tar.extractall(destination, filter="data")
    top = destination / next(iter(tops))
    if not top.is_dir():
        raise MachoError("archive top-level entry is not a directory")
    return top


def verify_prefix(prefix: Path, target: Target, *, version: str,
                  build_root: Path | None = None, scratch: Path | None = None) -> dict[str, str]:
    prefix = Path(prefix)
    audit_tree(prefix, target, build_root=build_root)
    cmake = prefix / "bin" / "cmake"
    output = _run([str(cmake), "--version"])
    if not output.splitlines() or output.splitlines()[0] != f"cmake version {version}":
        raise MachoError(f"packaged CMake reports {output.splitlines()[:1]!r}, expected {version}")
    work = Path(scratch) if scratch is not None else Path(tempfile.mkdtemp(prefix="macho-hello-"))
    project = work / "hello"
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "main.c").write_text('#include <stdio.h>\nint main(void) { puts("hello"); return 0; }\n')
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(hello C)\nadd_executable(hello src/main.c)\n"
    )
    build = project / "build"
    _run([str(cmake), "-S", str(project), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"])
    _run([str(cmake), "--build", str(build), "--parallel", str(os.cpu_count() or 1)])
    hello = build / "hello"
    if not hello.is_file():
        raise MachoError("hello-world build did not produce an executable")
    audit(hello, target)
    result = _run([str(hello)])
    if result.strip() != "hello":
        raise MachoError(f"hello-world executable printed {result.strip()!r}")
    return {
        "version": output.splitlines()[0],
        "hello": result.strip(),
    }


def verify(archive: Path, target: Target, *, version: str, build_root: Path | None = None) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="macho-verify-") as temporary:
        root = _extract(Path(archive), Path(temporary) / "tree")
        return verify_prefix(root / "usr", target, version=version,
                             build_root=build_root, scratch=Path(temporary))


def strip_debug(binary: Path, destination: Path, target: Target, tools: Path) -> None:
    if binary.resolve() == destination.resolve():
        raise MachoError("stripping requires a separate destination")
    try:
        _run([str(Path(tools) / "llvm-strip"), "--strip-debug", "-o", str(destination), str(binary)])
        audit(destination, target)
    except (MachoError, OSError):
        destination.unlink(missing_ok=True)
        raise
