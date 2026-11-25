"""Native macOS build for aarch64-apple-darwin: pinned LLVM, Xcode SDK, Rustls."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

from . import licenses, macho, patches, rust, stage
from .inputs import (
    BootstrapLock,
    Cache,
    Input,
    bootstrap_inputs,
    canonical_json,
    digest_file,
    identity,
    load_bootstrap,
    load_sources,
    safe_extract,
    tree_digest,
)
from .phases import PhaseCache
from .rust import _run
from .targets import Target

LLVM_ARCHIVE_ROOT = "LLVM-23.1.4-macOS-ARM64"
LLVM_CLANG_VERSION = (
    "clang version 23.1.4 "
    "(https://github.com/llvm/llvm-project 7a941dfb2877a0b8cf30323fefa85ad019e0b0f5)"
)
LLVM_BINARIES = (
    "clang-23",
    "clang",
    "clang++",
    "llvm-ar",
    "llvm-ranlib",
    "llvm-nm",
    "llvm-objcopy",
    "llvm-strip",
    "llvm-readobj",
)
BOOTSTRAP_CMAKE_VERSION = "4.4.5"
RUST_COMPONENTS = {"cargo", "rustc", "rust-std", "rust-src"}


class DarwinError(Exception):
    pass


def _require_host(target: Target) -> None:
    if target.executable_format != "mach-o":
        raise DarwinError(f"{target.triple} is not a macOS target")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise DarwinError(
            f"{target.triple} builds natively on macOS arm64 only; "
            f"this host is {platform.system()} {platform.machine()}"
        )


def sdk() -> dict[str, str]:
    path = _run(["xcrun", "--show-sdk-path"], cwd=Path.cwd(), env=dict(os.environ)).strip()
    version = _run(["xcrun", "--show-sdk-version"], cwd=Path.cwd(), env=dict(os.environ)).strip()
    if not Path(path).is_dir() or not path.endswith(".sdk"):
        raise DarwinError(f"xcrun reported an invalid SDK path: {path!r}")
    return {"path": path, "version": version}


def _selected(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    if not parts:
        return False
    if len(parts) == 2 and parts[0] == "bin" and parts[1] in LLVM_BINARIES:
        return True
    if relative == "lib/libLTO.dylib":
        return True
    return parts[0] == "lib" and len(parts) > 1 and parts[1] == "clang"


def _install_llvm(archive: Path, destination: Path) -> Path:
    destination = Path(destination)
    if destination.exists():
        raise DarwinError(f"{destination}: already exists")
    staging = destination.parent / f".{destination.name}.extract"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        prefix = PurePosixPath(LLVM_ARCHIVE_ROOT).parts[0]
        with tarfile.open(archive, "r|xz") as tar:
            for member in tar:
                name = PurePosixPath(member.name)
                if name.is_absolute() or any(part in ("", ".", "..") for part in name.parts):
                    raise DarwinError(f"unsafe LLVM archive member: {member.name!r}")
                if not name.parts or name.parts[0] != prefix:
                    continue
                relative = PurePosixPath(*name.parts[1:])
                text = relative.as_posix()
                if text == "." or not _selected(text):
                    continue
                target = staging / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if member.issym():
                    link = member.linkname
                    if PurePosixPath(link).is_absolute() or ".." in PurePosixPath(link).parts:
                        raise DarwinError(f"unsafe LLVM symlink: {member.name!r} -> {link!r}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink() or target.exists():
                        target.unlink()
                    os.symlink(link, target)
                    continue
                if not member.isreg():
                    raise DarwinError(f"unsupported LLVM archive member: {member.name!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tar.extractfile(member)
                if source is None:
                    raise DarwinError(f"unreadable LLVM archive member: {member.name!r}")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                os.chmod(target, member.mode & 0o777)
        if not (staging / "bin" / "clang-23").is_file():
            raise DarwinError(f"{archive}: unexpected LLVM layout")
        os.replace(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def verify_toolchain(toolchain: Path, target: Target, scratch: Path) -> dict[str, object]:
    toolchain = Path(toolchain)
    binaries = toolchain / "bin"
    if not binaries.is_dir():
        raise DarwinError(f"{toolchain}: missing bin directory")
    names = ("clang", "clang++", "llvm-ar", "llvm-ranlib", "llvm-nm",
             "llvm-objcopy", "llvm-strip", "llvm-readobj")
    for name in names:
        path = binaries / name
        if not path.exists():
            raise DarwinError(f"{path}: missing")
        resolved = path.resolve()
        if resolved != toolchain.resolve() and toolchain.resolve() not in resolved.parents:
            raise DarwinError(f"{path}: resolves outside {toolchain} ({resolved})")
        if not os.access(path, os.X_OK):
            raise DarwinError(f"{path}: not executable")
    for name in ("clang", "clang++"):
        first = _run([str(binaries / name), "--version"], cwd=toolchain, env=dict(os.environ)).splitlines()
        if not first or first[0] != LLVM_CLANG_VERSION:
            raise DarwinError(
                f"{name} version {first[0] if first else 'missing'!r} != {LLVM_CLANG_VERSION!r}"
            )
    sdk_root = sdk()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tc-probe-", dir=scratch) as temporary:
        probe = Path(temporary)
        source = probe / "probe.cpp"
        source.write_text(
            "#include <filesystem>\n#include <cstdio>\n"
            "int main() { std::printf(\"%s\\n\", std::filesystem::current_path().c_str()); return 0; }\n"
        )
        executable = probe / "probe"
        _run([
            str(binaries / "clang++"), "-isysroot", sdk_root["path"],
            "-std=c++17", "-O2", str(source), "-o", str(executable),
        ], cwd=probe, env=dict(os.environ))
        output = _run([str(executable)], cwd=probe, env=dict(os.environ)).strip()
        if output != str(probe):
            raise DarwinError(f"toolchain probe printed {output!r}")
    return {
        "release": LLVM_ARCHIVE_ROOT,
        "clang": LLVM_CLANG_VERSION,
        "target": target.triple,
        "sdk_path": sdk_root["path"],
        "sdk_version": sdk_root["version"],
        "tools": {name: str((binaries / name).resolve()) for name in names},
    }


def environment(toolchain: Path) -> dict[str, str]:
    binaries = Path(toolchain) / "bin"
    return {
        "CC": str(binaries / "clang"),
        "CXX": str(binaries / "clang++"),
        "AR": str(binaries / "llvm-ar"),
        "RANLIB": str(binaries / "llvm-ranlib"),
        "NM": str(binaries / "llvm-nm"),
        "STRIP": str(binaries / "llvm-strip"),
        "OBJCOPY": str(binaries / "llvm-objcopy"),
    }


def _toolchain_file(toolchain: Path, sdk_root: dict[str, str], target: Target) -> str:
    binaries = Path(toolchain) / "bin"
    compile_flags = f"{target.cpu_baseline_cflag} -fstack-protector-strong"
    return (
        f'set(CMAKE_C_COMPILER "{binaries / "clang"}")\n'
        f'set(CMAKE_CXX_COMPILER "{binaries / "clang++"}")\n'
        f'set(CMAKE_AR "{binaries / "llvm-ar"}")\n'
        f'set(CMAKE_RANLIB "{binaries / "llvm-ranlib"}")\n'
        f'set(CMAKE_NM "{binaries / "llvm-nm"}")\n'
        f'set(CMAKE_STRIP "{binaries / "llvm-strip"}")\n'
        f'set(CMAKE_OSX_SYSROOT "{sdk_root["path"]}")\n'
        f'set(CMAKE_OSX_DEPLOYMENT_TARGET "{target.deployment_target}")\n'
        f'set(CMAKE_C_FLAGS_INIT "{compile_flags}")\n'
        f'set(CMAKE_CXX_FLAGS_INIT "{compile_flags} -stdlib=libc++")\n'
    )


def _controller_digest(root: Path) -> str:
    material = {
        "build.py": digest_file(root / "build.py")[0],
        "buildsys": tree_digest(root / "buildsys", exclude={"__pycache__"}),
        "macho": digest_file(root / "buildsys" / "macho.py")[0],
    }
    return identity(canonical_json(material).encode())


def phases_root(root: Path, target: Target) -> Path:
    return root / ".work" / "build" / target.triple / "phases"


def prepare(
    *,
    target: Target,
    cache: Cache,
    sources: list[Input],
    root: Path,
    work: Path,
) -> Path:
    _require_host(target)
    selected = {item.name: item for item in sources if item.target in ("all", target.triple)}
    toolchain_item = selected.get(f"llvm-toolchain-{target.machine}")
    bootstrap_item = selected.get("cmake-bootstrap-darwin")
    if toolchain_item is None or bootstrap_item is None:
        raise DarwinError(f"{target.triple}: source lock lacks the LLVM toolchain or bootstrap CMake")
    sdk_root = sdk()
    toolchain_lock = json.loads((root / "bootstrap.lock.json").read_text()).get("macos_toolchain", {})
    minimum = toolchain_lock.get("sdk_minimum_version")
    if minimum:
        floor = tuple(int(part) for part in str(minimum).split(".")[:2])
        found = tuple(int(part) for part in sdk_root["version"].split(".")[:2])
        if found < floor:
            raise DarwinError(f"SDK {sdk_root['version']} is below the locked minimum {minimum}")
    inputs = {
        "toolchain": toolchain_item.sha256,
        "bootstrap-cmake": bootstrap_item.sha256,
        "sdk-version": identity(sdk_root["version"].encode()),
        "sdk-path": identity(sdk_root["path"].encode()),
        "sdk-minimum": identity(str(minimum or "").encode()),
        "controller": _controller_digest(root),
    }
    phases = PhaseCache(phases_root(root, target))

    def action(directory: Path) -> None:
        toolchain_dir = _install_llvm(cache.require(toolchain_item), directory / "toolchain")
        report = verify_toolchain(toolchain_dir, target, work)
        (directory / "toolchain.json").write_text(json.dumps(report, indent=2) + "\n")
        (directory / "sdk.json").write_text(json.dumps(sdk_root, indent=2) + "\n")
        cmake_app = safe_extract(cache.require(bootstrap_item), directory / "bootstrap-cmake")
        entries = list(cmake_app.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise DarwinError("bootstrap CMake archive has an invalid layout")
        binary = entries[0] / "CMake.app" / "Contents" / "bin" / "cmake"
        if not binary.is_file():
            raise DarwinError(f"{binary}: missing")
        version = _run([str(binary), "--version"], cwd=directory, env=dict(os.environ)).splitlines()
        if not version or version[0] != f"cmake version {BOOTSTRAP_CMAKE_VERSION}":
            raise DarwinError(f"bootstrap CMake is {version[0] if version else 'missing'!r}")
        (directory / "bootstrap-cmake.json").write_text(
            json.dumps({"path": str(binary), "version": version[0]}, indent=2) + "\n"
        )

    result = phases.run("prepare", inputs, action)
    print(f"prepare {'reused' if result.reused else 'built'} at {result.directory} ({result.fingerprint[:16]})")
    return result.directory


def _rust_root(root: Path, target: Target) -> Path:
    return root / ".work" / "rust" / target.triple


def _vendor_rustls(
    *, target: Target, cache: Cache, lock: BootstrapLock, root: Path, work: Path, source: Input
) -> tuple[Path, Path]:
    components = [item for item in bootstrap_inputs(lock, target.triple)
                  if item.name in RUST_COMPONENTS]
    if {item.name for item in components} != RUST_COMPONENTS:
        raise DarwinError(f"{target.triple}: bootstrap lock lacks the Rust component set")
    rust_root = _rust_root(root, target)
    tools = rust.install_tools(cache, components, rust_root, work)
    vendored = rust.vendor(
        cache, components, source,
        root / "patches" / "rustls-ffi" / "0001-graviola-provider.patch",
        rust_root, work,
    )
    return tools, vendored


def _phase_digest(directory: Path) -> str:
    try:
        record = json.loads((directory / "phase.json").read_text())
        expected: object = record["output_digest"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DarwinError(f"{directory}: missing or invalid phase record") from error
    if (not isinstance(expected, str) or (directory / "state.json").exists()
            or tree_digest(directory, exclude={"phase.json", "state.json"}) != expected):
        raise DarwinError(f"{directory}: phase output does not match its record")
    return expected


def build_rustls(
    *,
    target: Target,
    cache: Cache,
    lock: BootstrapLock,
    root: Path,
    work: Path,
    prepared: Path,
    source: Input,
) -> Path:
    tools, vendored = _vendor_rustls(target=target, cache=cache, lock=lock, root=root,
                                    work=work, source=source)
    rust_root = _rust_root(root, target)
    inputs = {
        "tools": _phase_digest(rust_root / "phases" / "tools"),
        "vendor": _phase_digest(vendored),
        "prepare": _phase_digest(prepared),
        "implementation": digest_file(Path(__file__))[0],
    }
    phases = PhaseCache(rust_root / "phases")

    def action(directory: Path) -> None:
        projects = list((vendored / "source").iterdir())
        if len(projects) != 1 or not projects[0].is_dir():
            raise DarwinError("vendored Rustls source has an invalid layout")
        project = directory / "source"
        shutil.copytree(projects[0], project)
        cargo_home = directory / "cargo"
        cargo_home.mkdir()
        rust._cargo_config(cargo_home, vendored)
        toolchain_dir = prepared / "toolchain"
        binaries = toolchain_dir / "bin"
        sdk_root = json.loads((prepared / "sdk.json").read_text())
        env = {
            **rust._rust_environment(),
            "TMPDIR": str(work),
            "CARGO_HOME": str(cargo_home),
            "CARGO_TARGET_DIR": str(directory / "target"),
            "RUSTC": str(tools / "bin" / "rustc"),
            "RUSTC_WRAPPER": "",
            "RUSTFLAGS": f"--remap-path-prefix={rust_root}=/rust",
            "MACOSX_DEPLOYMENT_TARGET": target.deployment_target,
            "SDKROOT": sdk_root["path"],
            "PATH": f"{tools / 'bin'}{os.pathsep}{binaries}{os.pathsep}{os.environ.get('PATH', '')}",
            f"CARGO_TARGET_{target.triple.upper().replace('-', '_')}_LINKER": str(binaries / "clang"),
        }
        _run([
            str(tools / "bin" / "cargo"), "build", "--release", "--offline", "--frozen",
            "--target", target.triple, "--no-default-features", "--features", "graviola",
        ], cwd=project, env=env)
        archive = directory / "target" / target.triple / "release" / "librustls_ffi.a"
        if not archive.is_file():
            raise DarwinError("Rustls static archive was not produced")
        symbols = _run([str(binaries / "llvm-nm"), "-g", str(archive)], cwd=directory, env=env)
        if any(line.split() and line.split()[-1].startswith(("SSL_", "OPENSSL_"))
               for line in symbols.splitlines()):
            raise DarwinError("Rustls static archive contains OpenSSL symbols")

    result = phases.run("rustls", inputs, action)
    print(f"Rustls static library {'reused' if result.reused else 'built'} at {result.directory}")
    return result.directory / "target" / target.triple / "release" / "librustls_ffi.a"


def bootstrap(
    *,
    target: Target,
    cache: Cache,
    sources: list[Input],
    prepared: Path,
    root: Path,
) -> Path:
    selected = {item.name: item for item in sources if item.target in ("all", target.triple)}
    ninja_item = selected.get("ninja-source")
    if ninja_item is None:
        raise DarwinError("source lock lacks ninja-source")
    prepare_record = json.loads((prepared / "phase.json").read_text())
    phases = PhaseCache(phases_root(root, target))
    inputs = {
        "prepare": prepare_record["output_digest"],
        "ninja": ninja_item.sha256,
        "controller": _controller_digest(root),
    }

    def action(directory: Path) -> None:
        extracted = safe_extract(cache.require(ninja_item), directory / "source")
        entries = list(extracted.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise DarwinError("ninja source has an invalid layout")
        _run(["python3", "configure.py", "--bootstrap"], cwd=entries[0], env=dict(os.environ))
        binary = entries[0] / "ninja"
        if not binary.is_file():
            raise DarwinError("ninja bootstrap did not produce a binary")
        shutil.copy2(binary, directory / "ninja")
        os.chmod(directory / "ninja", 0o755)

    result = phases.run("bootstrap", inputs, action)
    print(f"bootstrap {'reused' if result.reused else 'built'} at {result.directory} ({result.fingerprint[:16]})")
    return result.directory


def build_cmake(
    *,
    target: Target,
    cache: Cache,
    sources: list[Input],
    root: Path,
    prepared: Path,
    rustls_archive: Path,
    bootstrap_dir: Path,
) -> Path:
    selected = {item.name: item for item in sources if item.target in ("all", target.triple)}
    cmake_item = selected.get("cmake-source")
    rustls_item = selected.get("rustls-ffi-source")
    if cmake_item is None or rustls_item is None:
        raise DarwinError("source lock lacks CMake or Rustls")
    inventory = patches.verify_inventory(root / "patches")
    prepare_record = json.loads((prepared / "phase.json").read_text())
    sdk_root = json.loads((prepared / "sdk.json").read_text())
    phases = PhaseCache(phases_root(root, target))
    inputs = {
        "prepare": prepare_record["output_digest"],
        "cmake": cmake_item.sha256,
        "rustls": _phase_digest(rustls_archive.parents[3]),
        "patches": identity(canonical_json([(item.name, item.sha256) for item in inventory]).encode()),
        "controller": _controller_digest(root),
    }

    def action(directory: Path) -> None:
        extracted = safe_extract(cache.require(cmake_item), directory / "source-input")
        entries = list(extracted.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise DarwinError("cmake source has an invalid layout")
        source = directory / "source"
        shutil.copytree(entries[0], source, symlinks=True)
        toolchain_dir = prepared / "toolchain"
        env = {key: value for key, value in os.environ.items()
               if key not in {"CFLAGS", "CXXFLAGS", "LDFLAGS", "SDKROOT",
                              "MACOSX_DEPLOYMENT_TARGET"}}
        env.update(environment(toolchain_dir))
        env["SDKROOT"] = sdk_root["path"]
        env["MACOSX_DEPLOYMENT_TARGET"] = target.deployment_target
        for item in inventory:
            if item.name.startswith("rustls-ffi/"):
                continue
            with tempfile.NamedTemporaryFile(prefix="patch-", suffix=".patch", dir=directory) as patch_file:
                patch_file.write(item.content)
                patch_file.flush()
                _run(["patch", "--batch", "--forward", "-p1", "-i", patch_file.name], cwd=source, env=env)
        rustls_root = rustls_archive.parents[3] / "source"
        ninja = bootstrap_dir / "ninja"
        cmake = _bootstrap_cmake(prepared)
        file = directory / "toolchain.cmake"
        file.write_text(_toolchain_file(toolchain_dir, sdk_root, target))
        build_tree = directory / "build"
        _run([
            str(cmake), "-S", str(source), "-B", str(build_tree),
            "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
            f"-DCMAKE_TOOLCHAIN_FILE={file}", "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_OSX_DEPLOYMENT_TARGET={target.deployment_target}",
            f"-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG -ffile-prefix-map={source}=/usr/src/cmake",
            f"-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG -ffile-prefix-map={source}=/usr/src/cmake",
            "-DBUILD_CursesDialog=OFF", "-DBUILD_QtDialog=OFF", "-DCMAKE_USE_SYSTEM_LIBRARIES=OFF",
            "-DCMake_ENABLE_DEBUGGER=ON", "-DCMAKE_USE_OPENSSL=OFF", "-DCURL_USE_RUSTLS=ON",
            "-DCURL_USE_LIBPSL=OFF", "-DCURL_CA_BUNDLE=none", "-DCURL_CA_PATH=none",
            f"-DRUSTLS_VERSION={rustls_item.version}",
            f"-DRUSTLS_INCLUDE_DIR={rustls_root / 'src'}",
            f"-DRUSTLS_LIBRARY={rustls_archive}",
            *[f"-DSPHINX_{name}=OFF" for name in (
                "INFO", "MAN", "HTML", "SINGLEHTML", "LINKCHECK", "QTHELP", "LATEXPDF", "TEXT", "INCLUDE_IN_ALL",
            )],
        ], cwd=directory, env=env)
        _run([str(ninja), "-C", str(build_tree), f"-j{os.cpu_count() or 1}"], cwd=directory, env=env)
        executable = build_tree / "bin" / "cmake"
        version_output = _run([str(executable), "--version"], cwd=directory, env=env)
        if not version_output.splitlines() or version_output.splitlines()[0] != f"cmake version {cmake_item.version}":
            raise DarwinError(f"built CMake does not report version {cmake_item.version}")
        capabilities = json.loads(_run([str(executable), "-E", "capabilities"], cwd=directory, env=env))
        if capabilities.get("tls") is not True or capabilities.get("debugger") is not True:
            raise DarwinError("CMake must include TLS and the debugger")
        for name in ("cmake", "ctest", "cpack"):
            macho.audit(build_tree / "bin" / name, target)
        (directory / "source-version").write_text(cmake_item.version + "\n")

    result = phases.run("cmake", inputs, action)
    print(f"cmake {'reused' if result.reused else 'built'} at {result.directory} ({result.fingerprint[:16]})")
    return result.directory


def _bootstrap_cmake(prepared: Path) -> Path:
    record = json.loads((prepared / "bootstrap-cmake.json").read_text())
    return Path(record["path"])


def stage_distribution(cmake_phase: Path, directory: Path, target: Target, version: str,
                       licenses_dir: Path, notice: Path, toolchain: Path) -> None:
    stage.stage(cmake_phase, directory, target.triple, version, licenses_dir, notice)
    for name in ("cmake", "ctest", "cpack"):
        macho.strip_debug(cmake_phase / "build/bin" / name, directory / "bin" / name,
                          target, toolchain / "bin")


def _rustls_closure(root: Path, target: Target) -> tuple[str, str]:
    rust_root = _rust_root(root, target)
    tools = rust_root / "phases" / "tools" / "bin"
    vendored = rust_root / "phases" / "vendor"
    projects = list((vendored / "source").iterdir())
    if len(projects) != 1 or not projects[0].is_dir():
        raise DarwinError("vendored Rustls source has an invalid layout")
    with tempfile.TemporaryDirectory(prefix="cargo-tree-", dir=root / ".work" / "tmp") as temporary:
        cargo_home = Path(temporary)
        rust._cargo_config(cargo_home, vendored)
        env = {**rust._rust_environment(), "CARGO_HOME": str(cargo_home),
               "TMPDIR": str(root / ".work" / "tmp"),
               "RUSTC": str(tools / "rustc"), "RUSTC_WRAPPER": "",
               "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}"}
        rust_closure = rust._run([
            str(tools / "cargo"), "tree", "--manifest-path", str(projects[0] / "Cargo.toml"),
            "--locked", "--offline", "--no-default-features", "--features", "graviola",
            "--target", target.triple, "-e", "normal,build", "--prefix", "none", "--format", "{p}",
        ], cwd=projects[0], env=env)
        std_home = cargo_home / "std-home"
        std_home.mkdir()
        std_source = rust_root / "phases" / "tools" / "lib" / "rustlib" / "src" / "rust" / "library"
        std_env = {**env, "CARGO_HOME": str(std_home)}
        std_closure = rust._run([
            str(tools / "cargo"), "tree", "--locked", "--offline", "-p", "std",
            "--features", "panic-unwind,backtrace", "--target", target.triple,
            "-e", "normal,build", "--prefix", "none", "--format", "{p}",
        ], cwd=std_source, env=std_env)
    return rust_closure, std_closure


def package_archive(
    *,
    target: Target,
    root: Path,
    stage_phase: Path,
    cmake_phase: Path,
    prepared: Path,
    commit: str,
) -> Path:
    from . import package as package_module

    sources_lock = load_sources(root / "sources.lock.json")
    bootstrap_lock = load_bootstrap(root / "bootstrap.lock.json")
    source = next(item for item in sources_lock if item.name == "cmake-source")
    toolchain_item = next(item for item in sources_lock
                          if item.name == f"llvm-toolchain-{target.machine}")
    with tarfile.open(Cache(root / ".work" / "cache", offline=True).require(source), "r:gz") as archive:
        first = archive.next()
        if first is None:
            raise DarwinError("cmake source archive is empty")
        epoch = int(first.mtime)
    cmake_record = json.loads((cmake_phase / "phase.json").read_text())
    stage_record = json.loads((stage_phase / "phase.json").read_text())
    if (cmake_phase / "state.json").exists() or tree_digest(
            cmake_phase, exclude={"phase.json", "state.json"}) != cmake_record["output_digest"]:
        raise DarwinError("built CMake no longer matches its phase record")
    if (stage_phase / "state.json").exists() or stage_record["inputs"].get("cmake") != cmake_record["output_digest"] or tree_digest(
            stage_phase, exclude={"phase.json", "state.json"}) != stage_record["output_digest"]:
        raise DarwinError("staged CMake no longer matches its phase record")
    cache_text = (cmake_phase / "build/CMakeCache.txt").read_text().splitlines()
    flag_names = {"CMAKE_C_FLAGS", "CMAKE_C_FLAGS_RELEASE", "CMAKE_CXX_FLAGS",
                  "CMAKE_CXX_FLAGS_RELEASE", "CMAKE_EXE_LINKER_FLAGS",
                  "CMAKE_OSX_DEPLOYMENT_TARGET", "CMAKE_OSX_SYSROOT"}
    flags = {line.split(":", 1)[0]: line.split("=", 1)[1]
             for line in cache_text if ":" in line and "=" in line
             and line.split(":", 1)[0] in flag_names}
    present = {line.split(":", 1)[0] for line in cache_text if ":" in line}
    if flag_names - present:
        raise DarwinError(f"built CMake cache lacks flags: {sorted(flag_names - present)}")
    toolchain_report = json.loads((prepared / "toolchain.json").read_text())
    inventory = patches.verify_inventory(root / "patches")
    patch_identity = identity(canonical_json([(item.name, item.sha256) for item in inventory]).encode())
    rustls_closure, std_closure = _rustls_closure(root, target)
    licenses.verify_closure(rustls_closure, std_closure, root / "licenses")
    darwin_names = {"cmake-source", "rustls-ffi-source", "ninja-source",
                    "cmake-bootstrap-darwin", f"llvm-toolchain-{target.machine}"}
    locked = [item for item in sources_lock
              if item.name in darwin_names and item.role in ("source", "build-source")]
    locked.extend(bootstrap_inputs(bootstrap_lock, target.triple))
    build_inputs = [{"name": item.name, "version": item.version, "sha256": item.sha256}
                    for item in locked]
    metadata = {
        "schema_version": 1,
        "source": {"version": source.version, "sha256": source.sha256,
                   "commit": commit, "patch_set": patch_identity},
        "target": {"triple": target.triple, "cpu_baseline": target.cpu_baseline,
                   "deployment_target": target.deployment_target},
        "toolchain": {"version": toolchain_item.version, "sha256": toolchain_item.sha256,
                      "compiler": toolchain_report["clang"]},
        "flags": flags,
        "dependencies": {
            "native": "Mach-O audit: system libraries only, no RPATH, deployment floor enforced",
            "rustls": rustls_closure.splitlines(),
            "rust_std": std_closure.splitlines(),
            "build_inputs": build_inputs,
        },
        "build": {"mode": "qualification", "network": "host",
                  "isolation": "native macOS host; fetch is the only networked step"},
        "macho_audit": "passed",
    }
    destination = root / ".work" / "artifacts" / target.triple / f"cmake-{source.version}-{target.triple}.tar.xz"
    package_module.create(stage_phase, destination, metadata, epoch)
    package_module.inspect(destination)
    sha256 = digest_file(destination)[0]
    candidate_record = {"archive": destination.name, "sha256": sha256,
                        "size": destination.stat().st_size, "commit": commit}
    temporary = destination.with_name("candidate.json.tmp")
    temporary.write_text(json.dumps(candidate_record, sort_keys=True, indent=2) + "\n")
    temporary.replace(destination.with_name("candidate.json"))
    print(f"package: {destination} ({sha256})")
    return destination


def archive_path(root: Path, target: Target) -> Path:
    source = next(item for item in load_sources(root / "sources.lock.json")
                  if item.name == "cmake-source")
    return root / ".work" / "artifacts" / target.triple / f"cmake-{source.version}-{target.triple}.tar.xz"


def candidate(root: Path, target: Target) -> tuple[Path, dict[str, object]]:
    archive = archive_path(root, target)
    record_path = archive.with_name("candidate.json")
    try:
        record: dict[str, object] = json.loads(record_path.read_text())
    except (OSError, ValueError) as error:
        raise DarwinError(f"candidate record is missing or invalid: {error}") from error
    if (not archive.is_file() or not isinstance(record, dict)
            or record.get("archive") != archive.name
            or not isinstance(record.get("sha256"), str)
            or record.get("size") != archive.stat().st_size):
        raise DarwinError("candidate record does not match the archive")
    if digest_file(archive)[0] != record["sha256"]:
        raise DarwinError("candidate archive has been modified")
    return archive, record


def qualify(root: Path, target: Target) -> Path:
    from . import budgets, generations

    _require_host(target)
    archive, record = candidate(root, target)
    sha256 = record["sha256"]
    if not isinstance(sha256, str):
        raise DarwinError("candidate record has no sha256")
    source = next(item for item in load_sources(root / "sources.lock.json")
                  if item.name == "cmake-source")
    size_budgets = budgets.read(root / "release-budgets.json")

    def run(tree: Path) -> dict[str, object]:
        sizes = budgets.check_size(size_budgets, target.triple, tree, tree.parent / "artifact.tar.xz")
        print(f"size budgets passed: {sizes}")
        report = macho.verify_prefix(tree / "usr", target, version=source.version,
                                     scratch=tree.parent / "verify")
        return {"basic": "passed", "macho_audit": "passed", "hello": report["hello"],
                "sizes": sizes}

    generation = generations.qualify(
        root / ".work" / "generations" / target.triple, archive, sha256, run)
    print(f"qualified generation: {generation}")
    return generation


def _measure(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    before = os.getloadavg()[0]
    with tempfile.TemporaryDirectory(prefix="measure-", dir=cwd) as temporary:
        output = Path(temporary) / "output"
        pid = os.fork()
        if pid == 0:
            try:
                os.chdir(cwd)
                with output.open("wb") as stream:
                    os.dup2(stream.fileno(), 1)
                    os.dup2(stream.fileno(), 2)
                os.execvpe(command[0], command, env)
            except BaseException:  # noqa: BLE001 - a forked child must exit instead of unwinding into the parent
                os._exit(127)
        _, status, usage = os.wait4(pid, 0)
        returncode = os.waitstatus_to_exitcode(status)
        text = output.read_text(errors="replace")
    duration = time.perf_counter() - started
    if returncode != 0:
        raise DarwinError(f"measurement failed ({returncode}): {command[0]}\n{text[-4000:]}")
    return {
        "seconds": duration,
        "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "max_rss_kib": usage.ru_maxrss // 1024,
        "exit_code": returncode,
        "load_before": before,
        "load_after": os.getloadavg()[0],
    }


_WORKLOADS = {
    "fmt": ("fmt-source", "", ["-DFMT_TEST=OFF", "-DFMT_DOC=OFF"]),
    "zstd": ("zstd-source", "build/cmake", ["-DZSTD_BUILD_PROGRAMS=ON", "-DZSTD_BUILD_SHARED=OFF"]),
    "libjpeg-turbo": ("libjpeg-turbo-source", "", ["-DWITH_SIMD=OFF", "-DENABLE_SHARED=OFF"]),
    "llvm-clang": ("llvm-project-source", "llvm",
                   ["-DLLVM_ENABLE_PROJECTS=clang", "-DPython3_EXECUTABLE={python}"]),
}


def benchmark(root: Path, target: Target, repetitions: int = 5) -> None:
    from . import budgets

    _require_host(target)
    if repetitions < 5:
        raise DarwinError("memory baseline requires at least five repetitions")
    active = root / ".work" / "generations" / target.triple / "active"
    if not active.is_symlink():
        raise DarwinError("qualify a candidate before benchmarking")
    generation = active.resolve().parent
    archive = generation / "artifact.tar.xz"
    results = json.loads((generation / "results.json").read_text())
    archive_sha256 = digest_file(archive)[0]
    if results.get("archive_sha256") != archive_sha256 or results.get("archive_size") != archive.stat().st_size:
        raise DarwinError("qualified archive digest or size does not match results")
    budget_path = root / "release-budgets.json"
    budget_document = budgets.read(budget_path)
    budget_digest = digest_file(budget_path)[0]
    budgets.validate_memory_source(budget_document, target.triple,
                                   archive_sha256, archive.stat().st_size)
    extract_root = root / ".work" / "tmp" / "benchmark-tree"
    shutil.rmtree(extract_root, ignore_errors=True)
    tree = safe_extract(archive, extract_root) / "usr"
    cmake = tree / "bin" / "cmake"
    ninja = phases_root(root, target) / "bootstrap" / "ninja"
    if not ninja.is_file():
        raise DarwinError("bootstrap phase lacks the ninja executor")
    sources_lock = {item.name: item for item in load_sources(root / "sources.lock.json")}
    input_cache = Cache(root / ".work" / "cache", offline=True)
    scratch = Path(tempfile.mkdtemp(prefix="darwin-bench-", dir=root / ".work" / "tmp"))
    env = {**os.environ, "TMPDIR": str(scratch)}
    records = []
    try:
        for workload, (input_name, subdirectory, options) in _WORKLOADS.items():
            item = sources_lock.get(input_name)
            if item is None:
                raise DarwinError(f"source lock lacks {input_name}")
            extracted = safe_extract(input_cache.require(item), scratch / input_name)
            entries = list(extracted.iterdir())
            if len(entries) != 1 or not entries[0].is_dir():
                raise DarwinError(f"{input_name}: invalid source layout")
            source = entries[0] / subdirectory
            (scratch / workload).mkdir(parents=True, exist_ok=True)
            build = scratch / workload / "build"
            command = [str(cmake), "-S", str(source), "-B", str(build), "-G", "Ninja",
                       f"-DCMAKE_MAKE_PROGRAM={ninja}", "-DCMAKE_BUILD_TYPE=Release",
                       *[option.replace("{python}", sys.executable) for option in options]]
            for iteration in range(repetitions):
                shutil.rmtree(build, ignore_errors=True)
                print(f"{workload}: repetition {iteration + 1}/{repetitions}", flush=True)
                measured = _measure(command, cwd=scratch / workload, env=env)
                records.append({"variant": "product", "workload": workload,
                                "scenario": "initial", "iteration": iteration, **measured})
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if digest_file(archive)[0] != archive_sha256 or digest_file(budget_path)[0] != budget_digest:
        raise DarwinError("benchmark inputs changed during measurement")
    try:
        initialized = budgets.apply_memory(budget_document, target.triple,
                                           archive_sha256, archive.stat().st_size, records)
    except budgets.BudgetError as error:
        raise DarwinError(str(error)) from error
    if initialized:
        temporary = budget_path.with_name("release-budgets.json.tmp")
        temporary.write_text(json.dumps(budget_document, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, budget_path)
        print(f"memory baseline established for {target.triple}; review and commit the budget")
    else:
        evidence = budgets.release_evidence(budget_document, target.triple, archive_sha256,
                                            archive.stat().st_size, budget_digest,
                                            repetitions, records)
        results_dir = root / ".work" / "benchmark-results"
        results_dir.mkdir(parents=True, exist_ok=True)
        temporary = results_dir / f"{target.triple}.json.tmp"
        temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, results_dir / f"{target.triple}.json")
        print(f"size and memory budgets passed for {target.triple}; existing baseline retained")
