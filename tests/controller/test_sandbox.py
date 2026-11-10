from __future__ import annotations

import contextlib
import io
import json
import struct
import subprocess
import unittest
import runpy
import os
from pathlib import Path
from unittest.mock import patch

import build
from buildsys.inputs import Cache, Input, InputError, load_bootstrap
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


class ReferenceImageTests(unittest.TestCase):
    def test_sealed_container_protects_declared_read_only_inputs(self) -> None:
        created = subprocess.CompletedProcess([], 0, 'container-id\n', '')
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{'HostConfig': {'NetworkMode': 'none'}}]), '')
        started = subprocess.CompletedProcess([], 0, '', '')
        removed = subprocess.CompletedProcess([], 0, '', '')
        with workspace() as directory, patch.object(sandbox, '_docker', side_effect=[created, inspection, started, removed]) as docker:
            inputs = directory / 'inputs'
            output = directory / 'output'
            inputs.mkdir()
            output.mkdir()
            sandbox.run_sealed('image', ['test'], target=X86, mounts=[(inputs, '/inputs'), (output, '/output')],
                               read_only=frozenset({'/inputs'}))
            create = docker.call_args_list[0].args
            self.assertIn(f'{inputs}:/inputs:ro', create)
            self.assertIn(f'{output}:/output:rw', create)
        with patch.object(sandbox, '_docker') as docker:
            with self.assertRaises(sandbox.SandboxError):
                sandbox.run_sealed('image', ['test'], target=X86, mounts=[], read_only=frozenset({'/missing'}))
            docker.assert_not_called()

    def test_fetch_uses_locked_reference_index(self) -> None:
        lock = load_bootstrap(build.BOOTSTRAP_LOCK)
        with patch.object(sandbox, "_docker", return_value=subprocess.CompletedProcess([], 0, "", "")) as docker:
            sandbox.pull_reference(lock, X86.docker_platform)
        docker.assert_called_once_with("pull", "--platform", X86.docker_platform, lock.reference_image)

    def test_networked_container_rejects_wrong_mode_and_cleans_up(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{"HostConfig": {"NetworkMode": "none"}}]), "")
        removed = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(sandbox, "_docker", side_effect=[created, inspection, removed]) as docker:
            with self.assertRaisesRegex(sandbox.SandboxError, "not bridge"):
                sandbox.run_networked("image", ["test"], target=X86, mounts=[])
        self.assertEqual(docker.call_args_list[-1].args, ("rm", "--force", "container-id"))

    def test_container_cleanup_failure_is_reported(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{"HostConfig": {"NetworkMode": "bridge"}}]), "")
        started = subprocess.CompletedProcess([], 0, "ok", "")
        removed = subprocess.CompletedProcess([], 1, "", "remove failed")
        with patch.object(sandbox, "_docker", side_effect=[created, inspection, started, removed]):
            with self.assertRaisesRegex(sandbox.SandboxError, "remove failed"):
                sandbox.run_networked("image", ["test"], target=X86, mounts=[])

    def test_reference_runtime_copy_failure_removes_container(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        failed = subprocess.CompletedProcess([], 1, "", "copy failed")
        removed = subprocess.CompletedProcess([], 0, "", "")
        with workspace() as directory, patch.object(sandbox, "_docker", side_effect=[created, failed, removed]) as docker:
            with self.assertRaisesRegex(sandbox.SandboxError, "copy failed"):
                sandbox.copy_reference_runtime("image", X86, directory / "runtime")
        self.assertEqual(docker.call_args_list[-1].args, ("rm", "--force", "container-id"))


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
    def test_doctor_rejects_shadowed_or_wrong_version_clang(self) -> None:
        with workspace() as directory:
            tc = fake_toolchain(directory / "tc")
            shadow = directory / "shadow"
            shadow.mkdir()
            clang = shadow / "clang"
            clang.write_text("#!/bin/sh\nexit 0\n")
            clang.chmod(0o755)
            with patch.object(build, "_toolchain_directory", return_value=tc), patch.dict(os.environ, {"PATH": str(shadow)}), patch("sys.stdout"):
                self.assertEqual(build.main(["doctor", "--target", X86.triple]), 1)
            (tc / "bin/clang").write_text("#!/bin/sh\necho 'clang version 22.0.0'\n")
            with patch.object(build, "_toolchain_directory", return_value=tc), patch.dict(os.environ, {"PATH": str(tc / "bin")}), patch("sys.stdout"):
                self.assertEqual(build.main(["doctor", "--target", X86.triple]), 1)

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

    def test_lld_version_prefix_is_not_enough(self) -> None:
        with workspace() as directory:
            toolchain = fake_toolchain(directory / "tc", lld="LLD 23.1.50")
            with self.assertRaisesRegex(ToolchainError, "ld.lld version"):
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
    def test_fetch_attempt_during_prepare_fails(self) -> None:
        with workspace() as directory:
            caches = []

            def cache_factory(path, *, offline=False):
                cache = Cache(directory / "cache", offline=offline)
                caches.append(cache)
                return cache

            item = Input(name="source", version="1", url="https://example.invalid/source", sha256="a" * 64, role="source", target=X86.triple, size=4)

            def fetch_during_build(*args):
                caches[0].fetch(item)

            with patch.object(build, "BUILD_ROOT", directory / "build"), patch.object(build, "Cache", side_effect=cache_factory), patch.object(Cache, "require", return_value=directory / "input"), patch.object(build.toolchain, "install", return_value=directory / "tc"), patch.object(build.toolchain, "verify", return_value={}), patch.object(build.sysroot, "build", side_effect=fetch_during_build), contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit):
                    build._prepare_inside(X86)
            self.assertIn("offline phase cannot fetch", error.getvalue())

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
    def test_prepare_rejects_networked_container(self) -> None:
        with patch.object(sandbox, "in_container", return_value=True), patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                build.main(["prepare", "--target", X86.triple, "--in-container"])

    def test_host_control_connects_and_container_connections_are_denied(self) -> None:
        probe = sandbox._probe

        def run(command, cwd, timeout):
            if command[0] == "docker":
                return subprocess.CompletedProcess(command, 0, "DENIED:101\n", "")
            return probe(command, cwd, timeout)

        with workspace() as directory, patch.object(sandbox, "_host_gateway", return_value="172.17.0.1"), patch.object(sandbox, "docker_path", return_value="docker"), patch.object(sandbox, "_probe", side_effect=run):
            result = sandbox.network_boundary_selftest("image", X86, directory)
        self.assertTrue(result["ok"], result)


class ProvenanceTests(unittest.TestCase):
    def test_dynamic_trace_requires_sysroot_loader(self) -> None:
        fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / "fixtures/provenance/run.py"))
        with self.assertRaisesRegex(fixture["ProvenanceError"], "loader"):
            fixture["_check_dynamic_trace"]("/tc/lib/musl/Scrt1.o\n", Path("/tc"), Path("/sysroot"), Path("/work"), X86)

    def test_static_trace_requires_compiler_runtime(self) -> None:
        fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / "fixtures/provenance/run.py"))
        trace = "/tc/lib/libc++.a(a.o)\n/tc/lib/libunwind.a(a.o)\n/tc/lib/musl/libc.a(a.o)\n"
        with self.assertRaisesRegex(fixture["ProvenanceError"], "compiler-rt"):
            fixture["_check_static_trace"](trace, Path("/tc"), Path("/sysroot"), Path("/work"), X86)

    def test_interpreter_extracts_llvm_readelf_path(self) -> None:
        fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / "fixtures/provenance/run.py"))
        with workspace() as directory:
            binary = directory / "bin"
            binary.mkdir()
            readelf = binary / "llvm-readelf"
            readelf.write_text("#!/bin/sh\necho '      [Requesting program interpreter: /lib/ld-musl-x86_64.so.1]'\n")
            readelf.chmod(0o755)
            self.assertEqual(fixture["_interpreter"](directory, directory / "elf"), X86.musl_loader)


if __name__ == "__main__":
    unittest.main()
