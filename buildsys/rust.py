"""Install locked Rust components and vendor the patched Rustls sources."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from .inputs import Cache, Input, digest_bytes, safe_extract
from .phases import PhaseCache


class RustError(Exception):
    pass


class _Interrupted(BaseException):
    def __init__(self, signum: int) -> None:
        self.signum = signum


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
            **os.environ,
            "TMPDIR": str(scratch),
            "CARGO_HOME": str(root / "cargo"),
            "RUSTC_WRAPPER": "",
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
