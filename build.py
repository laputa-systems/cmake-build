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
)
from buildsys.phases import PhaseCache, PhaseError
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
SOURCES_LOCK = ROOT / "sources.lock.json"
BOOTSTRAP_LOCK = ROOT / "bootstrap.lock.json"

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
    return 0


_NOT_IMPLEMENTED = {
    "prepare": "G2 builds the sealed image and sysroot",
    "configure": "G3 configures CMake with the locked toolchain",
    "build": "C1 builds CMake",
    "test": "C2 runs acceptance suites",
    "package": "D5 stages and publishes the archive",
    "qualify": "D5 qualifies packaged bytes",
    "reproduce": "D5 reproduces two clean builds",
    "benchmark": "E1 measures against the Kitware reference",
}


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
