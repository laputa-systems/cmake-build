"""Build the upstream bootstrap CMake and the locked build executors."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from .inputs import safe_extract
from .targets import Target
from .rust import _run as run_process
from . import toolchain


class BootstrapError(Exception):
    pass


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    run_process(command, cwd=cwd, env=env)


def _source(archive: Path, destination: Path) -> Path:
    safe_extract(archive, destination)
    entries = list(destination.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise BootstrapError(f"{archive}: expected one source directory")
    return entries[0]


def build(cmake_archive: Path, samurai_archive: Path, ninja_archive: Path, directory: Path, tc: Path, sysroot: Path, target: Target) -> None:
    flags = toolchain.flags(target, sysroot)
    env = {**os.environ, **toolchain.environment(tc, target)}
    env["CFLAGS"] = shlex.join(flags)
    env["CXXFLAGS"] = shlex.join(toolchain.cxx_flags(target, sysroot))
    env["LDFLAGS"] = shlex.join(flags)
    jobs = str(os.process_cpu_count() or 1)
    samurai = _source(samurai_archive, directory / "samurai")
    _run(["make", f"-j{jobs}", f"CC={shlex.join([str(tc / 'bin/clang'), *flags])}"], samurai, env)
    source = _source(cmake_archive, directory / "source")
    bootstrap_directory = directory / "bootstrap"
    bootstrap_directory.mkdir()
    _run([str(source / "bootstrap"), f"--parallel={jobs}", "--no-system-libs", "--", "-DCMAKE_USE_OPENSSL=OFF", f"-DCMAKE_SYSROOT={sysroot}"], bootstrap_directory, env)
    _run(["make", f"-j{jobs}", "cmake"], bootstrap_directory, env)
    file = directory / "toolchain.cmake"
    file.write_text(
        f'set(CMAKE_C_COMPILER "{tc / "bin/clang"}")\n'
        f'set(CMAKE_CXX_COMPILER "{tc / "bin/clang++"}")\n'
        f'set(CMAKE_AR "{tc / "bin/llvm-ar"}")\n'
        f'set(CMAKE_RANLIB "{tc / "bin/llvm-ranlib"}")\n'
        f'set(CMAKE_NM "{tc / "bin/llvm-nm"}")\n'
        f'set(CMAKE_STRIP "{tc / "bin/llvm-strip"}")\n'
        f'set(CMAKE_OBJCOPY "{tc / "bin/llvm-objcopy"}")\n'
        f'set(CMAKE_READELF "{tc / "bin/llvm-readelf"}")\n'
        f'set(CMAKE_LINKER "{tc / "bin/ld.lld"}")\n'
        f'set(CMAKE_SYSROOT "{sysroot}")\n'
        f'set(CMAKE_C_FLAGS_INIT "{shlex.join([*flags, "-fstack-protector-strong", "-fstack-clash-protection"])}")\n'
        f'set(CMAKE_CXX_FLAGS_INIT "{shlex.join([*toolchain.cxx_flags(target, sysroot), "-fstack-protector-strong", "-fstack-clash-protection"])}")\n'
        f'set(CMAKE_EXE_LINKER_FLAGS_INIT "-static-pie -Wl,-z,relro,-z,now,-z,noexecstack")\n'
    )
    ninja = _source(ninja_archive, directory / "ninja-source")
    ninja_build = directory / "ninja-build"
    _run([
        str(bootstrap_directory / "bin/cmake"), "-S", str(ninja), "-B", str(ninja_build),
        "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={samurai / 'samu'}",
        f"-DCMAKE_TOOLCHAIN_FILE={file}", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
    ], directory, env)
    _run([str(samurai / "samu"), "-C", str(ninja_build), f"-j{jobs}"], directory, env)


def configure(bootstrap_directory: Path, directory: Path, tc: Path, target: Target) -> None:
    source = next((bootstrap_directory / "source").iterdir())
    ninja = bootstrap_directory / "ninja-build/ninja"
    file = bootstrap_directory / "toolchain.cmake"
    env = {**os.environ, **toolchain.environment(tc, target)}
    _run([
        str(bootstrap_directory / "bootstrap/bin/cmake"), "-S", str(source), "-B", str(directory),
        "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_TOOLCHAIN_FILE={file}", "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_USE_OPENSSL=OFF", "-DBUILD_CursesDialog=OFF", "-DBUILD_QtDialog=OFF",
        "-DCMAKE_USE_SYSTEM_LIBRARIES=OFF", "-DCMake_ENABLE_DEBUGGER=ON",
    ], directory, env)
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/native"
    _run([
        str(bootstrap_directory / "bootstrap/bin/cmake"), "-S", str(fixture), "-B", str(directory / "native-check"),
        f"-DCMAKE_TOOLCHAIN_FILE={file}",
    ], directory, env)
