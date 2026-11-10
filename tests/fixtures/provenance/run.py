"""Six-point provenance fixture for the pinned toolchain and sysroot.

Run inside the sealed builder container. Every check either proves a property
of the produced bytes or fails loudly with the command output that broke it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from buildsys.sysroot import SysrootError, check_link_trace, check_machine, elf_machine, trace_paths
from buildsys.targets import target as describe_target

DYNAMIC_C = """
#include <stdio.h>
int main(void) {
    puts("hello");
    return 0;
}
"""

TREE_CPP = """
#include <cstdio>
#include <filesystem>
#include <stdexcept>

struct Guard {
    ~Guard() { std::puts("dtor"); }
};

volatile __int128 numerator = 42;
volatile __int128 denominator = 2;

int main() {
    Guard guard;
    if (numerator / denominator != 21) {
        return 3;
    }
    std::filesystem::path root("/");
    if (!root.is_absolute()) {
        return 2;
    }
    try {
        throw std::runtime_error("caught");
    } catch (const std::exception &error) {
        std::printf("%s\\n", error.what());
    }
    return 0;
}
"""

LTO_ONE = """
int twice(int value);
int main(void) { return twice(21) == 42 ? 0 : 1; }
"""

LTO_TWO = """
int twice(int value) { return value * 2; }
"""


class ProvenanceError(Exception):
    """A provenance check failed."""


def _run(
    command: list[str],
    *,
    work: Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    environment = {**os.environ, "TMPDIR": str(work), "TMP": str(work)}
    result = subprocess.run(
        command,
        cwd=work,
        env=environment,
        capture_output=capture,
        text=True,
        check=False,
        timeout=300,
    )
    if check and result.returncode != 0:
        raise ProvenanceError(
            f"{' '.join(command)} failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def _readelf(toolchain: Path, *arguments: str) -> str:
    return _run(
        [str(toolchain / "bin" / "llvm-readelf"), *arguments],
        work=Path.cwd(),
    ).stdout


def _dynamic(toolchain: Path, binary: Path) -> list[str]:
    output = _readelf(toolchain, "-d", str(binary))
    return [line for line in output.splitlines() if "NEEDED" in line or "RPATH" in line or "RUNPATH" in line]


def _needed(toolchain: Path, binary: Path) -> list[str]:
    needed = []
    for line in _dynamic(toolchain, binary):
        if "(NEEDED)" in line:
            needed.append(line.rsplit("[", 1)[1].rstrip("]"))
    return needed


def _interpreter(toolchain: Path, binary: Path) -> str | None:
    output = _readelf(toolchain, "-l", str(binary))
    for line in output.splitlines():
        if "[Requesting program interpreter: " in line:
            return line.split("[Requesting program interpreter: ", 1)[1].rstrip("]")
    return None


def _comment(toolchain: Path, binary: Path) -> list[str]:
    output = _readelf(toolchain, "-p", ".comment", str(binary))
    return [line.split("] ", 1)[1].strip() for line in output.splitlines() if "] " in line]


def _check_comment(toolchain: Path, binary: Path) -> list[str]:
    comments = _comment(toolchain, binary)
    if not comments:
        raise ProvenanceError(f"{binary}: no .comment provenance")
    if any(comment.startswith("GCC:") for comment in comments):
        raise ProvenanceError(f"{binary}: GCC compiled at {comments}")
    return comments


def _check_static_trace(trace: str, toolchain: Path, sysroot: Path, work: Path, target) -> None:
    check_link_trace(trace, toolchain, sysroot, work, target)
    root = toolchain.resolve()
    names = {Path(path).name for path in trace_paths(trace) if root in Path(path).resolve().parents}
    for required in ("libc++.a", "libunwind.a", "libc.a"):
        if required not in names:
            raise ProvenanceError(f"static link trace lacks {required}")
    if not any(name.startswith("libclang_rt.builtins-") and name.endswith(".a") for name in names):
        raise ProvenanceError("static link trace lacks compiler-rt builtins")


def _check_dynamic_trace(trace: str, toolchain: Path, sysroot: Path, work: Path, target) -> None:
    check_link_trace(trace, toolchain, sysroot, work, target)
    loader = (sysroot / target.musl_loader.lstrip("/")).resolve()
    if loader not in {Path(path).resolve() for path in trace_paths(trace)}:
        raise ProvenanceError("dynamic link trace lacks the sysroot loader")


def run(toolchain: Path, sysroot: Path, target_triple: str, work: Path, output: Path) -> dict:
    target = describe_target(target_triple)
    toolchain = Path(toolchain).resolve()
    sysroot = Path(sysroot).resolve()
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    clang = toolchain / "bin" / "clang"
    clangxx = toolchain / "bin" / "clang++"
    llvm_ar = toolchain / "bin" / "llvm-ar"
    flags = [
        f"--target={target.triple}",
        f"--sysroot={sysroot}",
        "-fuse-ld=lld",
        "--rtlib=compiler-rt",
        "--unwindlib=libunwind",
    ]
    cxx_flags = [*flags, "-stdlib=libc++"]
    sources = {
        "hello.c": DYNAMIC_C,
        "tree.cpp": TREE_CPP,
        "one.c": LTO_ONE,
        "two.c": LTO_TWO,
    }
    for name, content in sources.items():
        (work / name).write_text(content)
    checks: list[str] = []

    hello = work / "hello"
    _run([str(clang), *flags, "hello.c", "-o", str(hello)], work=work)
    check_machine(hello, target)
    result = _run([str(hello)], work=work)
    if result.stdout.strip() != "hello":
        raise ProvenanceError(f"dynamic C binary printed {result.stdout!r}")
    needed = _needed(toolchain, hello)
    expected = f"libc.musl-{target.machine}.so.1"
    if needed != [expected]:
        raise ProvenanceError(f"dynamic C NEEDED {needed} != [{expected}]")
    interpreter = _interpreter(toolchain, hello)
    if interpreter != target.musl_loader:
        raise ProvenanceError(f"dynamic C interpreter {interpreter!r} != {target.musl_loader!r}")
    checks.append("C compile, dynamic musl link, run")

    hello_static = work / "hello-static"
    _run([str(clang), *flags, "-static-pie", "hello.c", "-o", str(hello_static)], work=work)
    check_machine(hello_static, target)
    _run([str(hello_static)], work=work)
    if _interpreter(toolchain, hello_static) is not None:
        raise ProvenanceError("static PIE has an interpreter")
    if _needed(toolchain, hello_static):
        raise ProvenanceError(f"static PIE NEEDED {_needed(toolchain, hello_static)}")
    checks.append("C compile, static PIE link, run")

    tree_static = work / "tree-static"
    _run(
        [str(clangxx), *cxx_flags, "-static-pie", "tree.cpp", "-o", str(tree_static)],
        work=work,
    )
    check_machine(tree_static, target)
    result = _run([str(tree_static)], work=work)
    if "dtor" not in result.stdout or "caught" not in result.stdout:
        raise ProvenanceError(f"C++ output missing destructor or catch: {result.stdout!r}")
    if _interpreter(toolchain, tree_static) is not None or _needed(toolchain, tree_static):
        raise ProvenanceError("static C++ binary has a dynamic dependency")
    _check_comment(toolchain, tree_static)
    checks.append("C++ exceptions, destructors, std::filesystem static PIE")

    tree_dynamic = work / "tree-dynamic"
    _run([str(clangxx), *cxx_flags, "tree.cpp", "-o", str(tree_dynamic)], work=work)
    check_machine(tree_dynamic, target)
    _run([str(tree_dynamic)], work=work)
    if _needed(toolchain, tree_dynamic) != [expected]:
        raise ProvenanceError(f"C++ dynamic NEEDED {_needed(toolchain, tree_dynamic)}")
    if _interpreter(toolchain, tree_dynamic) != target.musl_loader:
        raise ProvenanceError("dynamic C++ binary has the wrong interpreter")
    checks.append("C++ exceptions, destructors, std::filesystem dynamic musl link")

    static_trace = _run(
        [
            str(clangxx),
            *cxx_flags,
            "-static-pie",
            "-Wl,--trace",
            "tree.cpp",
            "-o",
            str(work / "tree-traced"),
        ],
        work=work,
    ).stdout
    _check_static_trace(static_trace, toolchain, sysroot, work, target)
    checks.append("link inputs resolve from the toolchain, sysroot loader only")

    dynamic_trace = _run(
        [str(clang), *flags, "-Wl,--trace", "hello.c", "-o", str(work / "hello-traced")],
        work=work,
    ).stdout
    _check_dynamic_trace(dynamic_trace, toolchain, sysroot, work, target)
    checks.append("dynamic link trace resolves the loader through the sysroot")

    _run([str(clang), *flags, "-flto=thin", "-c", "one.c", "-o", "one.o"], work=work)
    _run([str(clang), *flags, "-flto=thin", "-c", "two.c", "-o", "two.o"], work=work)
    _run([str(llvm_ar), "rcs", "libtwo.a", "two.o"], work=work)
    lto = work / "lto"
    _run(
        [
            str(clang),
            *flags,
            "-flto=thin",
            "one.o",
            "libtwo.a",
            "-o",
            str(lto),
        ],
        work=work,
    )
    check_machine(lto, target)
    _run([str(lto)], work=work)
    if _interpreter(toolchain, lto) != target.musl_loader or _needed(toolchain, lto) != [expected]:
        raise ProvenanceError("ThinLTO binary has an unexpected dynamic closure")
    _check_comment(toolchain, lto)
    checks.append("ThinLTO compile, llvm-ar archive, link, run")

    wrong_machine = work / "wrong-machine.o"
    other_machine = "aarch64" if target.machine == "x86_64" else "x86_64"
    _run([str(clang), f"--target={other_machine}-linux-musl", "-c", "one.c", "-o", str(wrong_machine)], work=work)
    try:
        check_machine(wrong_machine, target)
    except SysrootError:
        pass
    else:
        raise ProvenanceError("wrong-machine object passed the machine check")

    contaminated_sysroot = work / "contaminated-sysroot"
    contaminated_sysroot.mkdir(exist_ok=True)
    crt = contaminated_sysroot / "crt1.o"
    _run([str(clang), *flags, "-c", "one.c", "-o", str(crt)], work=work)
    contaminated_trace = _run(
        [str(toolchain / "bin/ld.lld"), "-r", "--trace", str(crt), "-o", str(work / "contaminated.o")],
        work=work,
    ).stdout
    try:
        check_link_trace(contaminated_trace, toolchain, contaminated_sysroot, work, target)
    except SysrootError:
        pass
    else:
        raise ProvenanceError("sysroot object passed the link provenance check")
    checks.append("wrong-machine object and sysroot link input rejected")

    for binary in (hello, hello_static, tree_static, tree_dynamic, lto):
        _check_comment(toolchain, binary)
        if (work / binary.name).is_file():
            machine = elf_machine(binary)
            if machine != target.elf_machine:
                raise ProvenanceError(f"{binary}: e_machine {machine}")
    checks.append("ELF machine, closure, and .comment on every artifact")

    report = {
        "target": target.triple,
        "toolchain": str(toolchain),
        "sysroot": str(sysroot),
        "checks": checks,
        "artifacts": {
            binary.name: {"e_machine": elf_machine(binary), "comment": _comment(toolchain, binary)}
            for binary in (hello, hello_static, tree_static, tree_dynamic, lto)
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--sysroot", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = run(
            Path(args.toolchain),
            Path(args.sysroot),
            args.target,
            Path(args.work),
            Path(args.output),
        )
    except (ProvenanceError, OSError, subprocess.SubprocessError) as error:
        print(f"provenance: {error}", file=sys.stderr)
        return 1
    print(f"provenance: {len(report['checks'])} checks passed for {report['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
