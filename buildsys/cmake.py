"""Build the locked CMake source with the verified Rustls backend."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path
from enum import Enum

from . import dependencies, elf, patches, toolchain
from .rust import _run
from .targets import Target


class BuildMode(Enum):
    DEVELOPMENT = "development"
    QUALIFICATION = "qualification"


class CMakeBuildError(Exception):
    pass


def check_capabilities(output: str, expected_version: str) -> None:
    try:
        capabilities = json.loads(output)
    except (ValueError, TypeError) as error:
        raise CMakeBuildError("CMake capabilities are not valid JSON") from error
    if not isinstance(capabilities, dict) or not isinstance(capabilities.get("version"), dict):
        raise CMakeBuildError("CMake capabilities lack a version")
    if capabilities["version"].get("string") != expected_version:
        raise CMakeBuildError(f"CMake version does not match {expected_version}")
    if capabilities.get("tls") is not True or capabilities.get("debugger") is not True:
        raise CMakeBuildError("CMake must include TLS and the debugger")


def build(*, bootstrap: Path, prepared: Path, archive: Path, inventory: tuple[patches.Patch, ...],
          directory: Path, target: Target, cmake_version: str, rustls_version: str, mode: BuildMode,
          kache: Path, compiler_cache: Path) -> None:
    entries = list((bootstrap / "source").iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise CMakeBuildError("bootstrap source has an invalid layout")
    source = directory / "source"
    shutil.copytree(entries[0], source, symlinks=True)
    tc = prepared / "toolchain"
    env = {key: value for key, value in os.environ.items() if key not in {"CFLAGS", "CXXFLAGS", "LDFLAGS"}}
    env.update(toolchain.environment(tc, target))
    for item in inventory:
        if item.name.startswith("rustls-ffi/"):
            continue
        with tempfile.NamedTemporaryFile(prefix="patch-", suffix=".patch", dir=directory) as patch_file:
            patch_file.write(item.content)
            patch_file.flush()
            _run(["patch", "--batch", "--forward", "-p1", "-i", patch_file.name], cwd=source, env=env)
    evidence = directory / "link-evidence.cmake"
    evidence.write_text(
        "function(cmake_build_link_evidence)\n"
        "  foreach(tool cmake ctest cpack)\n"
        "    if(NOT TARGET ${tool})\n"
        '      message(FATAL_ERROR "${tool} target is missing")\n'
        "    endif()\n"
        '    target_link_options(${tool} PRIVATE "LINKER:--gc-sections" "LINKER:-Map,${CMAKE_BINARY_DIR}/${tool}.map" "LINKER:--why-extract=${CMAKE_BINARY_DIR}/${tool}.extract")\n'
        f'    set_property(TARGET ${{tool}} PROPERTY RULE_LAUNCH_LINK "python3 -m buildsys.elf {shlex.quote(str(tc / "bin"))}")\n'
        "  endforeach()\n"
        "endfunction()\n"
        "if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)\n"
        "  cmake_language(DEFER CALL cmake_build_link_evidence)\n"
        "endif()\n"
    )
    build_tree = directory / "build"
    graph = directory / "dependencies.dot"
    ninja = bootstrap / "ninja-build/ninja"
    standard_libraries = f"-L{tc / 'lib'} -lunwind -ldl -lm -lpthread"
    command = [
        "/usr/bin/cmake", f"--graphviz={graph}", "-S", str(source), "-B", str(build_tree),
        "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}", f"-DCMAKE_TOOLCHAIN_FILE={bootstrap / 'toolchain.cmake'}",
        f"-DCMAKE_PROJECT_INCLUDE={evidence}", "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_FLAGS_RELEASE={shlex.join(['-O3', '-DNDEBUG', f'-ffile-prefix-map={source}=/usr/src/cmake'])}",
        f"-DCMAKE_CXX_FLAGS_RELEASE={shlex.join(['-O3', '-DNDEBUG', f'-ffile-prefix-map={source}=/usr/src/cmake'])}",
        "-DBUILD_CursesDialog=OFF", "-DBUILD_QtDialog=OFF", "-DCMAKE_USE_SYSTEM_LIBRARIES=OFF",
        "-DCMake_ENABLE_DEBUGGER=ON", "-DCMAKE_USE_OPENSSL=OFF", "-DCURL_USE_RUSTLS=ON", "-DCURL_USE_LIBPSL=OFF",
        "-DCURL_CA_BUNDLE=none", "-DCURL_CA_PATH=none", f"-DRUSTLS_VERSION={rustls_version}",
        f"-DRUSTLS_INCLUDE_DIR={archive.parents[3] / 'source/src'}", f"-DRUSTLS_LIBRARY={archive}",
        f"-DCMAKE_C_STANDARD_LIBRARIES={standard_libraries}", f"-DCMAKE_CXX_STANDARD_LIBRARIES={standard_libraries}",
    ]
    if mode is BuildMode.DEVELOPMENT:
        compiler_cache.mkdir(parents=True, exist_ok=True)
        env.update({"XDG_CACHE_HOME": str(compiler_cache), "XDG_CONFIG_HOME": str(compiler_cache / "config"),
                    "KACHE_CC_PATH_NORMALIZE": "0", "KACHE_CC_SOURCE_DATE_EPOCH": "passthrough"})
        link_flags = {"-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=libunwind"}
        compile_flags = [flag for flag in toolchain.flags(target, prepared / "sysroot") if flag not in link_flags]
        hardening = ["-fstack-protector-strong", "-fstack-clash-protection"]
        link_driver = [flag for flag in toolchain.flags(target, prepared / "sysroot") if flag in link_flags]
        executable_link = [*link_driver, "-static-pie", "-Wl,-z,relro,-z,now,-z,noexecstack"]
        command.extend([
            f"-DCMAKE_C_COMPILER_LAUNCHER={kache}", f"-DCMAKE_CXX_COMPILER_LAUNCHER={kache}",
            f"-DCMAKE_C_FLAGS={shlex.join([*compile_flags, *hardening])}",
            f"-DCMAKE_CXX_FLAGS={shlex.join([*compile_flags, '-stdlib=libc++', *hardening])}",
            f"-DCMAKE_EXE_LINKER_FLAGS={shlex.join(executable_link)}",
            f"-DCMAKE_SHARED_LINKER_FLAGS={shlex.join(link_driver)}",
            f"-DCMAKE_MODULE_LINKER_FLAGS={shlex.join(link_driver)}",
        ])
    elif mode is not BuildMode.QUALIFICATION:
        raise CMakeBuildError(f"unsupported build mode: {mode!r}")
    command.extend(f"-DSPHINX_{name}=OFF" for name in (
        "INFO", "MAN", "HTML", "SINGLEHTML", "LINKCHECK", "QTHELP", "LATEXPDF", "TEXT", "INCLUDE_IN_ALL",
    ))
    _run(command, cwd=directory, env=env)
    _run([str(ninja), "-C", str(build_tree), f"-j{os.process_cpu_count() or 1}"], cwd=directory, env=env)
    executable = build_tree / "bin/cmake"
    version_output = _run([str(executable), "--version"], cwd=directory, env=env)
    if not version_output.splitlines() or version_output.splitlines()[0] != f"cmake version {cmake_version}":
        raise CMakeBuildError(f"built CMake does not report version {cmake_version}")
    check_capabilities(_run([str(executable), "-E", "capabilities"], cwd=directory, env=env), cmake_version)
    for name in ("cmake", "ctest", "cpack"):
        elf.audit(build_tree / "bin" / name, target, tc / "bin")
        extract = build_tree / f"{name}.extract"
        if not extract.is_file() or not extract.read_text().startswith("reference\textracted\tsymbol\n"):
            raise CMakeBuildError(f"linker did not produce archive extraction evidence for {name}")
    link_map = build_tree / "cmake.map"
    (directory / "dependencies.md").write_text(
        dependencies.inventory(source, graph, link_map, cmake_version, rustls_version)
    )
