from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from buildsys import rust, sandbox, tls
from buildsys.inputs import Cache, load_bootstrap, load_sources, safe_extract
from buildsys.targets import native_target


def inside() -> None:
    if not sandbox.in_container() or {name for _, name in sandbox.socket.if_nameindex()} != {"lo"}:
        raise RuntimeError("TLS tests require a sealed container with only loopback networking")
    target = native_target()
    work = ROOT / ".work"
    scratch = work / "tmp"
    prepared = work / "build" / target.triple / "phases/prepare"
    rust_root = work / "rust" / target.triple
    cache = Cache(work / "cache", offline=True)
    sources = {item.name: item for item in load_sources(ROOT / "sources.lock.json")}
    archive = rust.build_static(rust_root, prepared, target, scratch / "tls-kache", scratch)
    client = tls.build_client(cache, sources["cmake-source"], prepared, archive, target,
                              work / "build" / target.triple, scratch, ROOT / "tests/tls/client.c")
    with tempfile.TemporaryDirectory(prefix="tls-tests-", dir=scratch) as temporary:
        directory = Path(temporary)
        package = safe_extract(cache.require(sources[f"openssl-test-{target.machine}"]), directory / "openssl")
        env = {**os.environ, "TLS_CLIENT": str(client), "TLS_FIXTURE_DIR": str(directory / "certs"),
               "PATH": f"{package / 'usr/bin'}{os.pathsep}{os.environ.get('PATH', '')}"}
        print(rust._run([sys.executable, str(ROOT / "tests/tls/cases.py")], cwd=ROOT, env=env), end="")


def main() -> None:
    if sys.argv[1:] == ["--in-container"]:
        inside()
        return
    if sys.argv[1:]:
        raise RuntimeError("unexpected TLS test arguments")
    target = native_target()
    scratch = ROOT / ".work/tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TMPDIR": str(scratch)}
    for command in ("fetch", "prepare"):
        print(rust._run([sys.executable, str(ROOT / "build.py"), command, "--target", target.triple], cwd=ROOT, env=env), end="")
    kache = shutil.which("kache", path=f"{os.environ.get('PATH', '')}{os.pathsep}{Path.home() / '.cargo/bin'}")
    if not kache:
        raise RuntimeError("kache is required for Rust builds")
    shutil.copy2(kache, scratch / "tls-kache")
    lock = load_bootstrap(ROOT / "bootstrap.lock.json")
    tag = sandbox.image_tag(lock, target, ROOT / "docker/builder.Dockerfile")
    result = sandbox.run_sealed(tag, ["python3", "tests/tls/run.py", "--in-container"], target=target,
                                mounts=[(ROOT, "/src")], env={"TMPDIR": "/src/.work/tmp", "PYTHONPATH": "/src"}, timeout=3600)
    print(result.stdout, end="")
    if result.returncode:
        raise RuntimeError(f"sealed TLS tests failed ({result.returncode}):\n{result.stderr}")


if __name__ == "__main__":
    main()
