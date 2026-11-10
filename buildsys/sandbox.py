"""Sealed Docker execution and the network-boundary self-test."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .inputs import (
    BootstrapLock,
    Cache,
    Input,
    InputError,
    canonical_json,
    digest_bytes,
    identity,
)
from .targets import Target

PROBE = """
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket()
sock.settimeout(3)
try:
    sock.connect((host, port))
    sock.sendall(b"cmake-build-network-probe")
except OSError as error:
    print(f"DENIED:{error.errno}")
    raise SystemExit(0)
sock.close()
print("CONNECTED")
raise SystemExit(3)
"""


class SandboxError(Exception):
    """The builder image or the sealed execution boundary failed."""


@dataclass(frozen=True)
class SealedResult:
    returncode: int
    stdout: str
    stderr: str
    network_mode: str
    networks: dict


def in_container() -> bool:
    return Path("/.dockerenv").is_file()


def docker_path() -> str:
    found = shutil.which("docker")
    if not found:
        raise SandboxError("docker is not installed")
    return found


def _docker(*arguments: str, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        [docker_path(), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _checked(result: subprocess.CompletedProcess, what: str) -> subprocess.CompletedProcess:
    if result.returncode != 0:
        raise SandboxError(f"{what} failed ({result.returncode}): {result.stderr.strip()}")
    return result


def image_reference(lock: BootstrapLock) -> str:
    return f"alpine@{lock.image_index_digest}"


def pull_image(lock: BootstrapLock, platform: str) -> None:
    _checked(
        _docker("pull", "--platform", platform, image_reference(lock)),
        f"pull {image_reference(lock)}",
    )
    _checked(
        _docker("image", "inspect", "--format", "{{.Id}}", image_reference(lock)),
        f"inspect {image_reference(lock)}",
    )


def pull_reference(lock: BootstrapLock, platform: str) -> None:
    _checked(_docker("pull", "--platform", platform, lock.reference_image), f"pull {lock.reference_image}")


def run_fetch(image: str, target: Target, root: Path, requested: str) -> None:
    result = _docker(
        "run", "--rm", "--network", "bridge", "--platform", target.docker_platform,
        "--user", f"{os.getuid()}:{os.getgid()}", "--workdir", "/src",
        "--volume", f"{root}:/src:rw", "--env", "TMPDIR=/src/.work/tmp",
        "--env", "PYTHONPATH=/src", image,
        "python3", "build.py", "fetch", "--target", requested, "--vendor-in-container",
        timeout=1800,
    )
    if result.returncode:
        raise SandboxError(f"Rust vendoring failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    print(result.stdout, end="")


def _lock_packages(lock: BootstrapLock, triple: str) -> list[Input]:
    from .inputs import bootstrap_inputs

    return [
        item for item in bootstrap_inputs(lock, triple) if item.target == triple
    ]


def image_fingerprint(lock: BootstrapLock, target: Target, dockerfile: Path) -> str:
    packages = sorted(
        (item.name, item.version, item.sha256)
        for item in _lock_packages(lock, target.triple)
        if not item.name.startswith("rust")
    )
    material = {
        "base": lock.image_index_digest,
        "platform": target.docker_platform,
        "dockerfile": digest_bytes(dockerfile)[0],
        "packages": packages,
        "keys": sorted((item.name, item.sha256) for item in lock.keys),
    }
    return identity(canonical_json(material).encode())


def _locked_image_fingerprint(target: Target) -> str:
    from .inputs import load_bootstrap

    root = Path(__file__).resolve().parents[1]
    return image_fingerprint(load_bootstrap(root / "bootstrap.lock.json"), target, root / "docker/builder.Dockerfile")


def image_tag(lock: BootstrapLock, target: Target, dockerfile: Path) -> str:
    return f"cmake-build-builder:{image_fingerprint(lock, target, dockerfile)[:16]}"


def _context(
    lock: BootstrapLock,
    target: Target,
    dockerfile: Path,
    cache: Cache,
    context: Path,
) -> None:
    shutil.rmtree(context, ignore_errors=True)
    (context / "apks").mkdir(parents=True)
    (context / "keys").mkdir(parents=True)
    shutil.copyfile(dockerfile, context / "Dockerfile")
    for item in _lock_packages(lock, target.triple):
        destination = context / "apks" / Path(item.url).name
        shutil.copyfile(cache.require(item), destination)
    for item in lock.keys:
        shutil.copyfile(cache.require(item), context / "keys" / Path(item.url).name)


def build_image(
    lock: BootstrapLock,
    target: Target,
    dockerfile: Path,
    cache: Cache,
    context_root: Path,
) -> str:
    tag = image_tag(lock, target, dockerfile)
    existing = _docker("image", "inspect", tag)
    if existing.returncode == 0:
        return tag
    context = context_root / image_fingerprint(lock, target, dockerfile)
    _context(lock, target, dockerfile, cache, context)
    result = _docker(
        "build",
        "--network",
        "none",
        "--platform",
        target.docker_platform,
        "--tag",
        tag,
        "--file",
        str(context / "Dockerfile"),
        str(context),
        timeout=1800,
    )
    _checked(result, f"build {tag}")
    return tag


def _run_container(
    image: str,
    command: list[str],
    *,
    network_mode: str,
    target: Target,
    mounts: list[tuple[Path, str]],
    env: dict[str, str] | None = None,
    workdir: str = "/src",
    timeout: int = 3600,
) -> SealedResult:
    arguments = [
        "create",
        "--network",
        network_mode,
        "--platform",
        target.docker_platform,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--workdir",
        workdir,
    ]
    for host, container in mounts:
        arguments.extend(["--volume", f"{host}:{container}:rw"])
    for key, value in (env or {}).items():
        arguments.extend(["--env", f"{key}={value}"])
    arguments.extend([image, *command])
    created = _checked(_docker(*arguments), f"create {network_mode} container")
    container_id = created.stdout.strip()
    try:
        inspection = json.loads(
            _checked(_docker("inspect", container_id), "inspect container").stdout
        )[0]
        if inspection.get("HostConfig", {}).get("NetworkMode") != network_mode:
            raise SandboxError(f"container network mode is not {network_mode}")
        started = _docker("start", "--attach", container_id, timeout=timeout)
    finally:
        primary = sys.exception()
        try:
            _checked(_docker("rm", "--force", container_id), "remove container")
        except Exception as error:
            if primary is None:
                raise
            print(f"container cleanup failed: {error}", file=sys.stderr)
    settings = inspection.get("HostConfig", {})
    return SealedResult(
        returncode=started.returncode,
        stdout=started.stdout,
        stderr=started.stderr,
        network_mode=settings.get("NetworkMode", ""),
        networks=inspection.get("NetworkSettings", {}).get("Networks", {}),
    )


def run_sealed(
    image: str, command: list[str], *, target: Target, mounts: list[tuple[Path, str]],
    env: dict[str, str] | None = None, workdir: str = "/src", timeout: int = 3600,
) -> SealedResult:
    return _run_container(image, command, network_mode="none", target=target, mounts=mounts,
                          env=env, workdir=workdir, timeout=timeout)


def run_networked(
    image: str, command: list[str], *, target: Target, mounts: list[tuple[Path, str]],
    env: dict[str, str] | None = None, workdir: str = "/src", timeout: int = 3600,
) -> SealedResult:
    return _run_container(image, command, network_mode="bridge", target=target, mounts=mounts,
                          env=env, workdir=workdir, timeout=timeout)


def _host_gateway() -> str:
    result = _docker(
        "network",
        "inspect",
        "bridge",
        "--format",
        "{{(index .IPAM.Config 0).Gateway}}",
    )
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value or "172.17.0.1"


def _probe(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def network_boundary_selftest(image: str, target: Target, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", 0))
    listener.listen(4)
    port = listener.getsockname()[1]
    gateway = _host_gateway()
    received: list[bytes] = []
    errors: list[str] = []
    stop = threading.Event()

    def accept_loop() -> None:
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError as error:
                if not stop.is_set():
                    errors.append(str(error))
                return
            try:
                connection.settimeout(3)
                chunks = []
                while chunk := connection.recv(64):
                    chunks.append(chunk)
                received.append(b"".join(chunks))
            except OSError as error:
                errors.append(str(error))
            finally:
                connection.close()

    thread = threading.Thread(target=accept_loop)
    thread.start()
    outside: subprocess.CompletedProcess | None = None
    inside_gateway: subprocess.CompletedProcess | None = None
    inside_loopback: subprocess.CompletedProcess | None = None
    failure: str | None = None
    try:
        outside = _probe(
            [sys.executable, "-c", PROBE, "127.0.0.1", str(port)], workdir, 15
        )
        inside_gateway = _probe(
            [
                docker_path(),
                "run",
                "--rm",
                "--network",
                "none",
                "--platform",
                target.docker_platform,
                image,
                "python3",
                "-c",
                PROBE,
                gateway,
                str(port),
            ],
            workdir,
            60,
        )
        inside_loopback = _probe(
            [
                docker_path(),
                "run",
                "--rm",
                "--network",
                "none",
                "--platform",
                target.docker_platform,
                image,
                "python3",
                "-c",
                PROBE,
                "127.0.0.1",
                str(port),
            ],
            workdir,
            60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        failure = str(error)
    finally:
        stop.set()
        listener.close()
        thread.join(timeout=3)

    outside_ok = (
        outside is not None
        and outside.returncode == 3
        and outside.stdout.strip() == "CONNECTED"
    )
    gateway_denied = (
        inside_gateway is not None
        and inside_gateway.returncode == 0
        and inside_gateway.stdout.strip().startswith("DENIED:")
    )
    loopback_denied = (
        inside_loopback is not None
        and inside_loopback.returncode == 0
        and inside_loopback.stdout.strip().startswith("DENIED:")
    )
    received_ok = received == [b"cmake-build-network-probe"]
    return {
        "probe": "TCP connect to a listener held by the controller",
        "listener": f"0.0.0.0:{port}",
        "host_gateway": gateway,
        "host_returncode": None if outside is None else outside.returncode,
        "host_output": None if outside is None else outside.stdout.strip()[:120],
        "gateway_returncode": None if inside_gateway is None else inside_gateway.returncode,
        "gateway_output": None if inside_gateway is None else inside_gateway.stdout.strip()[:120],
        "loopback_returncode": None if inside_loopback is None else inside_loopback.returncode,
        "loopback_output": None if inside_loopback is None else inside_loopback.stdout.strip()[:120],
        "listener_received": [value.decode("ascii", "replace") for value in received],
        "errors": errors,
        "worker_stopped": not thread.is_alive(),
        "ok": (
            outside_ok
            and gateway_denied
            and loopback_denied
            and received_ok
            and not errors
            and failure is None
        ),
        "error": failure,
    }
