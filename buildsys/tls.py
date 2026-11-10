"""Checks for the selected Rustls dependency closure."""

from __future__ import annotations

import json
import os
import tempfile
import shlex
import tomllib
from pathlib import Path

from .inputs import Cache, Input, digest_bytes, safe_extract
from .phases import PhaseCache
from .rust import RustError, _cargo_config, _phase_digest, _run, _rust_environment
from .targets import Target
from . import rust, sandbox, toolchain


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


def check_dependencies(cargo: Path, manifest: Path, target: str, env: dict[str, str], launcher: tuple[str, ...] = ()) -> None:
    cargo = cargo.resolve()
    manifest = manifest.resolve()
    command = [
        *launcher, str(cargo), "tree", "--manifest-path", str(manifest), "--locked", "--offline",
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
        _cargo_config(cargo_home, vendored)
        env = {**_rust_environment(), "CARGO_HOME": str(cargo_home), "TMPDIR": str(scratch),
               "RUSTC": str(tools / "rustc"), "RUSTC_WRAPPER": "",
               "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}"}
        check_dependencies(tools / "cargo", projects[0] / "Cargo.toml", target, env)


def check_host_vendored(root: Path, native: Target, components: list[Input], source: Input, patch: Path, cache: Cache,
                        targets: list[str], scratch: Path) -> None:
    tools = root / "phases/tools"
    vendored = root / "phases/vendor"
    names = {item.name: item for item in components}
    required = {"rustc", "cargo", "rust-std", "rust-src", "musl", "libgcc"}
    if not required <= names.keys() or any(sum(item.name == name for item in components) != 1 for name in required):
        raise TlsError("bootstrap lock lacks or duplicates a Rust or host runtime component")
    for item in (source, *(names[name] for name in ("rustc", "cargo", "rust-std", "rust-src"))):
        cache.require(item)
    implementation = digest_bytes(Path(rust.__file__))[0]
    tool_inputs = {name: names[name].sha256 for name in ("rustc", "cargo", "rust-std", "rust-src")}
    tool_inputs["implementation"] = implementation
    tool_digest = _phase_digest(tools)
    _phase_digest(vendored)
    phase_cache = PhaseCache(root / "phases")
    vendor_inputs = {"tools": tool_digest, "source": source.sha256, "patch": digest_bytes(patch)[0], "implementation": implementation}
    for directory, inputs in ((tools, tool_inputs), (vendored, vendor_inputs)):
        record = json.loads((directory / "phase.json").read_text())
        if record.get("inputs") != dict(sorted(inputs.items())) or record.get("fingerprint") != phase_cache.fingerprint(directory.name, inputs):
            raise TlsError(f"{directory}: inputs changed; run fetch")
    projects = list((vendored / "source").iterdir())
    if len(projects) != 1 or not projects[0].is_dir():
        raise TlsError("vendored Rustls source has an invalid layout")
    with tempfile.TemporaryDirectory(prefix="cargo-host-check-", dir=scratch) as temporary:
        directory = Path(temporary)
        loader = safe_extract(cache.require(names["musl"]), directory / "musl") / native.musl_loader.lstrip("/")
        if not loader.is_file():
            raise TlsError("locked musl package does not contain its loader")
        library = safe_extract(cache.require(names["libgcc"]), directory / "libgcc") / "usr/lib"
        library_path = f"{library}{os.pathsep}{tools / 'lib'}"
        launcher = (str(loader), "--library-path", library_path)
        rustc = directory / "rustc"
        rustc.write_text("#!/bin/sh\nexec " + shlex.join([*launcher, str(tools / "bin/rustc")]) + ' "$@"\n')
        rustc.chmod(0o755)
        cargo_home = directory / "cargo"
        cargo_home.mkdir()
        _cargo_config(cargo_home, vendored)
        env = {key: value for key, value in _rust_environment().items() if key not in {"LD_LIBRARY_PATH", "LD_PRELOAD"}}
        env.update({"CARGO_HOME": str(cargo_home), "TMPDIR": str(scratch), "RUSTC": str(rustc), "RUSTC_WRAPPER": ""})
        for target in targets:
            check_dependencies(tools / "bin/cargo", projects[0] / "Cargo.toml", target, env, launcher)


def build_client(cache: Cache, source: Input, prepared: Path, archive: Path, target: Target, root: Path, scratch: Path, client: Path) -> Path:
    tc = prepared / "toolchain"
    sysroot = prepared / "sysroot"
    toolchain.verify(tc, target, environ={**os.environ, "PATH": f"{tc / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"})
    phases = PhaseCache(root / "phases")
    inputs = {"prepare": _phase_digest(prepared), "source": source.sha256, "image": sandbox._locked_image_fingerprint(target),
              "toolchain": digest_bytes(Path(toolchain.__file__))[0], "implementation": digest_bytes(Path(__file__))[0]}
    env = {**os.environ, **toolchain.environment(tc, target), "TMPDIR": str(scratch)}
    env["CFLAGS"] = shlex.join(toolchain.flags(target, sysroot))
    env["CXXFLAGS"] = shlex.join(toolchain.cxx_flags(target, sysroot))
    env["LDFLAGS"] = env["CFLAGS"]
    jobs = str(os.process_cpu_count() or 1)

    def bootstrap(directory: Path) -> None:
        extracted = safe_extract(cache.require(source), directory / "source")
        entries = list(extracted.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise TlsError("CMake archive has an invalid layout")
        build = directory / "bootstrap"
        build.mkdir()
        _run([str(entries[0] / "bootstrap"), f"--parallel={jobs}", "--no-system-libs", "--", "-DCMAKE_USE_OPENSSL=OFF", f"-DCMAKE_SYSROOT={sysroot}"], cwd=build, env=env)

    boot = phases.run("tls-bootstrap", inputs, bootstrap)
    boot_digest = _phase_digest(boot.directory)
    curl_inputs = {"bootstrap": boot_digest, "rustls": _phase_digest(archive.parents[3]), "image": inputs["image"],
                   "client": digest_bytes(client)[0], "implementation": inputs["implementation"]}

    def curl(directory: Path) -> None:
        source_root = next((boot.directory / "source").iterdir())
        mini = boot.directory / "bootstrap/Bootstrap.cmk/cmake"
        build = directory / "build"
        includes = shlex.join([*toolchain.flags(target, sysroot), f"-I{source_root / 'Utilities'}", f"-I{boot.directory / 'bootstrap/Utilities'}"])
        _run([
            str(mini), "-S", str(source_root / "Utilities/cmcurl"), "-B", str(build),
            "-DCMAKE_BUILD_TYPE=Debug", f"-DCMAKE_C_COMPILER={tc / 'bin/clang'}", f"-DCMAKE_SYSROOT={sysroot}",
            "-DCMAKE_USE_OPENSSL=OFF", "-DCURL_USE_RUSTLS=ON", "-DCURL_USE_LIBPSL=OFF", "-DBUILD_SHARED_LIBS=OFF",
            "-DCURL_CA_BUNDLE=none", "-DCURL_CA_PATH=none",
            f"-DRUSTLS_VERSION={tomllib.loads((archive.parents[3] / 'source/Cargo.toml').read_text())['package']['version']}",
            f"-DRUSTLS_INCLUDE_DIR={archive.parents[3] / 'source/src'}", f"-DRUSTLS_LIBRARY={archive}",
            f"-DCMAKE_C_FLAGS={includes}",
        ], cwd=directory, env=env)
        _run(["make", f"-j{jobs}", "cmcurl"], cwd=build, env=env)
        _run([
            str(tc / "bin/clang"), *toolchain.flags(target, sysroot), "-static-pie",
            f"-I{source_root / 'Utilities/cmcurl/include'}", str(client), str(build / "lib/libcmcurl.a"),
            str(archive), f"-L{tc / 'lib'}", "-lunwind", "-lm", "-ldl", "-lpthread", "-o", str(directory / "client"),
        ], cwd=directory, env=env)

    result = phases.run("tls-client", curl_inputs, curl)
    print(f"TLS client {'reused' if result.reused else 'built'} at {result.directory}")
    return result.directory / "client"
