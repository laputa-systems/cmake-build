from __future__ import annotations

import struct
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from buildsys.inputs import Cache, Input, InputError
from buildsys import sandbox
from buildsys.sysroot import SysrootError, check_link_trace, check_machine, elf_machine
from buildsys.targets import target
from buildsys.toolchain import (
    CLANG_VERSION,
    LLD_VERSION,
    TOOLS,
    ToolchainError,
    verify,
)
from helpers import workspace

X86 = target("x86_64-unknown-linux-musl")
ARM = target("aarch64-unknown-linux-musl")


def fake_toolchain(directory: Path, *, clang_version: str = CLANG_VERSION, lld: str = LLD_VERSION) -> Path:
    binary = directory / "bin"
    binary.mkdir(parents=True)
    for name in TOOLS:
        path = binary / name
        if name in ("clang", "clang++"):
            body = f"#!/bin/sh\necho '{clang_version}'\n"
        elif name == "ld.lld":
            body = f"#!/bin/sh\necho '{lld} (compatible with GNU linkers)'\n"
        else:
            body = "#!/bin/sh\necho 'LLVM version 23.1.5'\n"
        path.write_text(body)
        path.chmod(0o755)
    return directory


def elf_header(machine: int, *, order: int = 1) -> bytes:
    return b"\x7fELF" + bytes([2, order, 1]) + bytes(9) + bytes(2) + struct.pack("<H", machine)


class ToolchainTests(unittest.TestCase):
    def test_accepts_pinned_identity(self) -> None:
        with workspace() as directory:
            toolchain = fake_toolchain(directory / "tc")
            report = verify(toolchain, X86, environ={"PATH": str(directory / "empty")})
            self.assertEqual(report["clang"], CLANG_VERSION)

    def test_wrong_version_string_fails(self) -> None:
        with workspace() as directory:
            toolchain = fake_toolchain(directory / "tc", clang_version="clang version 22.0.0")
            with self.assertRaisesRegex(ToolchainError, "!= 'clang version 23.1.5'"):
                verify(toolchain, X86, environ={"PATH": str(directory / "empty")})

    def test_fake_clang_earlier_on_path_fails(self) -> None:
        with workspace() as directory:
            toolchain = fake_toolchain(directory / "tc")
            elsewhere = directory / "elsewhere"
            elsewhere.mkdir()
            fake = elsewhere / "clang"
            fake.write_text("#!/bin/sh\necho 'clang version 23.1.5'\n")
            fake.chmod(0o755)
            with self.assertRaisesRegex(ToolchainError, "resolves outside the pinned toolchain"):
                verify(toolchain, X86, environ={"PATH": str(elsewhere)})


class MachineTests(unittest.TestCase):
    def test_wrong_machine_fails(self) -> None:
        with workspace() as directory:
            artifact = directory / "arm.bin"
            artifact.write_bytes(elf_header(ARM.elf_machine))
            self.assertEqual(elf_machine(artifact), ARM.elf_machine)
            with self.assertRaisesRegex(SysrootError, "e_machine 183 != 62"):
                check_machine(artifact, X86)

    def test_not_an_elf_fails(self) -> None:
        with workspace() as directory:
            artifact = directory / "text"
            artifact.write_bytes(b"not an elf")
            with self.assertRaisesRegex(SysrootError, "not an ELF"):
                elf_machine(artifact)


class LinkTraceTests(unittest.TestCase):
    def test_sysroot_object_fails(self) -> None:
        with workspace() as directory:
            toolchain = directory / "tc"
            sysroot = directory / "sysroot"
            work = directory / "work"
            for path in (toolchain, sysroot, work):
                path.mkdir()
            trace = f"{sysroot}/usr/lib/crt1.o\n{toolchain}/lib/musl/crti.o\n"
            with self.assertRaisesRegex(SysrootError, "resolved from the sysroot"):
                check_link_trace(trace, toolchain, sysroot, work, X86)

    def test_sysroot_loader_is_allowed(self) -> None:
        with workspace() as directory:
            toolchain = directory / "tc"
            sysroot = directory / "sysroot"
            work = directory / "work"
            for path in (toolchain, sysroot, work):
                path.mkdir()
            loader = sysroot / X86.musl_loader.lstrip("/")
            loader.parent.mkdir(parents=True)
            loader.write_bytes(b"")
            trace = f"{loader}\n{toolchain}/lib/musl/crti.o\n{work}/tmp.o\n"
            check_link_trace(trace, toolchain, sysroot, work, X86)

    def test_outside_input_fails(self) -> None:
        with workspace() as directory:
            toolchain = directory / "tc"
            sysroot = directory / "sysroot"
            work = directory / "work"
            for path in (toolchain, sysroot, work):
                path.mkdir()
            with self.assertRaisesRegex(SysrootError, "outside the pinned toolchain"):
                check_link_trace("/usr/lib/crt1.o\n", toolchain, sysroot, work, X86)


class OfflineTests(unittest.TestCase):
    def test_offline_cache_refuses_fetch(self) -> None:
        with workspace() as directory:
            item = Input(
                name="source",
                version="1.0",
                url="https://example.invalid/source",
                sha256="a" * 64,
                role="source",
                target="x86_64-unknown-linux-musl",
                size=4,
            )
            cache = Cache(directory / "cache", offline=True)
            with self.assertRaisesRegex(InputError, "offline phase cannot fetch"):
                cache.fetch(item)


class NetworkBoundaryTests(unittest.TestCase):
    def test_host_control_connects_and_container_connections_are_denied(self) -> None:
        probe = sandbox._probe

        def run(command, cwd, timeout):
            if command[0] == "docker":
                return subprocess.CompletedProcess(command, 0, "DENIED:101\n", "")
            return probe(command, cwd, timeout)

        with workspace() as directory, patch.object(sandbox, "_host_gateway", return_value="172.17.0.1"), patch.object(sandbox, "docker_path", return_value="docker"), patch.object(sandbox, "_probe", side_effect=run):
            result = sandbox.network_boundary_selftest("image", X86, directory)
        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
