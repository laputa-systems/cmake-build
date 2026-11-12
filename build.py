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
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from buildsys import (
    benchmark,
    bootstrap,
    budgets,
    cmake,
    dependencies,
    elf,
    generations,
    licenses,
    package,
    patches,
    qualify,
    reference,
    reproduce,
    rust,
    sandbox,
    stage,
    sysroot,
    tls,
    toolchain,
)
from buildsys.inputs import (
    BootstrapLock,
    Cache,
    Input,
    InputError,
    bootstrap_inputs,
    canonical_json,
    digest_file,
    identity,
    load_bootstrap,
    load_sources,
    tree_digest,
)
from buildsys.phases import PhaseCache, PhaseError
from buildsys.sandbox import SandboxError
from buildsys.targets import (
    UnsupportedTargetError,
    native_target,
)
from buildsys.targets import (
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
    if args.vendor_in_container:
        if not sandbox.in_container() or _NATIVE is None:
            _fail("Rust vendoring requires a native builder container")
        lock = load_bootstrap(BOOTSTRAP_LOCK)
        source = next((item for item in load_sources(SOURCES_LOCK) if item.name == "rustls-ffi-source"), None)
        if source is None:
            _fail("source lock lacks rustls-ffi-source")
        rust_root = WORK / "rust" / _NATIVE.triple
        try:
            vendored = rust.vendor(Cache(CACHE, offline=True), bootstrap_inputs(lock, _NATIVE.triple), source,
                                   ROOT / "patches/rustls-ffi/0001-graviola-provider.patch", rust_root, WORK / "tmp")
            tls.check_vendored(vendored, rust_root / "phases/tools/bin", description.triple, WORK / "tmp")
        except (rust.RustError, tls.TlsError, InputError, PhaseError) as error:
            _fail(str(error))
        print(f"TLS dependency gate passed for {description.triple}")
        return 0
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
        size = item.size if item.size is not None else digest_file(cache.require(item))[1]
        total += size
        print(f"{item.name} {item.version} {outcome} {size} B")
    print(f"{len(selected)} inputs, {total} B, cache {CACHE}")
    try:
        sandbox.pull_image(bootstrap, description.docker_platform)
        sandbox.pull_reference(bootstrap, description.docker_platform)
    except SandboxError as error:
        _fail(str(error))
    print(f"builder base {sandbox.image_reference(bootstrap)} for {description.docker_platform}")
    print(f"reference base {bootstrap.reference_image} for {description.docker_platform}")
    if _NATIVE is None:
        _fail("Rust vendoring requires a supported native machine")
    rust_source = next((item for item in sources if item.name == "rustls-ffi-source"), None)
    if rust_source is None:
        _fail("source lock lacks rustls-ffi-source")
    try:
        native_inputs = bootstrap_inputs(bootstrap, _NATIVE.triple)
        for item in native_inputs:
            try:
                cache.require(item)
            except InputError:
                cache.fetch(item)
        rust_root = WORK / "rust" / _NATIVE.triple
        rust.install_tools(cache, native_inputs, rust_root, WORK / "tmp")
        if _NATIVE != description:
            sandbox.pull_image(bootstrap, _NATIVE.docker_platform)
        tag = sandbox.build_image(bootstrap, _NATIVE, DOCKERFILE, cache, WORK / "tmp/image")
        sandbox.run_fetch(tag, _NATIVE, ROOT, description.triple)
    except (rust.RustError, sandbox.SandboxError, InputError, PhaseError) as error:
        _fail(str(error))
    return 0


def _target_root(description) -> Path:
    return BUILD_ROOT / description.triple


def _toolchain_directory(description) -> Path:
    return _target_root(description) / "phases" / "prepare" / "toolchain"


def _required_inputs(
    sources: list[Input], lock: BootstrapLock, description
) -> tuple[dict[str, Input], list[Input]]:
    selected = [item for item in sources if item.target in ("all", description.triple)]
    extras = bootstrap_inputs(lock, description.triple)
    return {item.name: item for item in selected}, extras


def _controller_digest() -> str:
    material = {
        "build.py": digest_file(ROOT / "build.py")[0],
        "buildsys": tree_digest(ROOT / "buildsys", exclude={"__pycache__"}),
        "dockerfile": digest_file(DOCKERFILE)[0],
        "provenance": tree_digest(PROVENANCE.parent, exclude={"__pycache__"}),
        "native_fixture": tree_digest(ROOT / "tests/fixtures/native"),
    }
    from buildsys.inputs import canonical_json, identity

    return identity(canonical_json(material).encode())


def prepare(args: argparse.Namespace) -> int:
    description = _target(args.target)
    patches.verify_inventory(ROOT / "patches")
    if args.in_container:
        if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
            _fail("prepare requires a sealed container with only loopback networking")
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
        env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"},
        timeout=3600,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        _fail(f"prepare failed inside the sealed container ({result.returncode})")
    print(result.stdout, end="")
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
    patches.verify_inventory(ROOT / "patches")
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


def configure(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if args.in_container:
        if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
            _fail("configure requires a sealed container with only loopback networking")
        return _configure_inside(description)
    prepare(argparse.Namespace(target=description.triple, in_container=False))
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    tag = sandbox.image_tag(lock, description, DOCKERFILE)
    result = sandbox.run_sealed(
        tag, ["python3", "build.py", "configure", "--target", description.triple, "--in-container"],
        target=description, mounts=[(ROOT, "/src")],
        env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"}, timeout=3600,
    )
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        _fail(f"configure failed inside the sealed container ({result.returncode})")
    return 0


def _configure_inside(description) -> int:
    _prepare_inside(description)
    sources = load_sources(SOURCES_LOCK)
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    selected = {item.name: item for item in sources if item.target in ("all", description.triple)}
    cache = Cache(CACHE, offline=True)
    cmake = selected["cmake-source"]
    samurai = selected["samurai-source"]
    ninja = selected["ninja-source"]
    packages = [item for item in bootstrap_inputs(lock, description.triple) if item.name == "cmake"]
    if len(packages) != 1:
        _fail(f"{description.triple}: lock must contain exactly one bootstrap CMake package")
    version = re.fullmatch(r"(.+)-r[0-9]+", packages[0].version)
    if version is None:
        _fail(f"{description.triple}: invalid bootstrap CMake package version {packages[0].version!r}")
    phases = PhaseCache(_target_root(description) / "phases")
    prepared = phases.directory("prepare")
    record = json.loads((prepared / "phase.json").read_text())
    tc = prepared / "toolchain"
    toolchain.verify(tc, description)
    inputs = {
        "prepare": record["output_digest"],
        "cmake": cmake.sha256,
        "samurai": samurai.sha256,
        "ninja": ninja.sha256,
        "image": sandbox.image_fingerprint(lock, description, DOCKERFILE),
        "controller": _controller_digest(),
    }

    def action(directory: Path) -> None:
        bootstrap.build(cmake_archive=cache.require(cmake), samurai_archive=cache.require(samurai),
                        ninja_archive=cache.require(ninja), directory=directory, tc=tc,
                        sysroot=prepared / "sysroot", target=description, bootstrap_version=version.group(1))

    built = phases.run("bootstrap", inputs, action)
    bootstrap_record = json.loads((built.directory / "phase.json").read_text())
    result = phases.run("configure", {"bootstrap": bootstrap_record["output_digest"], "image": inputs["image"], "controller": inputs["controller"]},
                        lambda directory: bootstrap.configure(built.directory, directory, tc, description))
    print(f"configure {'reused' if result.reused else 'built'} at {result.directory} ({result.fingerprint[:16]})")
    return 0


def build_command(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if args.in_container:
        if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
            _fail("build requires a sealed container with only loopback networking")
        if _NATIVE != description:
            _fail(f"{description.triple} does not match the running machine; no emulation is used")
        mode = cmake.BuildMode.QUALIFICATION if args.qualification_build else cmake.BuildMode.DEVELOPMENT
        return _build_inside(description, mode)
    configure(argparse.Namespace(target=description.triple, in_container=False))
    scratch = WORK / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    path = f"{os.environ.get('PATH', '')}{os.pathsep}{Path.home() / '.cargo/bin'}"
    wrapper = shutil.which("kache", path=path)
    if not wrapper:
        _fail("kache is required for Rust builds")
    rust.install_wrapper(Path(wrapper), scratch)
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    tag = sandbox.image_tag(lock, description, DOCKERFILE)
    command = ["python3", "build.py", "build", "--target", description.triple, "--in-container"]
    if args.qualification_build:
        command.append("--qualification-build")
    result = sandbox.run_sealed(
        tag, command,
        target=description, mounts=[(ROOT, "/src")],
        env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"}, timeout=7200,
    )
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        _fail(f"build failed inside the sealed container ({result.returncode})")
    return 0


def _build_inside(description, mode: cmake.BuildMode) -> int:
    _configure_inside(description)
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    sources = {item.name: item for item in load_sources(SOURCES_LOCK) if item.target in ("all", description.triple)}
    if "cmake-source" not in sources or "rustls-ffi-source" not in sources:
        _fail("source lock lacks CMake or Rustls")
    inventory = patches.verify_inventory(ROOT / "patches")
    prepared = _target_root(description) / "phases/prepare"
    bootstrap_directory = _target_root(description) / "phases/bootstrap"
    archive = rust.build_static(WORK / "rust" / description.triple, prepared, description,
                                WORK / "tmp/build-kache", WORK / "tmp")
    bootstrap_record = json.loads((bootstrap_directory / "phase.json").read_text())
    rust_record = json.loads((archive.parents[3] / "phase.json").read_text())
    prepare_record = json.loads((prepared / "phase.json").read_text())
    inputs = {
        "prepare": prepare_record["output_digest"],
        "bootstrap": bootstrap_record["output_digest"],
        "rustls": rust_record["output_digest"],
        "patches": identity(canonical_json([(item.name, item.sha256) for item in inventory]).encode()),
        "image": sandbox.image_fingerprint(lock, description, DOCKERFILE),
        "controller": _controller_digest(),
        "mode": identity(mode.value.encode()),
    }
    if mode is cmake.BuildMode.DEVELOPMENT:
        inputs["compiler_cache"] = rust.wrapper_identity(WORK / "tmp/build-kache")
    phases = PhaseCache(_target_root(description) / "phases")
    result = phases.run("cmake", inputs, lambda directory: cmake.build(
        bootstrap=bootstrap_directory, prepared=prepared, archive=archive, inventory=inventory,
        directory=directory, target=description, cmake_version=sources["cmake-source"].version,
        rustls_version=sources["rustls-ffi-source"].version, mode=mode,
        kache=WORK / "tmp/build-kache", compiler_cache=WORK / "compiler-cache" / description.triple,
    ))
    print(f"cmake {'reused' if result.reused else 'built'} at {result.directory} ({result.fingerprint[:16]})")
    return 0


def test_command(args: argparse.Namespace, *, prepare_only: bool = False) -> int:
    description = _target(args.target)
    suites = {"basic": qualify.basic, "parity": qualify.parity, "network": qualify.network,
              "projects": qualify.projects, "upstream": qualify.upstream}
    selected = args.suite.split(",")
    if len(set(selected)) != len(selected) or any(name not in suites for name in selected):
        _fail(f"unsupported test suite {args.suite!r}; available: {', '.join(suites)}")
    if args.in_container:
        if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
            _fail("test staging requires a sealed container with only loopback networking")
        if _NATIVE != description:
            _fail(f"{description.triple} does not match the running machine; no emulation is used")
        _build_inside(description, cmake.BuildMode.QUALIFICATION)
        rust_phases = WORK / "rust" / description.triple / "phases"
        tls.check_vendored(rust_phases / "vendor", rust_phases / "tools/bin", description.triple, WORK / "tmp")
        phases = PhaseCache(_target_root(description) / "phases")
        if "upstream" in selected:
            prepared = phases.directory("prepare")
            bootstrap_directory = phases.directory("bootstrap")
            prepare_record = json.loads((prepared / "phase.json").read_text())
            bootstrap_record = json.loads((bootstrap_directory / "phase.json").read_text())
            source = next(item for item in load_sources(SOURCES_LOCK) if item.name == "cmake-source")
            inputs = {"prepare": prepare_record["output_digest"], "bootstrap": bootstrap_record["output_digest"],
                      "image": sandbox.image_fingerprint(load_bootstrap(BOOTSTRAP_LOCK), description, DOCKERFILE),
                      "controller": _controller_digest()}
            result = phases.run("reference", inputs, lambda directory: reference.build(
                bootstrap=bootstrap_directory, prepared=prepared, directory=directory,
                target=description, version=source.version))
            print(f"reference {'reused' if result.reused else 'built'} at {result.directory}")
        cmake_phase = phases.directory("cmake")
        record = json.loads((cmake_phase / "phase.json").read_text())
        source = next(item for item in load_sources(SOURCES_LOCK) if item.name == "cmake-source")
        license_inputs = {"cmake": record["output_digest"], "controller": _controller_digest(),
                          "licenses": tree_digest(ROOT / "licenses"), "notice": digest_file(ROOT / "NOTICE")[0]}
        def stage_distribution(directory: Path) -> None:
            stage.stage(cmake_phase, directory, description.triple, source.version, ROOT / "licenses", ROOT / "NOTICE")
            for name in ("cmake", "ctest", "cpack"):
                elf.strip_debug(cmake_phase / "build/bin" / name, directory / "bin" / name, description,
                                phases.directory("prepare") / "toolchain/bin")
        result = phases.run("stage", license_inputs, stage_distribution)
        print(f"stage {'reused' if result.reused else 'built'} at {result.directory}")
        return 0
    build_command(argparse.Namespace(target=description.triple, in_container=False, qualification_build=True))
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    image = sandbox.image_tag(lock, description, DOCKERFILE)
    result = sandbox.run_sealed(
        image, ["python3", "build.py", "test", "--target", description.triple, "--suite", args.suite, "--in-container"],
        target=description, mounts=[(ROOT, "/src")],
        env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"}, timeout=7200,
    )
    print(result.stdout, end="")
    if result.returncode:
        _fail(f"staging failed inside the sealed container ({result.returncode}):\n{result.stderr}")
    if not prepare_only:
        for name in selected:
            suites[name](root=ROOT, phase=_target_root(description) / "phases/stage", image=image, target=description)
    return 0


def _source_commit() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "build.py", "buildsys", "docker", "patches", "tests", "licenses", "NOTICE", "sources.lock.json", "bootstrap.lock.json", "release-budgets.json"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    if status.stdout:
        _fail("packaging requires committed build and qualification inputs")
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    commit = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        _fail("repository commit identity is invalid")
    return commit


def _package_inside(description, commit: str) -> Path:
    import tarfile

    source = next(item for item in load_sources(SOURCES_LOCK) if item.name == "cmake-source")
    toolchain_input = next(item for item in load_sources(SOURCES_LOCK) if item.name == f"llvm-toolchain-{description.machine}")
    source_archive = Cache(CACHE, offline=True).require(source)
    with tarfile.open(source_archive, "r:gz") as archive:
        first = archive.next()
        if first is None:
            _fail("cmake source archive is empty")
        epoch = int(first.mtime)
    phases = _target_root(description) / "phases"
    cmake_phase = phases / "cmake"
    cmake_record = json.loads((cmake_phase / "phase.json").read_text())
    stage_phase = phases / "stage"
    stage_record = json.loads((stage_phase / "phase.json").read_text())
    if cmake_record["inputs"].get("mode") != identity(cmake.BuildMode.QUALIFICATION.value.encode()):
        _fail("packaging requires an uncached qualification build")
    if (cmake_phase / "state.json").exists() or tree_digest(cmake_phase, exclude={"phase.json", "state.json"}) != cmake_record["output_digest"]:
        _fail("built CMake no longer matches its phase record")
    if (stage_phase / "state.json").exists() or stage_record["inputs"].get("cmake") != cmake_record["output_digest"] or tree_digest(stage_phase, exclude={"phase.json", "state.json"}) != stage_record["output_digest"]:
        _fail("staged CMake no longer matches its phase record")
    isolation = json.loads((_target_root(description) / "isolation.json").read_text())
    if isolation.get("network_mode") != "none" or isolation.get("probe", {}).get("ok") is not True:
        _fail("packaging requires successful network isolation evidence")
    inventory = patches.verify_inventory(ROOT / "patches")
    patch_identity = identity(canonical_json([(item.name, item.sha256) for item in inventory]).encode())
    cache = (cmake_phase / "build/CMakeCache.txt").read_text().splitlines()
    flag_names = {"CMAKE_C_FLAGS", "CMAKE_C_FLAGS_RELEASE", "CMAKE_CXX_FLAGS", "CMAKE_CXX_FLAGS_RELEASE", "CMAKE_EXE_LINKER_FLAGS", "CMAKE_C_STANDARD_LIBRARIES", "CMAKE_CXX_STANDARD_LIBRARIES"}
    flags = {line.split(":", 1)[0]: line.split("=", 1)[1] for line in cache if ":" in line and "=" in line and line.split(":", 1)[0] in flag_names}
    if set(flags) != flag_names:
        _fail("built CMake cache lacks effective compiler or linker flags")
    toolchain_report = json.loads((phases / "prepare/toolchain.json").read_text())
    rust_root = WORK / "rust" / description.triple / "phases"
    projects = list((rust_root / "vendor/source").iterdir())
    if len(projects) != 1 or not projects[0].is_dir():
        _fail("vendored Rustls source has an invalid layout")
    tools = rust_root / "tools/bin"
    with tempfile.TemporaryDirectory(prefix="package-cargo-", dir=WORK / "tmp") as temporary:
        cargo_home = Path(temporary)
        rust._cargo_config(cargo_home, rust_root / "vendor")
        env = {**rust._rust_environment(), "CARGO_HOME": str(cargo_home), "TMPDIR": str(WORK / "tmp"),
               "RUSTC": str(tools / "rustc"), "RUSTC_WRAPPER": "",
               "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}"}
        rust_closure = rust._run([
            str(tools / "cargo"), "tree", "--manifest-path", str(projects[0] / "Cargo.toml"), "--locked", "--offline",
            "--no-default-features", "--features", "graviola", "--target", description.triple,
            "-e", "normal,build", "--prefix", "none", "--format", "{p}",
        ], cwd=projects[0], env=env)
        std_home = cargo_home / "std-home"
        std_home.mkdir()
        std_source = rust_root / "tools/lib/rustlib/src/rust/library"
        std_env = {**env, "CARGO_HOME": str(std_home)}
        std_closure = rust._run([
            str(tools / "cargo"), "tree", "--locked", "--offline", "-p", "std",
            "--features", "panic-unwind,backtrace,llvm-libunwind", "--target", description.triple,
            "-e", "normal,build", "--prefix", "none", "--format", "{p}",
        ], cwd=std_source, env=std_env)
    licenses.verify_closure(rust_closure, std_closure, ROOT / "licenses")
    locked = [item for item in load_sources(SOURCES_LOCK)
              if item.target in ("all", description.triple) and item.role in ("source", "build-source")]
    locked.extend(bootstrap_inputs(load_bootstrap(BOOTSTRAP_LOCK), description.triple))
    build_inputs = [{"name": item.name, "version": item.version, "sha256": item.sha256} for item in locked]
    wrapper = WORK / "tmp/build-kache"
    engine = wrapper.with_name("kache-engine")
    wrapper_info = {"client_sha256": digest_file(wrapper)[0],
                    "engine_sha256": digest_file(engine)[0] if engine.is_file() else None}
    metadata = {
        "schema_version": 1,
        "source": {"version": source.version, "sha256": source.sha256, "commit": commit, "patch_set": patch_identity},
        "toolchain": {"version": toolchain_input.version, "sha256": toolchain_input.sha256, "compiler": toolchain_report["clang"]},
        "target": {"triple": description.triple, "cpu_baseline": description.cpu_baseline},
        "flags": flags,
        "dependencies": {"native": (cmake_phase / "dependencies.md").read_text(),
                         "rustls": rust_closure.splitlines(), "rust_std": std_closure.splitlines(),
                         "build_inputs": build_inputs},
        "build": {"mode": "qualification", "image": isolation["image_fingerprint"], "network": "none", "network_probe": "passed", "rust_wrapper": wrapper_info},
        "elf_audit": "passed",
    }
    destination = WORK / "artifacts" / description.triple / f"cmake-{source.version}-{description.triple}.tar.xz"
    package.create(stage_phase, destination, metadata, epoch)
    package.inspect(destination)
    sha256 = digest_file(destination)[0]
    candidate = {"archive": destination.name, "sha256": sha256, "size": destination.stat().st_size, "commit": commit}
    temporary = destination.with_name("candidate.json.tmp")
    temporary.write_text(json.dumps(candidate, sort_keys=True, indent=2) + "\n")
    temporary.replace(destination.with_name("candidate.json"))
    print(f"package: {destination} ({sha256})")
    return destination


def package_command(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if args.in_container:
        if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
            _fail("packaging requires a sealed container with only loopback networking")
        if _NATIVE != description:
            _fail(f"{description.triple} does not match the running machine; no emulation is used")
        commit = os.environ.get("CMAKE_BUILD_COMMIT", "")
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            _fail("packaging requires a repository commit identity")
        _package_inside(description, commit)
        return 0
    commit = _source_commit()
    test_command(argparse.Namespace(target=description.triple, suite="basic", in_container=False))
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    image = sandbox.image_tag(lock, description, DOCKERFILE)
    result = sandbox.run_sealed(
        image, ["python3", "build.py", "package", "--target", description.triple, "--in-container"],
        target=description, mounts=[(ROOT, "/src")],
        env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src", "CMAKE_BUILD_COMMIT": commit}, timeout=1800,
    )
    print(result.stdout, end="")
    if result.returncode:
        _fail(f"packaging failed inside the sealed container ({result.returncode}):\n{result.stderr}")
    return 0


def qualify_command(args: argparse.Namespace) -> int:
    description = _target(args.target)
    source = next(item for item in load_sources(SOURCES_LOCK) if item.name == "cmake-source")
    directory = WORK / "artifacts" / description.triple
    archive = directory / f"cmake-{source.version}-{description.triple}.tar.xz"
    candidate_path = directory / "candidate.json"
    if not archive.exists() and not candidate_path.exists():
        package_command(argparse.Namespace(target=description.triple, in_container=False))
    try:
        candidate = json.loads(candidate_path.read_text())
    except (OSError, ValueError) as error:
        _fail(f"candidate record is missing or invalid: {error}")
    if (not isinstance(candidate, dict) or not archive.is_file()
            or candidate.get("archive") != archive.name or candidate.get("commit") != _source_commit()
            or not isinstance(candidate.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", candidate["sha256"]) is None
            or candidate.get("size") != archive.stat().st_size):
        _fail("candidate record does not match the archive or repository commit")
    if digest_file(archive)[0] != candidate["sha256"]:
        _fail("candidate archive has been modified")
    size_budgets = budgets.read(ROOT / "release-budgets.json")
    test_command(argparse.Namespace(target=description.triple, suite="upstream", in_container=False), prepare_only=True)
    lock = load_bootstrap(BOOTSTRAP_LOCK)
    image = sandbox.image_tag(lock, description, DOCKERFILE)
    def run(tree: Path) -> dict:
        sizes = budgets.check_size(size_budgets, description.triple, tree, tree.parent / "artifact.tar.xz")
        print(f"size budgets passed: {sizes}")
        qualify.projects(root=ROOT, phase=tree / "usr", image=image, target=description)
        qualify.upstream(root=ROOT, phase=tree / "usr", image=image, target=description)
        for name, suite in (("basic", qualify.basic), ("parity", qualify.parity), ("network", qualify.network)):
            suite(root=ROOT, phase=tree / "usr", image=image, target=description)
        report = (ROOT / "docs/qualification.md").read_text()
        marker = f"## Latest upstream subset: {description.triple}"
        section = report.partition(marker)[2].partition("\n## ")[0].strip()
        if not section:
            _fail("upstream qualification report is missing")
        return {"basic": "passed", "parity": "passed", "network": "passed", "projects": "passed", "upstream": section,
                "sizes": sizes}
    generation = generations.qualify(WORK / "generations" / description.triple, archive, candidate["sha256"], run)
    print(f"qualified generation: {generation}")
    return 0


def reproduce_command(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if description != _NATIVE:
        _fail(f"{description.triple} does not match the running machine; no emulation is used")
    source = next(item for item in load_sources(SOURCES_LOCK) if item.name == "cmake-source")
    differences = reproduce.run(ROOT, description.triple, source.version, _source_commit())
    if differences:
        for difference in differences:
            print(difference)
        return 1
    print("reproducibility: file trees and archive bytes are identical")
    return 0


def benchmark_command(args: argparse.Namespace) -> int:
    description = _target(args.target)
    if description != _NATIVE:
        _fail(f"{description.triple} does not match the running machine; no emulation is used")
    benchmark.run(ROOT, description)
    print("benchmark report: docs/performance.md")
    return 0


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
        if count == 0 or result.returncode != 0:
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
            child.add_argument("--vendor-in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=fetch)
        elif command == "prepare":
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=prepare)
        elif command == "configure":
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=configure)
        elif command == "build":
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.add_argument("--qualification-build", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=build_command)
        elif command == "test":
            child.add_argument("--suite", required=True)
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=test_command)
        elif command == "package":
            child.add_argument("--in-container", action="store_true", help=argparse.SUPPRESS)
            child.set_defaults(handler=package_command)
        elif command == "qualify":
            child.set_defaults(handler=qualify_command)
        elif command == "reproduce":
            child.set_defaults(handler=reproduce_command)
        else:
            child.set_defaults(handler=benchmark_command)
    controller = subparsers.add_parser("controller-test")
    controller.add_argument("-k", dest="filter", default=None)
    controller.set_defaults(handler=_controller_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (InputError, PhaseError, benchmark.BenchmarkError, bootstrap.BootstrapError, budgets.BudgetError, cmake.CMakeBuildError, dependencies.DependencyError,
            elf.AuditError, patches.PatchError, qualify.QualificationError, reference.ReferenceError, rust.RustError,
            sandbox.SandboxError, stage.StageError, tls.TlsError) as error:
        _fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
