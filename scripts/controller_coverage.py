from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from buildsys.inputs import Cache, Input, InputError, load_bootstrap
from buildsys.sandbox import SandboxError, image_tag, run_sealed
from buildsys.targets import UnsupportedTargetError, native_target, target

ROOT = Path(__file__).resolve().parents[1]
PYTHON_RELEASE = "20261026"
PYTHON_VERSION = "3.15.2"
COVERAGE_VERSION = "7.17.3"
PYTHON_ARCHIVES = {
    "aarch64": ("2996760114a56a9cbe9111f8a55e8a2e67735c1ff5b5da1bbdedf06ccc26dbb4", 30101964),
    "x86_64": ("9723f525ec21a52e5e3b18165ad3d553f1af38aba76125ddae25b156ed9c9202", 29970422),
}
COVERAGE_WHEELS = {
    "aarch64": ("228f4bcecadcbb1ec3ed088b0595c5c08f3fca01406b72e8a02209a3af16aff9", 263461),
    "x86_64": ("24389d7d50f1fe98ac8d8ec1c946656a75b97d953b51a714484e174ed9f48eb1", 263276),
}

COVERAGE_CONFIG = """[run]
branch = true
parallel = true
patch = subprocess
relative_files = true
source =
    build
    buildsys
"""


def prepare_tools(work: Path, architecture: str, cache: Cache) -> None:
    python_sha, python_size = PYTHON_ARCHIVES[architecture]
    python_url = (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{PYTHON_RELEASE}/cpython-{PYTHON_VERSION}%2B{PYTHON_RELEASE}-"
        f"{architecture}-unknown-linux-musl-install_only_stripped.tar.gz"
    )
    archive = cache.fetch(Input(
        name="controller-coverage-python",
        version=PYTHON_VERSION,
        urls=(python_url,),
        sha256=python_sha,
        size=python_size,
    ))
    wheel_sha, wheel_size = COVERAGE_WHEELS[architecture]
    wheel_url = (
        "https://pypi.17166969.xyz/current/wheels/"
        f"coverage-{COVERAGE_VERSION}-cp315-cp315-musllinux_1_2_{architecture}.whl"
    )
    wheel = cache.fetch(Input(
        name="controller-coverage-wheel",
        version=COVERAGE_VERSION,
        urls=(wheel_url,),
        sha256=wheel_sha,
        size=wheel_size,
    ))
    with tarfile.open(archive, "r:gz") as python:
        runtime_paths = {("python", "bin"), ("python", "lib")}
        runtime = [
            member for member in python.getmembers()
            if PurePosixPath(member.name).parts[:2] in runtime_paths
        ]
        python.extractall(work, members=runtime, filter="data")
    with zipfile.ZipFile(wheel) as coverage:
        coverage.extractall(work / "python" / "lib" / f"python{PYTHON_VERSION.rsplit('.', 1)[0]}" / "site-packages")
    (work / "coverage.ini").write_text(COVERAGE_CONFIG, encoding="utf-8")


def main(requested: str) -> int:
    machine = target(requested) if requested else native_target()
    scratch = ROOT / ".work" / "tmp"
    reports = ROOT / ".work" / "coverage"
    scratch.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / ".work" / "build" / machine.triple / "phases" / "prepare" / "toolchain" / "bin" / "clang"
    if not compiler.is_file() or not (ROOT / ".work" / "tools" / "jaq").is_file():
        raise ValueError(f"prepare the native controller toolchain and jaq for {machine.triple} before running coverage")
    image = image_tag(load_bootstrap(ROOT / "bootstrap.lock.json"), machine, ROOT / "docker" / "builder.Dockerfile")
    with tempfile.TemporaryDirectory(prefix="controller-coverage-", dir=scratch) as directory:
        work = Path(directory)
        prepare_tools(work, machine.alpine_arch, Cache(reports / "cache"))
        result = run_sealed(
            image,
            ["sh", "-euc", """
                python3 -m coverage --version
                python3 -m coverage run build.py controller-test
                python3 -m coverage combine
                python3 -m coverage json -o /coverage-run/controller.json
            """],
            target=machine,
            mounts=[
                (ROOT, "/src"), (work, "/coverage-run"),
                (work / "python", "/coverage-python"),
            ],
            read_only=frozenset({"/coverage-python"}),
            env={
                "PATH": "/coverage-python/bin:/src/.work/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "PYTHONPATH": "/src",
                "TMPDIR": "/src/.work/tmp",
                "COVERAGE_RCFILE": "/coverage-run/coverage.ini",
                "COVERAGE_FILE": "/coverage-run/.coverage",
            },
            timeout=600,
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode:
            return result.returncode
        report = reports / f"controller-{machine.triple}.json"
        os.replace(work / "controller.json", report)
        print(f"Coverage report: {report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1]))
    except (InputError, OSError, SandboxError, UnsupportedTargetError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error
