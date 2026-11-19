from __future__ import annotations

import contextlib
import io
import json
import os
import signal
import subprocess
import tomllib
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from helpers import ROOT, archive, file_sha256, workspace

from buildsys import rust, sandbox
from buildsys.inputs import Cache, bootstrap_inputs, load_bootstrap, load_sources
from buildsys.phases import PhaseCache
from buildsys.targets import target


class RustVendorTests(unittest.TestCase):
    def test_install_and_vendor_use_locked_inputs_and_reuse_verified_outputs(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        components = bootstrap_inputs(load_bootstrap(ROOT / "bootstrap.lock.json"), description.triple)
        locked = {item.name: item for item in components}
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        names = ("rustc", "cargo", "rust-std", "rust-src")
        with workspace() as directory:
            root = directory / "rust"
            scratch = directory / "scratch root" / "temporary"
            tools = root / "phases/tools"
            vendored = root / "phases/vendor"
            project = vendored / "source/rustls-release"
            provider_patch = directory / "provider.patch"
            provider_patch.write_bytes(b"original provider patch")
            blobs = {
                name: archive(directory / f"{name}.tar.gz", [(f"{name}-release/install.sh", name.encode(), None)])
                for name in names
            }
            blobs[source.name] = archive(directory / "source.tar.gz", [
                ("rustls-release/Cargo.toml", b"[package]\nname = 'rustls-ffi'\n", None),
            ])
            cache = Cache(directory / "cache", offline=True)
            inherited = {"PATH": "/host/bin", "RUSTFLAGS": "host rust flags", "FIXTURE": "retained"}
            installation_roots = []
            output = io.StringIO()

            def run(command, *, cwd, env):
                if Path(command[0]).name == "install.sh":
                    installation_roots.append(cwd.parent.parent)
                    (tools / f"{cwd.parent.name}.installed").write_bytes((cwd / "install.sh").read_bytes())
                elif command[0] == "patch":
                    (project / "provider.patch").write_bytes(provider_patch.read_bytes())
                else:
                    packages = vendored / "vendor"
                    packages.mkdir()
                    (packages / "package").write_bytes(b"vendor fixture")
                return ""

            with contextlib.redirect_stdout(output), patch.dict(os.environ, inherited, clear=True), \
                    patch.object(cache, "require", side_effect=lambda item: blobs[item.name]) as require, \
                    patch.object(rust, "_run", side_effect=run) as execute:
                self.assertEqual(rust.vendor(cache, components, source, provider_patch, root, scratch), vendored)
                temporary = installation_roots[0]
                self.assertEqual(installation_roots, [temporary] * 4)
                self.assertEqual(temporary.parent, scratch)
                self.assertTrue(temporary.name.startswith("rust-install-"))
                self.assertFalse(temporary.exists())
                self.assertEqual([invocation.args[0] for invocation in require.call_args_list], [
                    *(locked[name] for name in names), source,
                ])
                install_env = {**inherited, "TMPDIR": str(scratch)}
                vendor_env = {
                    "PATH": f"{tools / 'bin'}{os.pathsep}/host/bin", "FIXTURE": "retained",
                    "TMPDIR": str(scratch), "CARGO_HOME": str(root / "cargo"),
                    "RUSTC_WRAPPER": "", "RUSTC": str(tools / "bin/rustc"),
                }
                install_calls = [
                    call([str(temporary / name / f"{name}-release/install.sh"), f"--prefix={tools}", "--disable-ldconfig"],
                         cwd=temporary / name / f"{name}-release", env=install_env)
                    for name in names
                ]
                vendor_calls = [
                    call(["patch", "--batch", "-p1", "-i", str(provider_patch)], cwd=project, env=vendor_env),
                    call([
                        str(tools / "bin/cargo"), "vendor", "--locked", "--sync",
                        str(tools / "lib/rustlib/src/rust/library/Cargo.toml"), str(vendored / "vendor"),
                    ], cwd=project, env=vendor_env),
                ]
                self.assertEqual(execute.call_args_list, [*install_calls, *vendor_calls])
                implementation = file_sha256(Path(rust.__file__))
                tool_record = json.loads((tools / "phase.json").read_text())
                self.assertEqual(tool_record["inputs"], {
                    **{name: locked[name].sha256 for name in names}, "implementation": implementation,
                })
                record = json.loads((vendored / "phase.json").read_text())
                self.assertEqual(record["inputs"], {
                    "tools": tool_record["output_digest"], "source": source.sha256,
                    "patch": file_sha256(provider_patch), "implementation": implementation,
                })
                self.assertEqual((project / "provider.patch").read_bytes(), b"original provider patch")
                self.assertEqual((vendored / "vendor/package").read_bytes(), b"vendor fixture")

                require.reset_mock()
                execute.reset_mock()
                self.assertEqual(rust.vendor(cache, components, source, provider_patch, root, scratch), vendored)
                require.assert_not_called()
                execute.assert_not_called()

                provider_patch.write_bytes(b"updated provider patch")
                os.environ.pop("PATH")
                self.assertEqual(rust.vendor(cache, components, source, provider_patch, root, scratch), vendored)
                require.assert_called_once_with(source)
                self.assertEqual(len(execute.call_args_list), 2)
                self.assertEqual(execute.call_args.kwargs["env"]["PATH"], f"{tools / 'bin'}{os.pathsep}")
                self.assertEqual((project / "provider.patch").read_bytes(), b"updated provider patch")

            self.assertEqual(output.getvalue().splitlines(), [
                f"Rust sources vendored at {vendored}",
                f"Rust sources reused at {vendored}",
                f"Rust sources vendored at {vendored}",
            ])

    def test_rejects_missing_or_duplicate_components_before_cache_reads(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        entries = bootstrap_inputs(load_bootstrap(ROOT / "bootstrap.lock.json"), description.triple)
        locked = {item.name: item for item in entries}
        components = [locked[name] for name in ("rustc", "cargo", "rust-std", "rust-src")]
        with workspace() as directory:
            cache = Cache(directory / "cache", offline=True)
            with patch.object(cache, "require") as require:
                for invalid in (components[:-1], [*components, components[0]]):
                    with self.subTest(count=len(invalid)), self.assertRaisesRegex(
                        rust.RustError, "^Rust component lock is incomplete or duplicated$",
                    ):
                        rust.install_tools(cache, invalid, directory / "rust", directory / "scratch")
                require.assert_not_called()
            self.assertFalse((directory / "scratch").exists())

    def test_rejects_flat_component_and_source_archives_before_commands(self) -> None:
        description = target("aarch64-unknown-linux-musl")
        components = bootstrap_inputs(load_bootstrap(ROOT / "bootstrap.lock.json"), description.triple)
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        with workspace() as directory:
            flat = archive(directory / "flat.tar.gz", [("plain-file", b"file", None)])
            cache = Cache(directory / "cache", offline=True)
            scratch = directory / "scratch"
            root = directory / "rust"
            provider_patch = directory / "provider.patch"
            provider_patch.write_bytes(b"provider patch")
            tools = directory / "prepared tools"
            tools.mkdir()
            (tools / "phase.json").write_text(json.dumps({"output_digest": "a" * 64}))

            with patch.object(cache, "require", return_value=flat), patch.object(rust, "_run") as run:
                with self.assertRaisesRegex(rust.RustError, "^rustc: expected one component directory$"):
                    rust.install_tools(cache, components, root, scratch)
                with patch.object(rust, "install_tools", return_value=tools), self.assertRaisesRegex(
                    rust.RustError, "^rustls-ffi: expected one source directory$",
                ):
                    rust.vendor(cache, components, source, provider_patch, root, scratch)
                run.assert_not_called()

    def test_rust_environment_removes_only_host_compiler_overrides(self) -> None:
        inherited = {
            "RUSTFLAGS": "flags", "CARGO_ENCODED_RUSTFLAGS": "encoded", "CARGO_BUILD_RUSTFLAGS": "build",
            "CARGO_TARGET_X86_64_UNKNOWN_LINUX_MUSL_RUSTFLAGS": "target flags",
            "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER": "target linker",
            "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUNNER": "target runner",
            "PROJECT_RUSTFLAGS": "project flags", "PATH": "/host/bin",
        }
        with patch.dict(os.environ, inherited, clear=True):
            self.assertEqual(rust._rust_environment(), {
                "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUNNER": "target runner",
                "PROJECT_RUSTFLAGS": "project flags", "PATH": "/host/bin",
            })

    def test_cargo_config_quotes_the_vendor_directory(self) -> None:
        with workspace() as directory:
            vendored = directory / 'vendor "checkout"'
            rust._cargo_config(directory, vendored)
            self.assertEqual(tomllib.loads((directory / "config.toml").read_text()), {
                "source": {
                    "crates-io": {"replace-with": "vendored-sources"},
                    "vendored-sources": {"directory": str(vendored / "vendor")},
                },
            })


class RustProcessTests(unittest.TestCase):
    def test_runs_in_own_process_group_and_reports_bounded_output(self) -> None:
        command = ["cargo", "vendor"]
        cwd = Path("/fixture/source")
        env = {"PATH": "/locked/bin"}
        process = Mock(pid=1234, returncode=0)
        process.communicate.return_value = ("cargo output", "cargo diagnostics")
        signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
        previous = {signum: signal.getsignal(signum) for signum in signals}

        with patch.object(rust.subprocess, "Popen", return_value=process) as spawn, \
                patch.object(rust.os, "killpg") as kill_group, patch.object(rust.os, "kill") as forward:
            self.assertEqual(rust._run(command, cwd=cwd, env=env), "cargo output")
            expected = call(
                command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True,
            )
            self.assertEqual(spawn.call_args_list, [expected])
            process.communicate.assert_called_once_with(timeout=1800)
            self.assertEqual({signum: signal.getsignal(signum) for signum in signals}, previous)

            process.returncode = 7
            process.communicate.return_value = ("old stdout\n" + "a" * 4000, "old stderr\n" + "b" * 4000)
            with self.assertRaises(rust.RustError) as failure:
                rust._run(command, cwd=cwd, env=env)
            self.assertEqual(str(failure.exception), "cargo failed (7):\n" + "a" * 4000 + "\n" + "b" * 4000)
            kill_group.assert_not_called()
            forward.assert_not_called()

    def test_start_failure_and_timeout_preserve_causes_and_reap_child(self) -> None:
        command = ["cargo", "vendor"]
        cwd = Path("/fixture/source")
        env = {"PATH": "/locked/bin"}
        missing = FileNotFoundError("fixture executable is absent")
        with patch.object(rust.subprocess, "Popen", side_effect=missing), \
                patch.object(rust.os, "killpg") as kill, patch.object(rust.os, "kill"):
            with self.assertRaises(rust.RustError) as failure:
                rust._run(command, cwd=cwd, env=env)
            self.assertEqual(str(failure.exception), f"cargo could not complete: {missing}")
            self.assertIs(failure.exception.__cause__, missing)
            kill.assert_not_called()

        process = Mock(pid=1234)
        timeout = subprocess.TimeoutExpired(command, 1800)
        process.communicate.side_effect = [timeout, ("", "")]
        with patch.object(rust.subprocess, "Popen", return_value=process), patch.object(rust.os, "kill"), patch.object(
            rust.os, "killpg", side_effect=ProcessLookupError("fixture child exited"),
        ) as kill:
            with self.assertRaises(rust.RustError) as failure:
                rust._run(command, cwd=cwd, env=env)
            self.assertEqual(str(failure.exception), "cargo exceeded its deadline")
            self.assertIs(failure.exception.__cause__, timeout)
            kill.assert_called_once_with(1234, signal.SIGKILL)
            self.assertEqual(process.communicate.call_args_list, [call(timeout=1800), call()])

    def test_reaps_group_before_forwarding_an_interrupt(self) -> None:
        signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
        events = Mock()
        process = Mock(pid=1234)

        def communicate(*, timeout=None):
            if timeout is not None:
                handler = events.signal.call_args_list[1].args[1]
                handler(signal.SIGTERM, None)
            return "", ""

        process.communicate.side_effect = communicate
        events.attach_mock(process.communicate, "communicate")
        events.signal.return_value = signal.SIG_IGN
        with patch.object(rust.subprocess, "Popen", return_value=process), \
                patch.object(rust.signal, "signal", events.signal), \
                patch.object(rust.os, "killpg", events.killpg), \
                patch.object(rust.os, "getpid", return_value=5678), \
                patch.object(rust.os, "kill", events.kill), self.assertRaises(rust._Interrupted):
            rust._run(["cargo"], cwd=Path("/fixture"), env={})
        signals_installed = events.signal.call_args_list[:4]
        self.assertEqual([invocation.args[0] for invocation in signals_installed], list(signals))
        self.assertTrue(all(callable(invocation.args[1]) for invocation in signals_installed))
        self.assertEqual(events.mock_calls[4:], [
            call.communicate(timeout=1800),
            *(call.signal(signum, signal.SIG_IGN) for signum in signals),
            call.killpg(1234, signal.SIGKILL),
            call.communicate(),
            call.signal(signal.SIGTERM, signal.SIG_DFL),
            call.kill(5678, signal.SIGTERM),
            *(call.signal(signum, signal.SIG_IGN) for signum in signals),
        ])


class RustPhaseRecordTests(unittest.TestCase):
    def test_loads_the_output_digest_and_rejects_an_unfinished_phase(self) -> None:
        with workspace() as directory:
            phase = PhaseCache(directory).run(
                "tools", {"rustc": "a" * 64}, lambda path: (path / "rustc").write_bytes(b"fixture"),
            ).directory
            record = json.loads((phase / "phase.json").read_text())
            self.assertEqual(rust._phase_digest(phase), record["output_digest"])
            (phase / "state.json").write_text('{"status":"interrupted"}')
            with self.assertRaises(rust.RustError) as unfinished:
                rust._phase_digest(phase)
            self.assertEqual(str(unfinished.exception), f"{phase}: phase output does not match its record")

    def test_rejects_missing_and_malformed_phase_records(self) -> None:
        with workspace() as directory:
            record = directory / "phase.json"
            with self.assertRaises(rust.RustError) as failure:
                rust._phase_digest(directory)
            self.assertEqual(str(failure.exception), f"{directory}: missing or invalid phase record")
            self.assertIsInstance(failure.exception.__cause__, FileNotFoundError)
            for contents, cause in (("{", ValueError), ("{}", KeyError), ("null", TypeError)):
                record.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(rust.RustError) as failure:
                    rust._phase_digest(directory)
                self.assertEqual(str(failure.exception), f"{directory}: missing or invalid phase record")
                self.assertIsInstance(failure.exception.__cause__, cause)


class RustStaticBuildTests(unittest.TestCase):
    def test_sealed_build_uses_locked_compiler_and_static_archive(self) -> None:
        description = target("aarch64-unknown-linux-musl")
        with workspace() as directory:
            root = directory / "rust"
            tools = root / "phases/tools"
            vendored = root / "phases/vendor"
            archive_root = root / "phases/staticlib"
            home = archive_root / "cargo"
            project = vendored / "source/rustls"
            project.mkdir(parents=True)
            manifest = b"[package]\nname = 'rustls-ffi'\n"
            (project / "Cargo.toml").write_bytes(manifest)
            prepared = directory / "prepared"
            tc = prepared / "toolchain"
            sysroot = prepared / "sysroot"
            kache = directory / "build-kache"
            kache.write_bytes(b"installed compiler cache")
            scratch = directory / "scratch"
            archive_path = archive_root / "target" / description.triple / "release/librustls_ffi.a"
            host_runtime = Path("/usr/lib/libgcc_s.so.1")
            original_is_file = Path.is_file
            digests = {tools: "a" * 64, vendored: "b" * 64, prepared: "c" * 64}
            stream = io.StringIO()

            def is_file(path):
                return path == host_runtime or original_is_file(path)

            def build(command, *, cwd, env):
                if Path(command[0]).name == "cargo":
                    archive_path.parent.mkdir(parents=True)
                    archive_path.write_bytes(b"fixture static archive")
                    return ""
                return "\n0000 T rustls_fixture\n"

            inherited = {"PATH": "/host/bin", "RUSTFLAGS": "host flags", "FIXTURE": "retained"}
            with contextlib.redirect_stdout(stream), patch.dict(os.environ, inherited, clear=True), \
                    patch.object(sandbox, "in_container", return_value=True), \
                    patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo")]), \
                    patch.object(rust.toolchain, "verify") as verify, \
                    patch.object(Path, "is_file", is_file), patch.object(rust, "_phase_digest", side_effect=digests.__getitem__), \
                    patch.object(sandbox, "_locked_image_fingerprint", return_value="d" * 64) as image, \
                    patch.object(rust, "_run", side_effect=build) as run:
                result = rust.build_static(root, prepared, description, kache, scratch)
                self.assertEqual(result, archive_path)
                self.assertEqual(result.read_bytes(), b"fixture static archive")
                verify.assert_called_once_with(tc, description, environ={**inherited, "PATH": f"{tc / 'bin'}{os.pathsep}/host/bin"})
                image.assert_called_once_with(description)
                host_libs = archive_root / "host-libs"
                self.assertEqual((host_libs / "libgcc_s.so").readlink(), host_runtime)
                self.assertEqual((archive_root / "source/Cargo.toml").read_bytes(), manifest)
                self.assertEqual(tomllib.loads((home / "config.toml").read_text()), {
                    "source": {
                        "crates-io": {"replace-with": "vendored-sources"},
                        "vendored-sources": {"directory": str(vendored / "vendor")},
                    },
                })
                environment = {
                    "PATH": f"{tools / 'bin'}{os.pathsep}{tc / 'bin'}{os.pathsep}/host/bin", "FIXTURE": "retained",
                    "TMPDIR": str(scratch), "CARGO_HOME": str(home), "CARGO_TARGET_DIR": str(archive_root / "target"),
                    "XDG_CACHE_HOME": str(scratch / "kache-cache"), "XDG_CONFIG_HOME": str(scratch / "kache-config"),
                    "RUSTC_WRAPPER": str(kache), "RUSTC": str(tools / "bin/rustc"), "LIBRARY_PATH": str(host_libs),
                    "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER": str(tc / "bin/clang"),
                    "RUSTFLAGS": (
                        "--remap-path-prefix=/proc/self/cwd=/workspace "
                        f"-C link-arg=--sysroot={sysroot} -C link-arg=-fuse-ld=lld -L native={tc / 'lib'}"
                    ),
                }
                self.assertEqual(run.call_args_list, [
                    call([
                        str(tools / "bin/cargo"), "build", "--release", "--offline", "--frozen", "--target", description.triple,
                        "-Zbuild-std=std,panic_unwind", "-Zbuild-std-features=panic-unwind,backtrace,llvm-libunwind",
                        "--no-default-features", "--features", "graviola",
                    ], cwd=archive_root / "source", env=environment),
                    call([str(tc / "bin/llvm-nm"), "-g", str(archive_path)], cwd=archive_root, env=environment),
                ])
                record = json.loads((archive_root / "phase.json").read_text())
                self.assertEqual(record["inputs"], {
                    "tools": digests[tools], "vendor": digests[vendored], "prepare": digests[prepared],
                    "image": "d" * 64, "kache": rust.wrapper_identity(kache),
                    "implementation": file_sha256(Path(rust.__file__)),
                })

                run.reset_mock()
                self.assertEqual(rust.build_static(root, prepared, description, kache, scratch), archive_path)
                run.assert_not_called()
                kache.write_bytes(b"updated compiler cache")
                os.environ.pop("PATH")
                self.assertEqual(rust.build_static(root, prepared, description, kache, scratch), archive_path)
                self.assertEqual(len(run.call_args_list), 2)
                self.assertEqual(run.call_args.kwargs["env"]["PATH"], f"{tools / 'bin'}{os.pathsep}{tc / 'bin'}{os.pathsep}")
                self.assertEqual(verify.call_args.kwargs["environ"]["PATH"], f"{tc / 'bin'}{os.pathsep}")

            self.assertEqual(stream.getvalue().splitlines(), [
                f"Rustls static library built at {archive_root}",
                f"Rustls static library reused at {archive_root}",
                f"Rustls static library built at {archive_root}",
            ])

    def test_static_build_rejects_host_execution_with_exact_error(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory, patch.object(sandbox, "in_container", return_value=False), \
                patch.object(rust, "_run") as run, self.assertRaises(rust.RustError) as failure:
            rust.build_static(directory, directory, description, directory, directory)
        self.assertEqual(str(failure.exception), "Rustls build requires a sealed container with only loopback networking")
        run.assert_not_called()

    def test_static_build_rejects_incomplete_or_wrong_outputs(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        host_runtime = Path("/usr/lib/libgcc_s.so.1")
        original_is_file = Path.is_file
        for failure, symbols, diagnostic in (
            ("layout", "", "vendored Rustls source has an invalid layout"),
            ("runtime", "", f"missing host procedural-macro runtime {host_runtime}"),
            ("archive", "", "Rustls static archive was not produced"),
            ("symbols", "\n0000 T SSL_fixture\n", "Rustls static archive contains OpenSSL symbols"),
            ("symbols", "         U OPENSSL_fixture\n", "Rustls static archive contains OpenSSL symbols"),
        ):
            with self.subTest(failure=failure, symbols=symbols), workspace() as directory:
                root = directory / "rust"
                vendored = root / "phases/vendor/source"
                vendored.mkdir(parents=True)
                if failure == "layout":
                    (vendored / "flat-file").touch()
                else:
                    (vendored / "rustls").mkdir()
                kache = directory / "kache"
                kache.write_bytes(b"wrapper")
                archive_path = root / "phases/staticlib/target" / description.triple / "release/librustls_ffi.a"

                def is_file(path, available=failure != "runtime"):
                    if path == host_runtime:
                        return available
                    return original_is_file(path)

                def build(command, *, cwd, env, artifact=archive_path, produce=failure != "archive", symbol_text=symbols):
                    if Path(command[0]).name == "cargo":
                        if produce:
                            artifact.parent.mkdir(parents=True)
                            artifact.write_bytes(b"fixture archive")
                        return ""
                    return symbol_text

                with patch.object(sandbox, "in_container", return_value=True), \
                        patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo")]), \
                        patch.object(rust.toolchain, "verify"), patch.object(Path, "is_file", is_file), \
                        patch.object(rust, "_phase_digest", return_value="a" * 64), \
                        patch.object(sandbox, "_locked_image_fingerprint", return_value="b" * 64), \
                        patch.object(rust, "_run", side_effect=build), self.assertRaises(rust.RustError) as error:
                    rust.build_static(root, directory / "prepared", description, kache, directory)
                self.assertEqual(str(error.exception), diagnostic)


if __name__ == "__main__":
    unittest.main()
