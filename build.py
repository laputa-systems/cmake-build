"""Typed controller front door for the CMake musl distribution build."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from buildsys.inputs import (
    Cache,
    InputError,
    bootstrap_inputs,
    digest_bytes,
    load_bootstrap,
    load_sources,
    tree_digest,
)
from buildsys.phases import PhaseCache, PhaseError
from buildsys.sandbox import SandboxError
from buildsys import sandbox, sysroot, toolchain
from buildsys.targets import (
    TARGETS,
    UnsupportedTargetError,
    native_target,
    target as describe_target,
)

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"
CACHE = WORK / "cache"
PHASES = WORK / "phases"
BUILD_ROOT = WORK / "build"
SOURCES_LOCK = ROOT / "sources.lock.json"
BOOTSTRAP_LOCK = ROOT / "bootstrap.lock.json"
DOCKERFILE = ROOT / "docker" / "builder.Dockerfile"
PROVENANCE = ROOT / "tests" / "fixtures" / "provenance" / "run.py"

try:
    _NATIVE = native_target()
except UnsupportedTargetError:
    _NATIVE = None
DEFAULT_TARGET = _NATIVE.triple if _NATIVE else "x86_64-unknown-linux-musl"


def _fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _target(value: str):
    try:
        return describe_target(value)
    except UnsupportedTargetError as error:
        _fail(str(error))


def doctor(args: argparse.Namespace) -> int:
    description = _target(args.target)
    report: dict[str, object] = {
        "host": platform.machine(),
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "native_target": _NATIVE.triple if _NATIVE else None,
        "target": description.triple,
        "docker": shutil.which("docker"),
        "cache": str(CACHE),
        "phases": str(PHASES),
    }
    try:
        sources = load_sources(SOURCES_LOCK)
        bootstrap = load_bootstrap(BOOTSTRAP_LOCK)
        extras = bootstrap_inputs(bootstrap, description.triple)
    except InputError as error:
        report["locks"] = str(error)
        print(json.dumps(report, indent=2))
        return 1
    selected = [
        item for item in sources if item.target in ("all", description.triple)
    ]
    report["sources"] = {
        "total": len(sources),
        "selected": [item.name for item in selected],
        "bootstrap": [item.name for item in extras],
    }
    cache = Cache(CACHE)
    missing = []
    for item in [*selected, *extras]:
        try:
            cache.require(item)
        except InputError:
            missing.append(item.name)
    report["cache_missing"] = missing
    toolchain_dir = _toolchain_directory(description)
    if toolchain_dir.is_dir():
        try:
            report["toolchain"] = toolchain.verify(toolchain_dir, description)
        except toolchain.ToolchainError as error:
            report["toolchain_error"] = str(error)
            print(json.dumps(report, indent=2))
            return 1
    else:
        report["toolchain"] = None
    print(json.dumps(report, indent=2))
    return 0


def fetch(args: argparse.Namespace) -> int:
    description = _target(args.target)
    try:
        sources = load_sources(SOURCES_LOCK)
        bootstrap = load_bootstrap(BOOTSTRAP_LOCK)
    except InputError as error:
        _fail(str(error))
    selected = [item for item in sources if item.target in ("all", description.triple)]
    selected.extend(bootstrap_inputs(bootstrap, description.triple))
    cache = Cache(CACHE)
    total = 0
    for item in selected:
        try:
            cache.require(item)
            outcome = "cached"
        except InputError:
            cache.fetch(item)
            outcome = "downloaded"
        size = item.size if item.size is not None else digest_bytes(cache.require(item))[1]
        total += size
        print(f"{item.name} {item.version} {outcome} {size} B")
    print(f"{len(selected)} inputs, {total} B, cache {CACHE}")
    try:
        sandbox.pull_image(bootstrap, description.docker_platform)
    except SandboxError as error:
        _fail(str(error))
    print(f"builder base {sandbox.image_reference(bootstrap)} for {description.docker_platform}")
    return 0


_NOT_IMPLEMENTED = {
    "configure": "G3 configures CMake with the locked toolchain",
    "build": "C1 builds CMake",
    "test": "C2 runs acceptance suites",
    "package": "D5 stages and publishes the archive",
    "qualify": "D5 qualifies packaged bytes",
    "reproduce": "D5 reproduces two clean builds",
    "benchmark": "E1 measures against the Kitware reference",
}


def _target_root(description) -> Path:
    return BUILD_ROOT / description.triple


def _toolchain_directory(description) -> Path:
    return _target_root(description) / "phases" / "prepare" / "toolchain"


def _required_inputs(
    sources, lock, description
) -> tuple[dict[str, object], list[object]]:
    selected = [item for item in sources if item.target in ("all", description.triple)]
    extras = bootstrap_inputs(lock, description.triple)
    return {item.name: item for item in selected}, extras


def _controller_digest() -> str:
    material = {
        "build.py": digest_bytes(ROOT / "build.py")[0],
        "buildsys": tree_digest(ROOT / "buildsys"),
        "dockerfile": digest_bytes(DOCKERFILE)[0],
        "provenance": tree_digest(ROOT / "tests" / "fixtures" / "provenance"),
    }
    from buildsys.inputs import canonical_json, identity

    return identity(canonical_json(material).encode())


def prepare(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if sandbox.in_container():
        return _prepare_inside(description)
    if platform.machine() != description.machine:
        _fail(
            f"--target {description.triple} does not match the running machine "
            f"({platform.machine()}); no emulation is used"
        )
    try:
        sources = load_sources(SOURCES_LOCK)
        lock = load_bootstrap(BOOTSTRAP_LOCK)
    except InputError as error:
        _fail(str(error))
    cache = Cache(CACHE)
    selected, extras = _required_inputs(sources, lock, description)
    missing = []
    for item in [*selected.values(), *extras]:
        try:
            cache.require(item)
        except InputError:
            missing.append(item.name)
    if missing:
        _fail(f"missing locked inputs: {', '.join(missing)}; run `build.py fetch`")
    try:
        tag = sandbox.build_image(lock, description, DOCKERFILE, cache, WORK / "tmp" / "image")
    except (SandboxError, InputError) as error:
        _fail(str(error))
    probe = sandbox.network_boundary_selftest(tag, description, WORK / "tmp" / "probe")
    if not probe["ok"]:
        _fail(f"network boundary probe failed: {json.dumps(probe, indent=2)}")
    result = sandbox.run_sealed(
        tag,
        ["python3", "build.py", "prepare", "--target", description.triple, "--in-container"],
        target=description,
        mounts=[(ROOT, "/src")],
        env={"TMPDIR": str(WORK / "tmp"), "PYTHONPATH": "/src"},
        timeout=3600,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        _fail(f"prepare failed inside the sealed container ({result.returncode})")
    evidence = {
        "image": tag,
        "image_fingerprint": sandbox.image_fingerprint(lock, description, DOCKERFILE),
        "network_mode": result.network_mode,
        "networks": result.networks,
        "probe": probe,
    }
    root = _target_root(description)
    root.mkdir(parents=True, exist_ok=True)
    evidence_path = root / "isolation.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0


def _prepare_inside(description) -> int:
    try:
        sources = load_sources(SOURCES_LOCK)
        lock = load_bootstrap(BOOTSTRAP_LOCK)
    except InputError as error:
        _fail(str(error))
    cache = Cache(CACHE, offline=True)
    selected, extras = _required_inputs(sources, lock, description)
    inputs: dict[str, str] = {}
    toolchain_input = selected.get(f"llvm-toolchain-{description.machine}")
    musl_input = selected.get("musl-source")
    headers = next((item for item in extras if item.name == "linux-headers"), None)
    if toolchain_input is None or musl_input is None or headers is None:
        _fail(f"{description.triple}: lock lacks toolchain, musl, or linux-headers")
    inputs["toolchain"] = toolchain_input.sha256
    inputs["musl"] = musl_input.sha256
    inputs["linux-headers"] = headers.sha256
    inputs["controller"] = _controller_digest()
    inputs["image"] = sandbox.image_fingerprint(lock, description, DOCKERFILE)
    phases = PhaseCache(_target_root(description) / "phases")

    def action(directory: Path) -> None:
        toolchain_dir = toolchain.install(
            cache.require(toolchain_input), directory / "toolchain"
        )
        identity = toolchain.verify(toolchain_dir, description)
        (directory / "toolchain.json").write_text(json.dumps(identity, indent=2) + "\n")
        sysroot.build(
            cache.require(musl_input),
            cache.require(headers),
            toolchain_dir,
            description,
            directory / "sysroot",
            WORK / "tmp" / f"sysroot-{os.getpid()}",
        )
        sysroot_report = sysroot.verify(
            directory / "sysroot", description, toolchain_dir
        )
        (directory / "sysroot.json").write_text(
            json.dumps(sysroot_report, indent=2) + "\n"
        )
        fixture = subprocess.run(
            [
                sys.executable,
                str(PROVENANCE),
                "--toolchain",
                str(toolchain_dir),
                "--sysroot",
                str(directory / "sysroot"),
                "--target",
                description.triple,
                "--work",
                str(directory / "fixture"),
                "--output",
                str(directory / "provenance.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        if fixture.returncode != 0:
            raise PhaseError(
                f"provenance fixture failed ({fixture.returncode}):\n"
                f"{fixture.stdout}\n{fixture.stderr}"
            )
        print(fixture.stdout.strip())

    try:
        result = phases.run("prepare", inputs, action)
    except (InputError, PhaseError, toolchain.ToolchainError, sysroot.SysrootError) as error:
        _fail(str(error))
    state = "reused" if result.reused else "built"
    print(f"prepare {state} at {result.directory} ({result.fingerprint[:16]})")
    return 0


def _not_implemented(args: argparse.Namespace) -> int:
    _fail(f"{args.command} is not implemented yet: {_NOT_IMPLEMENTED[args.command]}")


def _controller_test(args: argparse.Namespace) -> int:
    directory = ROOT / "tests" / "controller"
    modules = sorted(path.name for path in directory.glob("test_*.py"))
    if args.filter:
        modules = [module for module in modules if args.filter in module]
    if not modules:
        print(f"error: no controller test modules match {args.filter!r}", file=sys.stderr)
        return 1
    environment = {**os.environ, "PYTHONPATH": str(ROOT)}

    def run(module: str) -> tuple[str, subprocess.CompletedProcess]:
        return module, subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/controller",
                "-p",
                module,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=min(len(modules), os.cpu_count() or 4)) as pool:
        results = list(pool.map(run, modules))
    executed = 0
    failed: list[str] = []
    for module, result in results:
        counted = re.search(r"^Ran (\d+) tests? in ", result.stderr, re.MULTILINE)
        count = int(counted.group(1)) if counted else 0
        executed += count
        if count == 0:
            failed.append(module)
        elif result.returncode != 0:
            failed.append(module)
        if result.returncode != 0 or count == 0:
            print(f"--- {module} (exit {result.returncode}, {count} tests)")
            print(result.stdout + result.stderr)
    elapsed = time.monotonic() - started
    summary = (
        f"Ran {executed} tests in {len(modules)} modules in {elapsed:.1f}s; "
        f"{len(failed)} failed"
    )
    print(summary + (f": {', '.join(failed)}" if failed else ""))
    return 1 if failed or executed == 0 else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    commands = (
        "doctor",
        "fetch",
        "prepare",
        "configure",
        "build",
        "test",
        "package",
        "qualify",
        "reproduce",
        "benchmark",
    )
    for command in commands:
        child = subparsers.add_parser(command)
        child.add_argument("--target", default=DEFAULT_TARGET)
        if command == "doctor":
            child.set_defaults(handler=doctor)
        elif command == "fetch":
            child.set_defaults(handler=fetch)
        elif command == "prepare":
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=prepare)
        else:
            child.set_defaults(handler=_not_implemented)
    controller = subparsers.add_parser("controller-test")
    controller.add_argument("-k", dest="filter", default=None)
    controller.set_defaults(handler=_controller_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (InputError, PhaseError) as error:
        _fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
