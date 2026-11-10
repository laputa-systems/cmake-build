"""Install locked Rust components and vendor the patched Rustls sources."""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import tempfile
from pathlib import Path

from .inputs import Cache, Input, digest_bytes, safe_extract, tree_digest
from .phases import PhaseCache
from .targets import Target
from . import sandbox, toolchain


class RustError(Exception):
    pass


class _Interrupted(BaseException):
    def __init__(self, signum: int) -> None:
        self.signum = signum


def _rust_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if key not in {"RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS"}
            and not (key.startswith("CARGO_TARGET_") and key.endswith(("_RUSTFLAGS", "_LINKER")))}


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    def interrupt(signum, frame):
        raise _Interrupted(signum)

    previous = {signum: signal.signal(signum, interrupt) for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)}
    process = None
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        stdout, stderr = process.communicate(timeout=1800)
    except BaseException as error:
        for signum in previous:
            signal.signal(signum, signal.SIG_IGN)
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        if isinstance(error, _Interrupted):
            signal.signal(error.signum, signal.SIG_DFL)
            os.kill(os.getpid(), error.signum)
        if isinstance(error, OSError):
            raise RustError(f"{command[0]} could not complete: {error}") from error
        if isinstance(error, subprocess.TimeoutExpired):
            raise RustError(f"{command[0]} exceeded its deadline") from error
        raise
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    if process.returncode:
        raise RustError(f"{command[0]} failed ({process.returncode}):\n{stdout[-4000:]}\n{stderr[-4000:]}")
    return stdout


def vendor(cache: Cache, components: list[Input], source: Input, patch: Path, root: Path, scratch: Path) -> Path:
    selected = [item for item in components if item.name in {"rustc", "cargo", "rust-std", "rust-src"}]
    names = {item.name: item for item in selected}
    if len(selected) != 4 or set(names) != {"rustc", "cargo", "rust-std", "rust-src"}:
        raise RustError("Rust component lock is incomplete or duplicated")
    scratch.mkdir(parents=True, exist_ok=True)
    phases = PhaseCache(root / "phases")
    inputs = {name: item.sha256 for name, item in names.items()}
    inputs["implementation"] = digest_bytes(Path(__file__))[0]

    def install(directory: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="rust-install-", dir=scratch) as temporary:
            temporary = Path(temporary)
            env = {**os.environ, "TMPDIR": str(scratch)}
            for name in ("rustc", "cargo", "rust-std", "rust-src"):
                extracted = safe_extract(cache.require(names[name]), temporary / name)
                entries = list(extracted.iterdir())
                if len(entries) != 1 or not entries[0].is_dir():
                    raise RustError(f"{name}: expected one component directory")
                _run([str(entries[0] / "install.sh"), f"--prefix={directory}", "--disable-ldconfig"], cwd=entries[0], env=env)

    tools = phases.run("tools", inputs, install)
    tool_record = json.loads((tools.directory / "phase.json").read_text())
    vendor_inputs = {
        "tools": tool_record["output_digest"],
        "source": source.sha256,
        "patch": digest_bytes(patch)[0],
        "implementation": digest_bytes(Path(__file__))[0],
    }

    def download(directory: Path) -> None:
        extracted = safe_extract(cache.require(source), directory / "source")
        entries = list(extracted.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise RustError("rustls-ffi: expected one source directory")
        project = entries[0]
        env = {
            **_rust_environment(),
            "TMPDIR": str(scratch),
            "CARGO_HOME": str(root / "cargo"),
            "RUSTC_WRAPPER": "",
            "RUSTC": str(tools.directory / "bin/rustc"),
            "PATH": f"{tools.directory / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        _run(["patch", "--batch", "-p1", "-i", str(patch)], cwd=project, env=env)
        _run([
            str(tools.directory / "bin/cargo"), "vendor", "--locked", "--sync",
            str(tools.directory / "lib/rustlib/src/rust/library/Cargo.toml"),
            str(directory / "vendor"),
        ], cwd=project, env=env)

    result = phases.run("vendor", vendor_inputs, download)
    print(f"Rust sources {'reused' if result.reused else 'vendored'} at {result.directory}")
    return result.directory


def _phase_digest(directory: Path) -> str:
    try:
        record = json.loads((directory / "phase.json").read_text())
        expected = record["output_digest"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RustError(f"{directory}: missing or invalid phase record") from error
    if (directory / "state.json").exists() or tree_digest(directory, exclude={"phase.json", "state.json"}) != expected:
        raise RustError(f"{directory}: phase output does not match its record")
    return expected


def build_static(root: Path, prepared: Path, target: Target, kache: Path, scratch: Path) -> Path:
    if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
        raise RustError("Rustls build requires a sealed container with only loopback networking")
    tools = root / "phases/tools"
    vendored = root / "phases/vendor"
    tc = prepared / "toolchain"
    sysroot = prepared / "sysroot"
    toolchain.verify(tc, target, environ={**os.environ, "PATH": f"{tc / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"})
    inputs = {
        "tools": _phase_digest(tools),
        "vendor": _phase_digest(vendored),
        "prepare": _phase_digest(prepared),
        "kache": digest_bytes(kache)[0],
        "implementation": digest_bytes(Path(__file__))[0],
    }
    phases = PhaseCache(root / "phases")

    def action(directory: Path) -> None:
        projects = list((vendored / "source").iterdir())
        if len(projects) != 1 or not projects[0].is_dir():
            raise RustError("vendored Rustls source has an invalid layout")
        project = directory / "source"
        shutil.copytree(projects[0], project)
        cargo_home = directory / "cargo"
        cargo_home.mkdir()
        (cargo_home / "config.toml").write_text(
            '[source.crates-io]\nreplace-with = "vendored-sources"\n'
            '[source.vendored-sources]\ndirectory = ' + json.dumps(str(vendored / "vendor")) + '\n'
        )
        host_libs = directory / "host-libs"
        host_libs.mkdir()
        host_runtime = Path("/usr/lib/libgcc_s.so.1")
        if not host_runtime.is_file():
            raise RustError(f"missing host procedural-macro runtime {host_runtime}")
        (host_libs / "libgcc_s.so").symlink_to(host_runtime)
        env = {
            **_rust_environment(),
            "TMPDIR": str(scratch),
            "CARGO_HOME": str(cargo_home),
            "CARGO_TARGET_DIR": str(directory / "target"),
            "XDG_CACHE_HOME": str(scratch / "kache-cache"),
            "XDG_CONFIG_HOME": str(scratch / "kache-config"),
            "RUSTC_WRAPPER": str(kache),
            "RUSTC": str(tools / "bin/rustc"),
            "LIBRARY_PATH": str(host_libs),
            "PATH": f"{tools / 'bin'}{os.pathsep}{tc / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
            f"CARGO_TARGET_{target.triple.upper().replace('-', '_')}_LINKER": str(tc / "bin/clang"),
            "RUSTFLAGS": f"-C link-arg=--sysroot={sysroot} -C link-arg=-fuse-ld=lld -L native={tc / 'lib'}",
        }
        _run([
            str(tools / "bin/cargo"), "build", "--offline", "--frozen", "--target", target.triple,
            "-Zbuild-std=std,panic_unwind", "-Zbuild-std-features=panic-unwind,backtrace,llvm-libunwind",
            "--no-default-features", "--features", "graviola",
        ], cwd=project, env=env)
        archive = directory / "target" / target.triple / "debug/librustls_ffi.a"
        if not archive.is_file():
            raise RustError("Rustls static archive was not produced")
        symbols = _run([str(tc / "bin/llvm-nm"), "-g", str(archive)], cwd=directory, env=env)
        if any(line.split() and line.split()[-1].startswith(("SSL_", "OPENSSL_")) for line in symbols.splitlines()):
            raise RustError("Rustls static archive contains OpenSSL symbols")

    result = phases.run("staticlib", inputs, action)
    print(f"Rustls static library {'reused' if result.reused else 'built'} at {result.directory}")
    return result.directory / "target" / target.triple / "debug/librustls_ffi.a"
