from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import runpy
import struct
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import call, patch

from helpers import workspace

import build
from buildsys import sandbox
from buildsys.inputs import Cache, Input, InputError, load_bootstrap
from buildsys.sysroot import SysrootError, check_link_trace, check_machine, elf_machine
from buildsys.targets import target
from buildsys.toolchain import (
    CLANG_VERSION,
    LLD_VERSION,
    TOOLS,
    ToolchainError,
    verify,
)

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
            result = sandbox.run_sealed('image', ['test'], target=X86, mounts=[(inputs, '/inputs'), (output, '/output')],
                                        read_only=frozenset({'/inputs'}))
            self.assertEqual(result.networks, {})
            create = docker.call_args_list[0].args
            self.assertIn(f'{inputs}:/inputs:ro', create)
            self.assertIn(f'{output}:/output:rw', create)
            self.assertEqual(create[create.index('--workdir') + 1], '/src')
            self.assertEqual(docker.call_args_list[2], call('start', '--attach', 'container-id', timeout=3600))
        with patch.object(sandbox, '_docker') as docker:
            with self.assertRaisesRegex(sandbox.SandboxError, '^read-only destinations must be declared mounts$'):
                sandbox.run_sealed('image', ['test'], target=X86, mounts=[], read_only=frozenset({'/missing'}))
            docker.assert_not_called()

    def test_sealed_execution_forwards_exit_output_and_timeout(self) -> None:
        created = subprocess.CompletedProcess([], 0, 'candidate-container\n', '')
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{
            'HostConfig': {'NetworkMode': 'none'}, 'NetworkSettings': {'Networks': {}},
        }]), '')
        started = subprocess.CompletedProcess([], 7, 'child output\n', 'child error\n')
        removed = subprocess.CompletedProcess([], 0, '', '')
        with (
            workspace() as directory,
            patch.object(sandbox, '_docker', side_effect=[created, inspection, started, removed]) as docker,
            patch.object(sandbox.os, 'getuid', return_value=1080),
            patch.object(sandbox.os, 'getgid', return_value=2104),
        ):
            source = directory / 'source with spaces'
            target_dir = directory / 'output'
            result = sandbox.run_sealed(
                'locked-image', ['python3', 'build.py', 'test'], target=ARM,
                mounts=[(source, '/source'), (target_dir, '/output')],
                read_only=frozenset({'/source'}), env={'TMPDIR': '/output/tmp', 'MODE': 'fixture'},
                workdir='/output', timeout=23,
            )
            self.assertEqual(result, sandbox.SealedResult(7, 'child output\n', 'child error\n', 'none', {}))
            self.assertEqual(docker.call_args_list, [
                call('create', '--network', 'none', '--platform', ARM.docker_platform,
                     '--user', '1080:2104', '--workdir', '/output', '--volume', f'{source}:/source:ro',
                     '--volume', f'{target_dir}:/output:rw', '--env', 'TMPDIR=/output/tmp',
                     '--env', 'MODE=fixture', 'locked-image', 'python3', 'build.py', 'test'),
                call('inspect', 'candidate-container'),
                call('start', '--attach', 'candidate-container', timeout=23),
                call('rm', '--force', 'candidate-container'),
            ])

    def test_networked_execution_forwards_supported_options_and_network_evidence(self) -> None:
        created = subprocess.CompletedProcess([], 0, 'candidate-container\n', '')
        networks: dict[str, object] = {'bridge': {'Driver': 'bridge'}}
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{
            'HostConfig': {'NetworkMode': 'bridge'}, 'NetworkSettings': {'Networks': networks},
        }]), '')
        started = subprocess.CompletedProcess([], 0, 'child output\n', '')
        removed = subprocess.CompletedProcess([], 0, '', '')
        with workspace() as directory:
            source = directory / 'input'
            for custom in (False, True):
                with (
                    self.subTest(custom=custom),
                    patch.object(sandbox, '_docker', side_effect=[created, inspection, started, removed]) as docker,
                ):
                    mounts = [(source, '/input')]
                    if custom:
                        result = sandbox.run_networked(
                            'locked-image', ['test'], target=ARM, mounts=mounts,
                            workdir='/input', timeout=17, env={'MODE': 'fixture'},
                            read_only=frozenset({'/input'}),
                        )
                    else:
                        result = sandbox.run_networked('locked-image', ['test'], target=ARM, mounts=mounts)
                    self.assertEqual(result, sandbox.SealedResult(0, 'child output\n', '', 'bridge', networks))
                    create = docker.call_args_list[0].args
                    self.assertEqual(create[create.index('--workdir') + 1], '/input' if custom else '/src')
                    self.assertIn(f'{source}:/input:{"ro" if custom else "rw"}', create)
                    self.assertEqual(create[-2:], ('locked-image', 'test'))
                    if custom:
                        self.assertIn('MODE=fixture', create)
                    self.assertEqual(
                        docker.call_args_list[2], call('start', '--attach', 'candidate-container', timeout=17 if custom else 3600),
                    )

    def test_missing_inspection_network_mode_keeps_the_child_from_starting(self) -> None:
        created = subprocess.CompletedProcess([], 0, 'candidate-container\n', '')
        inspection = subprocess.CompletedProcess([], 0, '[{}]', '')
        removed = subprocess.CompletedProcess([], 0, '', '')
        with (
            patch.object(sandbox, '_docker', side_effect=[created, inspection, removed]) as docker,
            self.assertRaisesRegex(sandbox.SandboxError, '^container network mode is not none$'),
        ):
            sandbox.run_sealed('image', ['build'], target=X86, mounts=[])
        self.assertEqual(docker.call_args_list[1:], [
            call('inspect', 'candidate-container'), call('rm', '--force', 'candidate-container'),
        ])

    def test_cleanup_failure_preserves_the_original_inspection_failure(self) -> None:
        created = subprocess.CompletedProcess([], 0, 'candidate-container\n', '')
        inspection = subprocess.CompletedProcess([], 7, '', 'cannot inspect\n')
        removed = subprocess.CompletedProcess([], 6, '', 'cannot remove\n')
        with (
            patch.object(sandbox, '_docker', side_effect=[created, inspection, removed]) as docker,
            contextlib.redirect_stderr(io.StringIO()) as stderr,
            self.assertRaisesRegex(sandbox.SandboxError, r'^inspect container failed \(7\): cannot inspect$'),
        ):
            sandbox.run_sealed('image', ['build'], target=X86, mounts=[])
        self.assertEqual(docker.call_args_list[1:], [
            call('inspect', 'candidate-container'),
            call('rm', '--force', 'candidate-container'),
        ])
        self.assertEqual(stderr.getvalue(), 'container cleanup failed: remove container failed (6): cannot remove\n')

    def test_create_failure_stops_before_inspection_and_cleanup(self) -> None:
        failed = subprocess.CompletedProcess([], 12, '', 'cannot create\n')
        with (
            patch.object(sandbox, '_docker', return_value=failed) as docker,
            self.assertRaisesRegex(sandbox.SandboxError, r'^create none container failed \(12\): cannot create$'),
        ):
            sandbox.run_sealed('image', ['build'], target=X86, mounts=[])
        self.assertEqual(docker.call_count, 1)

    def test_fetch_uses_locked_reference_index(self) -> None:
        lock = load_bootstrap(build.BOOTSTRAP_LOCK)
        with patch.object(sandbox, "_docker", return_value=subprocess.CompletedProcess([], 0, "", "")) as docker:
            sandbox.pull_reference(lock, X86.docker_platform)
        docker.assert_called_once_with("pull", "--platform", X86.docker_platform, lock.reference_image)

    def test_networked_container_rejects_wrong_mode_and_cleans_up(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{"HostConfig": {"NetworkMode": "none"}}]), "")
        removed = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(sandbox, "_docker", side_effect=[created, inspection, removed]) as docker, self.assertRaisesRegex(sandbox.SandboxError, "not bridge"):
            sandbox.run_networked("image", ["test"], target=X86, mounts=[])
        self.assertEqual(docker.call_args_list[-1].args, ("rm", "--force", "container-id"))

    def test_container_cleanup_failure_is_reported(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        inspection = subprocess.CompletedProcess([], 0, json.dumps([{"HostConfig": {"NetworkMode": "bridge"}}]), "")
        started = subprocess.CompletedProcess([], 0, "ok", "")
        removed = subprocess.CompletedProcess([], 1, "", "remove failed")
        with patch.object(sandbox, "_docker", side_effect=[created, inspection, started, removed]), self.assertRaisesRegex(sandbox.SandboxError, "remove failed"):
            sandbox.run_networked("image", ["test"], target=X86, mounts=[])

    def test_reference_runtime_copy_failure_removes_container(self) -> None:
        created = subprocess.CompletedProcess([], 0, "container-id\n", "")
        failed = subprocess.CompletedProcess([], 1, "", "copy failed")
        removed = subprocess.CompletedProcess([], 0, "", "")
        with workspace() as directory, patch.object(sandbox, "_docker", side_effect=[created, failed, removed]) as docker, self.assertRaisesRegex(sandbox.SandboxError, "copy failed"):
            sandbox.copy_reference_runtime("image", X86, directory / "runtime")
        self.assertEqual(docker.call_args_list[-1].args, ("rm", "--force", "container-id"))


class BuilderImageContextTests(unittest.TestCase):
    def test_stable_builder_context_stages_only_native_verified_apks(self) -> None:
        lock = load_bootstrap(build.BOOTSTRAP_LOCK)
        self.assertEqual(
            build.DOCKERFILE.read_text().splitlines()[0],
            f'FROM {sandbox.image_reference(lock)}',
        )
        for machine in (X86, ARM):
            with self.subTest(target=machine.triple), workspace() as directory:
                inputs = []
                payloads = {}
                cache = Cache(directory / 'cache', offline=True)
                seed = directory / 'seed'
                for item in lock.targets[machine.triple]:
                    if item.target != machine.triple:
                        inputs.append(item)
                        continue
                    name = Path(item.url).name
                    body = name.encode('utf-8')
                    seed.write_bytes(body)
                    fixture = replace(item, sha256=hashlib.sha256(body).hexdigest(), size=len(body))
                    cache.store(seed, fixture)
                    inputs.append(fixture)
                    payloads[name] = body
                prepared = replace(lock, targets={**lock.targets, machine.triple: tuple(inputs)})
                fingerprint = sandbox.image_fingerprint(prepared, machine, build.DOCKERFILE)
                expected_tag = f'cmake-build-builder:{fingerprint[:16]}'
                context_root = directory / 'contexts'
                context = context_root / fingerprint
                if machine == X86:
                    context.mkdir(parents=True)
                    (context / 'stale').write_text('previous build')
                missing = subprocess.CompletedProcess([], 1, '', 'no image')
                complete = subprocess.CompletedProcess([], 0, '', '')
                with patch.object(sandbox, '_docker', side_effect=[missing, complete, complete]) as docker:
                    self.assertEqual(sandbox.build_image(prepared, machine, build.DOCKERFILE, cache, context_root), expected_tag)
                    self.assertEqual(sandbox.build_image(prepared, machine, build.DOCKERFILE, cache, context_root), expected_tag)
                self.assertEqual(docker.call_args_list, [
                    call('image', 'inspect', expected_tag),
                    call('build', '--network', 'none', '--platform', machine.docker_platform,
                         '--tag', expected_tag, '--file', str(context / 'Dockerfile'), str(context), timeout=1800),
                    call('image', 'inspect', expected_tag),
                ])
                self.assertEqual((context / 'Dockerfile').read_bytes(), build.DOCKERFILE.read_bytes())
                self.assertEqual({apk.name: apk.read_bytes() for apk in (context / 'apks').iterdir()}, payloads)
                self.assertEqual({entry.name for entry in context.iterdir()}, {'Dockerfile', 'apks'})
                failed = subprocess.CompletedProcess([], 7, '', 'fixture build failed')
                with (
                    patch.object(sandbox, '_docker', side_effect=[missing, failed]),
                    self.assertRaisesRegex(sandbox.SandboxError, f'^build {expected_tag} failed \\(7\\): fixture build failed$'),
                ):
                    sandbox.build_image(prepared, machine, build.DOCKERFILE, cache, context_root)

    def test_image_fingerprint_depends_on_base_and_apks_but_excludes_rust_components(self) -> None:
        lock = load_bootstrap(build.BOOTSTRAP_LOCK)
        with workspace() as directory:
            dockerfile = directory / 'Dockerfile'
            dockerfile.write_bytes(build.DOCKERFILE.read_bytes())
            fingerprint = sandbox.image_fingerprint(lock, X86, dockerfile)
            inputs = lock.targets[X86.triple]
            material = {
                'base': lock.image_index_digest,
                'platform': X86.docker_platform,
                'dockerfile': hashlib.sha256(dockerfile.read_bytes()).hexdigest(),
                'packages': sorted((item.name, item.version, item.sha256) for item in inputs if item.target == X86.triple),
            }
            canonical = json.dumps(material, sort_keys=True, separators=(',', ':')).encode()
            self.assertEqual(fingerprint, hashlib.sha256(canonical).hexdigest())
            self.assertNotEqual(sandbox.image_fingerprint(lock, ARM, dockerfile), fingerprint)
            changed_base = replace(lock, image_index_digest=f'sha256:{"a" * 64}')
            self.assertNotEqual(sandbox.image_fingerprint(changed_base, X86, dockerfile), fingerprint)
            entries = lock.targets[X86.triple]
            for role, should_change in ((X86.triple, True), ('all', False)):
                changed = tuple(replace(entry, sha256='f' * 64) if entry.target == role else entry for entry in entries)
                variant = replace(lock, targets={**lock.targets, X86.triple: changed})
                self.assertEqual(
                    sandbox.image_fingerprint(variant, X86, dockerfile) != fingerprint,
                    should_change,
                )
            reversed_items = replace(lock, targets={**lock.targets, X86.triple: tuple(reversed(entries))})
            self.assertEqual(sandbox.image_fingerprint(reversed_items, X86, dockerfile), fingerprint)
            original = dockerfile.read_bytes()
            modified = original.replace(b'WORKDIR /src', b'WORKDIR /tmp')
            self.assertEqual(len(original), len(modified))
            self.assertNotEqual(original, modified)
            dockerfile.write_bytes(modified)
            self.assertNotEqual(sandbox.image_fingerprint(lock, X86, dockerfile), fingerprint)


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

            item = Input(name="source", version="1", urls=("https://example.invalid/source",), sha256="a" * 64, role="source", target=X86.triple, size=4)

            def fetch_during_build(*args):
                caches[0].fetch(item)

            with patch.object(build, "BUILD_ROOT", directory / "build"), patch.object(build, "Cache", side_effect=cache_factory), patch.object(Cache, "require", return_value=directory / "input"), patch.object(build.toolchain, "install", return_value=directory / "tc"), patch.object(build.toolchain, "verify", return_value={}), patch.object(build.sysroot, "build", side_effect=fetch_during_build), contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
                build._prepare_inside(X86)
            self.assertIn("offline phase cannot fetch", error.getvalue())

    def test_offline_cache_refuses_fetch(self) -> None:
        with workspace() as directory:
            item = Input(
                name="source",
                version="1.0",
                urls=("https://example.invalid/source",),
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
        with patch.object(sandbox, "in_container", return_value=True), patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build.main(["prepare", "--target", X86.triple, "--in-container"])

    def test_host_control_connects_and_container_connections_are_denied(self) -> None:
        probe = sandbox._probe

        def run(command, cwd, timeout):
            if command[0] == "docker":
                return subprocess.CompletedProcess(command, 0, "DENIED:101\n", "")
            return probe(command, cwd, timeout)

        with (
            workspace() as directory,
            patch.object(sandbox, "_host_gateway", return_value="172.17.0.1"),
            patch.object(sandbox, "docker_path", return_value="docker"),
            patch.object(sandbox, "_probe", side_effect=run) as invoke,
        ):
            workdir = directory / "fresh" / "network"
            result = sandbox.network_boundary_selftest("image", X86, workdir)
            port = invoke.call_args_list[0].args[0][-1]
            self.assertGreater(int(port), 1024)
            base = ["docker", "run", "--rm", "--network", "none", "--platform", X86.docker_platform,
                    "image", "python3", "-c", sandbox.PROBE]
            self.assertEqual(invoke.call_args_list, [
                call([sys.executable, "-c", sandbox.PROBE, "127.0.0.1", port], workdir, 15),
                call([*base, "172.17.0.1", port], workdir, 60),
                call([*base, "127.0.0.1", port], workdir, 60),
            ])
        self.assertEqual(result, {
            "probe": "TCP connect to a listener held by the controller",
            "listener": f"0.0.0.0:{port}",
            "host_gateway": "172.17.0.1",
            "host_returncode": 3,
            "host_output": "CONNECTED",
            "gateway_returncode": 0,
            "gateway_output": "DENIED:101",
            "loopback_returncode": 0,
            "loopback_output": "DENIED:101",
            "listener_received": ["cmake-build-network-probe"],
            "errors": [],
            "worker_stopped": True,
            "ok": True,
            "error": None,
        })

    def test_gateway_lookup_failure_closes_the_listener(self) -> None:
        failure = subprocess.TimeoutExpired(['docker', 'network', 'inspect'], 5)
        with sandbox.socket.socket() as listener, workspace() as directory:
            with (
                patch.object(sandbox.socket, 'socket', return_value=listener),
                patch.object(sandbox, '_host_gateway', side_effect=failure),
                patch.object(sandbox, '_probe') as probe,
                self.assertRaises(subprocess.TimeoutExpired) as captured,
            ):
                sandbox.network_boundary_selftest('image', X86, directory)
            self.assertIs(captured.exception, failure)
            self.assertEqual(listener.fileno(), -1)
            probe.assert_not_called()

    def test_worker_start_failure_closes_the_listener(self) -> None:
        with sandbox.socket.socket() as listener, workspace() as directory:
            with (
                patch.object(sandbox.socket, 'socket', return_value=listener),
                patch.object(sandbox, '_host_gateway', return_value='172.17.0.1'),
                patch.object(sandbox.threading.Thread, 'start', side_effect=RuntimeError('worker start failed')),
                patch.object(sandbox, '_probe') as probe,
                self.assertRaisesRegex(RuntimeError, '^worker start failed$'),
            ):
                sandbox.network_boundary_selftest('image', X86, directory)
            self.assertEqual(listener.fileno(), -1)
            probe.assert_not_called()

    def test_failed_host_probe_closes_listener_and_records_failure(self) -> None:
        with (
            workspace() as directory,
            patch.object(sandbox, "_host_gateway", return_value="172.17.0.1"),
            patch.object(sandbox, "_probe", side_effect=OSError("fixture probe error")) as invoke,
        ):
            report = sandbox.network_boundary_selftest("image", X86, directory)
        self.assertEqual(invoke.call_count, 1)
        for name in ("host", "gateway", "loopback"):
            self.assertIsNone(report[f"{name}_returncode"])
            self.assertIsNone(report[f"{name}_output"])
        self.assertEqual(report["listener_received"], [])
        self.assertEqual(report["worker_stopped"], True)
        self.assertEqual(report["ok"], False)
        self.assertEqual(report["error"], "fixture probe error")


    def test_reports_failure_when_the_listener_worker_has_not_stopped(self) -> None:
        probe = sandbox._probe

        class LingeringThread(sandbox.threading.Thread):
            def is_alive(self) -> bool:
                return True

        def run(command, cwd, timeout):
            if command[0] == "docker":
                return subprocess.CompletedProcess(command, 0, "DENIED:101\n", "")
            return probe(command, cwd, timeout)

        with (
            workspace() as directory,
            patch.object(sandbox, "_host_gateway", return_value="172.17.0.1"),
            patch.object(sandbox, "docker_path", return_value="docker"),
            patch.object(sandbox, "_probe", side_effect=run),
            patch.object(sandbox.threading, "Thread", LingeringThread),
        ):
            report = sandbox.network_boundary_selftest("image", X86, directory)
        self.assertEqual(report["host_returncode"], 3)
        self.assertEqual(report["listener_received"], ["cmake-build-network-probe"])
        self.assertEqual(report["worker_stopped"], False)
        self.assertEqual(report["ok"], False)


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
