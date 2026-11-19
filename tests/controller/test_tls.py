from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, file_sha256, workspace

from buildsys import rust, sandbox, tls
from buildsys.inputs import Cache, Input, bootstrap_inputs, load_bootstrap, load_sources
from buildsys.phases import PhaseCache
from buildsys.rust import RustError, _phase_digest, build_static, vendor
from buildsys.targets import native_target, target
from buildsys.tls import TlsError, build_client, check_host_vendored, check_tree


class DependencyTests(unittest.TestCase):
    def test_dependency_check_runs_locked_offline_provider_query(self) -> None:
        cargo = Path("toolchain/bin/cargo")
        manifest = Path("vendored/source/rustls/Cargo.toml")
        description = target("aarch64-unknown-linux-musl")
        launcher = ("/locked/musl", "--library-path", "/locked/lib")
        env = {"CARGO_HOME": "/prepared/cargo"}
        graph = "rustls-ffi v0.15.7\n\nrustls-graviola v0.4.0\ngraviola v0.4.4\n"
        with patch.object(tls, "_run", return_value=graph) as run:
            tls.check_dependencies(cargo, manifest, description.triple, env, launcher)
        run.assert_called_once_with(
            [
                *launcher, str(cargo.resolve()), "tree", "--manifest-path", str(manifest.resolve()),
                "--locked", "--offline", "--no-default-features", "--features", "graviola",
                "--target", description.triple, "-e", "normal", "--prefix", "none", "--format", "{p}",
            ],
            cwd=manifest.resolve().parent,
            env=env,
        )

        error = RustError("locked Cargo graph could not be read")
        with patch.object(tls, "_run", side_effect=error), self.assertRaises(TlsError) as raised:
            tls.check_dependencies(cargo, manifest, description.triple, env)
        self.assertEqual(str(raised.exception), str(error))
        self.assertIs(raised.exception.__cause__, error)

        with patch.object(tls, "_run", return_value=graph + "ring v1.0.0\n"), self.assertRaisesRegex(
            TlsError, r"missing \[\], forbidden \['ring'\]",
        ):
            tls.check_dependencies(cargo, manifest, description.triple, env)

    def test_vendored_dependency_check_sets_up_and_removes_cargo_home(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            vendored = directory / "vendored"
            project = vendored / "source/rustls"
            project.mkdir(parents=True)
            tools = directory / "toolchain/bin"
            homes = []

            def check(cargo, manifest, triple, env):
                self.assertEqual(cargo, tools / "cargo")
                self.assertEqual(manifest, project / "Cargo.toml")
                self.assertEqual(triple, description.triple)
                cargo_home = Path(env["CARGO_HOME"])
                self.assertEqual(cargo_home.parent, directory)
                self.assertTrue(cargo_home.name.startswith("cargo-check-"))
                self.assertEqual(
                    tomllib.loads((cargo_home / "config.toml").read_text()),
                    {"source": {
                        "crates-io": {"replace-with": "vendored-sources"},
                        "vendored-sources": {"directory": str(vendored / "vendor")},
                    }},
                )
                self.assertEqual(env["RUSTC"], str(tools / "rustc"))
                self.assertEqual(env["RUSTC_WRAPPER"], "")
                self.assertEqual(env["PATH"], f"{tools}{os.pathsep}{host_path}")
                self.assertEqual(env["TMPDIR"], str(directory))
                self.assertNotIn("RUSTFLAGS", env)
                homes.append(cargo_home)

            for host_path, inherited in [
                ("/host/bin", {"PATH": "/host/bin", "RUSTFLAGS": "from-host"}),
                ("", {"RUSTFLAGS": "from-host"}),
            ]:
                with self.subTest(host_path=host_path), patch.dict(os.environ, inherited, clear=True), patch.object(
                    tls, "check_dependencies", side_effect=check,
                ) as check_dependencies:
                    tls.check_vendored(vendored, tools, description.triple, directory)
                    check_dependencies.assert_called_once()
            self.assertEqual(len(homes), 2)
            self.assertTrue(all(not home.exists() for home in homes))

    def test_vendored_dependency_check_rejects_invalid_source_layouts(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory, patch.object(tls, "check_dependencies") as check:
            source = directory / "source"
            source.mkdir()
            entry = source / "rustls"
            for layout in ("empty", "file", "multiple directories"):
                if layout == "file":
                    entry.touch()
                elif layout == "multiple directories":
                    entry.unlink()
                    entry.mkdir()
                    (source / "second").mkdir()
                with self.subTest(layout=layout), self.assertRaisesRegex(
                    TlsError, "^vendored Rustls source has an invalid layout$",
                ):
                    tls.check_vendored(directory, directory / "toolchain/bin", description.triple, directory)
            check.assert_not_called()

    def test_client_rebuilds_when_builder_image_changes(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        source = Input(name="cmake-source", version="4.4.5", urls=("https://example.invalid/cmake",), sha256="a" * 64, role="source", target="all", size=1)
        with workspace() as directory:
            root = directory / "build"
            prepared = directory / "prepared"
            toolchain = prepared / "toolchain"
            sysroot = prepared / "sysroot"
            bootstrap = root / "phases/tls-bootstrap"
            qualification = root / "phases/tls-client"
            source_root = bootstrap / "source/cmake-source"
            staticlib = directory / "rust/phases/staticlib"
            archive = staticlib / "target" / description.triple / "debug/librustls_ffi.a"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"archive")
            (staticlib / "source").mkdir()
            (staticlib / "source/Cargo.toml").write_text('[package]\nversion = "0.15.7"\n')
            client = directory / "client.c"
            client.write_text("int main(void) { return 0; }\n")
            build_commands = []
            digests = {prepared: "b" * 64, bootstrap: "e" * 64, staticlib: "f" * 64}
            stdout = io.StringIO()

            def extract(archive_path, destination):
                self.assertEqual(archive_path, directory / "source")
                self.assertEqual(destination, bootstrap / "source")
                (destination / "cmake-source").mkdir(parents=True)
                return destination

            def extract_flat(archive_path, destination):
                destination.mkdir(parents=True)
                (destination / "cmake-source").touch()
                return destination

            def run(command, *, cwd, env):
                build_commands.append((command, cwd, env.copy()))
                if Path(command[0]).name == "clang":
                    Path(command[-1]).write_bytes(b"client")
                return ""

            with contextlib.redirect_stdout(stdout), \
                    patch.dict(os.environ, {"PATH": "/host/bin", "TLS_FIXTURE": "retained"}, clear=True), \
                    patch.object(os, "process_cpu_count", return_value=7) as cpus, \
                    patch.object(tls.toolchain, "verify") as verify, patch.object(tls, "_phase_digest", side_effect=digests.__getitem__), \
                    patch.object(tls, "safe_extract", side_effect=extract) as stage, patch.object(tls, "_run", side_effect=run), \
                    patch.object(Cache, "require", return_value=directory / "source") as require, \
                    patch.object(sandbox, "image_fingerprint", return_value="c" * 64) as image:
                output = build_client(Cache(directory), source, prepared, archive, description, root, directory, client)
                self.assertEqual(output, qualification / "client")
                self.assertEqual(output.read_bytes(), b"client")
                verify.assert_called_once_with(toolchain, description, environ={
                    "PATH": f"{toolchain / 'bin'}{os.pathsep}/host/bin",
                    "TLS_FIXTURE": "retained",
                })
                require.assert_called_once_with(source)
                self.assertEqual(image.call_args.args[1], description)

                flags = [
                    f"--target={description.triple}", f"--sysroot={sysroot}",
                    "-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=libunwind",
                ]
                build = qualification / "build"
                self.assertEqual([(command, cwd) for command, cwd, _ in build_commands], [
                    ([
                        str(source_root / "bootstrap"), "--parallel=7", "--no-system-libs", "--",
                        "-DCMAKE_USE_OPENSSL=OFF", f"-DCMAKE_SYSROOT={sysroot}",
                    ], bootstrap / "bootstrap"),
                    ([
                        str(bootstrap / "bootstrap/Bootstrap.cmk/cmake"),
                        "-S", str(source_root / "Utilities/cmcurl"), "-B", str(build),
                        "-DCMAKE_BUILD_TYPE=Debug", f"-DCMAKE_C_COMPILER={toolchain / 'bin/clang'}",
                        f"-DCMAKE_SYSROOT={sysroot}", "-DCMAKE_USE_OPENSSL=OFF", "-DCURL_USE_RUSTLS=ON",
                        "-DCURL_USE_LIBPSL=OFF", "-DBUILD_SHARED_LIBS=OFF", "-DCURL_CA_BUNDLE=none",
                        "-DCURL_CA_PATH=none", "-DRUSTLS_VERSION=0.15.7",
                        f"-DRUSTLS_INCLUDE_DIR={staticlib / 'source/src'}", f"-DRUSTLS_LIBRARY={archive}",
                        "-DCMAKE_C_FLAGS=" + shlex.join([
                            *flags, f"-I{source_root / 'Utilities'}", f"-I{bootstrap / 'bootstrap/Utilities'}",
                        ]),
                    ], qualification),
                    (["make", "-j7", "cmcurl"], build),
                    ([
                        str(toolchain / "bin/clang"), *flags, "-static-pie",
                        f"-I{source_root / 'Utilities/cmcurl/include'}", str(client),
                        str(build / "lib/libcmcurl.a"), str(archive), f"-L{toolchain / 'lib'}",
                        "-lunwind", "-lm", "-ldl", "-lpthread", "-o", str(output),
                    ], qualification),
                ])
                for _, _, env in build_commands:
                    self.assertEqual(env["TLS_FIXTURE"], "retained")
                    self.assertEqual(env["TMPDIR"], str(directory))
                    self.assertEqual(env["CC"], str(toolchain / "bin/clang"))
                    self.assertEqual(env["TARGET"], description.triple)
                    self.assertEqual(env["CFLAGS"], shlex.join(flags))
                    self.assertEqual(env["CXXFLAGS"], shlex.join([*flags, "-stdlib=libc++"]))
                    self.assertEqual(env["LDFLAGS"], shlex.join(flags))
                implementation = file_sha256(Path(tls.__file__))
                self.assertEqual(json.loads((bootstrap / "phase.json").read_text())["inputs"], {
                    "prepare": digests[prepared], "source": source.sha256, "image": "c" * 64,
                    "toolchain": file_sha256(Path(tls.toolchain.__file__)), "implementation": implementation,
                })
                self.assertEqual(json.loads((qualification / "phase.json").read_text())["inputs"], {
                    "bootstrap": digests[bootstrap], "rustls": digests[staticlib], "image": "c" * 64,
                    "client": file_sha256(client), "implementation": implementation,
                })

                self.assertEqual(build_client(Cache(directory), source, prepared, archive, description, root, directory, client), output)
                self.assertEqual(len(build_commands), 4)
                image.return_value = "d" * 64
                cpus.return_value = None
                os.environ.pop("PATH")
                self.assertEqual(build_client(Cache(directory), source, prepared, archive, description, root, directory, client), output)
                self.assertEqual(len(build_commands), 8)
                self.assertEqual(verify.call_args.kwargs["environ"]["PATH"], f"{toolchain / 'bin'}{os.pathsep}")
                self.assertIn("--parallel=1", build_commands[4][0])
                self.assertEqual(build_commands[6][0], ["make", "-j1", "cmcurl"])
                self.assertEqual(stdout.getvalue().splitlines(), [
                    f"TLS client built at {qualification}",
                    f"TLS client reused at {qualification}",
                    f"TLS client built at {qualification}",
                ])

                image.return_value = "1" * 64
                stage.side_effect = extract_flat
                with self.assertRaisesRegex(TlsError, "^CMake archive has an invalid layout$"):
                    build_client(Cache(directory), source, prepared, archive, description, root, directory, client)
                self.assertEqual(len(build_commands), 8)

    def test_static_build_rebuilds_when_builder_image_changes(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            root = directory / "rust"
            (root / "phases/vendor/source/crate").mkdir(parents=True)
            kache = directory / "kache"
            kache.write_bytes(b"wrapper")
            original_is_file = Path.is_file
            cargo_runs = []

            def is_file(path):
                return True if path == Path("/usr/lib/libgcc_s.so.1") else original_is_file(path)

            def run(command, *, cwd, env):
                if Path(command[0]).name == "cargo":
                    cargo_runs.append(1)
                    archive = Path(env["CARGO_TARGET_DIR"]) / description.triple / "release/librustls_ffi.a"
                    archive.parent.mkdir(parents=True)
                    archive.write_bytes(b"archive")
                return ""

            with patch.object(sandbox, "in_container", return_value=True), \
                    patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo")]), \
                    patch.object(rust.toolchain, "verify"), patch.object(rust, "_phase_digest", return_value="a" * 64), \
                    patch.object(Path, "is_file", is_file), patch.object(rust, "_run", side_effect=run), \
                    patch.object(sandbox, "image_fingerprint", return_value="b" * 64) as image:
                build_static(root, directory / "prepared", description, kache, directory)
                build_static(root, directory / "prepared", description, kache, directory)
                self.assertEqual(len(cargo_runs), 1)
                image.return_value = "c" * 64
                build_static(root, directory / "prepared", description, kache, directory)
                self.assertEqual(len(cargo_runs), 2)

    def test_locked_graph_rejects_changed_provider_patch(self) -> None:
        native = native_target()
        lock = load_bootstrap(ROOT / "bootstrap.lock.json")
        inputs = bootstrap_inputs(lock, native.triple)
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        with workspace() as directory:
            patch_file = directory / "provider.patch"
            patch_file.write_bytes((ROOT / "patches/rustls-ffi/0001-graviola-provider.patch").read_bytes() + b"\n")
            with self.assertRaisesRegex(TlsError, "inputs changed"):
                check_host_vendored(ROOT / ".work/rust" / native.triple, native, inputs, source, patch_file,
                                    Cache(ROOT / ".work/cache", offline=True), [native.triple], ROOT / ".work/tmp")

    def test_host_dependency_check_uses_verified_phases_and_locked_runtime(self) -> None:
        native = target("x86_64-unknown-linux-musl")
        targets = [native.triple, "aarch64-unknown-linux-musl"]
        components = bootstrap_inputs(load_bootstrap(ROOT / "bootstrap.lock.json"), native.triple)
        locked = {item.name: item for item in components}
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        names = ("rustc", "cargo", "rust-std", "rust-src", "musl", "libgcc")
        required = [locked[name] for name in names]

        with workspace() as directory:
            root = directory / "rust"
            phases = PhaseCache(root / "phases")
            patch_file = directory / "provider.patch"
            patch_file.write_bytes(b"provider patch")
            implementation = file_sha256(Path(rust.__file__))
            tool_inputs = {name: locked[name].sha256 for name in ("rustc", "cargo", "rust-std", "rust-src")}
            tool_inputs["implementation"] = implementation
            tools = phases.run("tools", tool_inputs, lambda path: (path / "tool").write_bytes(b"tools")).directory
            vendor_inputs = {
                "tools": _phase_digest(tools), "source": source.sha256,
                "patch": file_sha256(patch_file), "implementation": implementation,
            }

            def stage_source(phase):
                project = phase / "source/rustls"
                project.mkdir(parents=True)
                (project / "Cargo.toml").write_text("[package]\n")

            vendored = phases.run("vendor", vendor_inputs, stage_source).directory
            homes = []
            checked_targets = []
            unpacked = []
            inherited = {
                "PATH": "/host/bin", "RUSTFLAGS": "from-host",
                "LD_LIBRARY_PATH": "/host/lib", "LD_PRELOAD": "/host/preload.so",
            }

            def extract(package, destination):
                unpacked.append((package, destination))
                if package.name == "musl":
                    loader = destination / native.musl_loader.removeprefix("/")
                    loader.parent.mkdir(parents=True)
                    loader.write_bytes(b"loader")
                else:
                    (destination / "usr/lib").mkdir(parents=True)
                return destination

            def check(cargo, manifest, triple, env, launcher):
                self.assertEqual(cargo, tools / "bin/cargo")
                self.assertEqual(manifest, vendored / "source/rustls/Cargo.toml")
                temporary = Path(env["CARGO_HOME"]).parent
                self.assertEqual(temporary.parent, directory)
                self.assertTrue(temporary.name.startswith("cargo-host-check-"))
                loader = temporary / "musl" / native.musl_loader.removeprefix("/")
                libgcc = temporary / "libgcc/usr/lib"
                rustc = temporary / "rustc"
                cargo_home = temporary / "cargo"
                self.assertEqual(launcher, (str(loader), "--library-path", f"{libgcc}{os.pathsep}{tools / 'lib'}"))
                self.assertEqual(rustc.read_text(), "#!/bin/sh\nexec " + shlex.join([
                    *launcher, str(tools / "bin/rustc"),
                ]) + ' "$@"\n')
                self.assertEqual(rustc.stat().st_mode & 0o777, 0o755)
                self.assertEqual(env, {
                    "PATH": "/host/bin", "CARGO_HOME": str(cargo_home), "TMPDIR": str(directory),
                    "RUSTC": str(rustc), "RUSTC_WRAPPER": "",
                })
                config = tomllib.loads((cargo_home / "config.toml").read_text())
                self.assertEqual(config["source"]["vendored-sources"]["directory"], str(vendored / "vendor"))
                homes.append(temporary)
                checked_targets.append(triple)

            cache = Cache(directory / "cache", offline=True)
            with patch.dict(os.environ, inherited, clear=True), \
                    patch.object(cache, "require", side_effect=lambda item: Path(item.name)) as require, \
                    patch.object(tls, "safe_extract", side_effect=extract) as unpack, \
                    patch.object(tls, "check_dependencies", side_effect=check) as verify:
                check_host_vendored(root, native, required, source, patch_file, cache, targets, directory)
                self.assertEqual([call.args[0] for call in require.call_args_list], [source, *required])
                self.assertEqual(checked_targets, targets)
                self.assertEqual(homes, [homes[0], homes[0]])
                self.assertEqual(unpacked, [(Path(name), homes[0] / name) for name in ("musl", "libgcc")])
                self.assertFalse(homes[0].exists())

                verify.reset_mock()
                require.reset_mock()
                diagnostic = "^bootstrap lock lacks or duplicates a Rust or host runtime component$"
                for name in names:
                    with self.subTest(missing=name), self.assertRaisesRegex(TlsError, diagnostic):
                        check_host_vendored(
                            root, native, [item for item in components if item.name != name],
                            source, patch_file, cache, targets, directory,
                        )
                    with self.subTest(duplicate=name), self.assertRaisesRegex(TlsError, diagnostic):
                        check_host_vendored(root, native, [*components, locked[name]], source, patch_file, cache, targets, directory)
                require.assert_not_called()

                record_path = vendored / "phase.json"
                valid_record = record_path.read_text()
                record = json.loads(valid_record)
                record["fingerprint"] = "1" * 64
                record_path.write_text(json.dumps(record))
                with self.assertRaises(TlsError) as stale:
                    check_host_vendored(root, native, required, source, patch_file, cache, targets, directory)
                self.assertEqual(str(stale.exception), f"{vendored}: inputs changed; run fetch")
                record_path.write_text(valid_record)

                unpack.side_effect = lambda package, destination: destination
                with self.assertRaisesRegex(TlsError, "^locked musl package does not contain its loader$"):
                    check_host_vendored(root, native, required, source, patch_file, cache, targets, directory)

                def stage_flat_source(phase):
                    (phase / "source").mkdir()
                    (phase / "source/rustls").touch()

                record_path.unlink()
                phases.run("vendor", vendor_inputs, stage_flat_source)
                unpack.reset_mock()
                with self.assertRaisesRegex(TlsError, "^vendored Rustls source has an invalid layout$"):
                    check_host_vendored(root, native, required, source, patch_file, cache, targets, directory)
                unpack.assert_not_called()
                verify.assert_not_called()

    def test_locked_dependency_graph_for_both_targets(self) -> None:
        native = native_target()
        lock = load_bootstrap(ROOT / "bootstrap.lock.json")
        inputs = bootstrap_inputs(lock, native.triple)
        source = next(item for item in load_sources(ROOT / "sources.lock.json") if item.name == "rustls-ffi-source")
        rust_root = ROOT / ".work/rust" / native.triple
        check_host_vendored(rust_root, native, inputs, source, ROOT / "patches/rustls-ffi/0001-graviola-provider.patch", Cache(ROOT / ".work/cache", offline=True),
                            ["x86_64-unknown-linux-musl", "aarch64-unknown-linux-musl"], ROOT / ".work/tmp")

    def test_static_build_rejects_networked_container(self) -> None:
        with workspace() as directory, patch.object(sandbox, "in_container", return_value=True), patch.object(sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), self.assertRaisesRegex(RustError, "sealed container"):
            build_static(directory, directory, target("x86_64-unknown-linux-musl"), directory, directory)

    def test_rejects_tampered_vendor_phase(self) -> None:
        with workspace() as directory:
            phase = PhaseCache(directory).run("vendor", {"source": "a" * 64}, lambda path: (path / "crate").write_bytes(b"verified"))
            self.assertTrue(_phase_digest(phase.directory))
            (phase.directory / "crate").write_bytes(b"tampered")
            with self.assertRaisesRegex(RustError, "does not match"):
                _phase_digest(phase.directory)

    def test_rejects_non_string_phase_digest_before_scanning_output(self) -> None:
        with workspace() as directory, patch.object(rust, "tree_digest") as digest:
            (directory / "phase.json").write_text('{"output_digest": 42}\n')
            with self.assertRaisesRegex(RustError, "does not match"):
                _phase_digest(directory)
            digest.assert_not_called()

    def test_vendor_process_tree_stops_on_termination(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(10)
            child = "import socket,sys; s=socket.socket(); s.connect(('127.0.0.1',int(sys.argv[1]))); s.sendall(b'ready'); s.recv(1)"
            owner = "import os,sys; from pathlib import Path; from buildsys.rust import _run; _run([sys.executable,'-c',sys.argv[1],sys.argv[2]],cwd=Path('.'),env=dict(os.environ))"
            process = subprocess.Popen([sys.executable, "-c", owner, child, str(listener.getsockname()[1])])
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(10)
                    self.assertEqual(connection.recv(5), b"ready")
                    process.send_signal(signal.SIGTERM)
                    self.assertEqual(connection.recv(1), b"")
                self.assertEqual(process.wait(timeout=10), -signal.SIGTERM)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_vendor_rejects_incomplete_toolchain_lock(self) -> None:
        with workspace() as directory, self.assertRaisesRegex(RustError, "component lock is incomplete"):
            source = Input(name="source", version="1", urls=("https://example.invalid",), sha256="a" * 64, role="source", target="all", size=1)
            vendor(Cache(directory / "cache"), [], source, Path("patch"), directory, directory)

    def test_graviola_closure_accepts_certificate_path_probe(self) -> None:
        check_tree("rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\nopenssl-probe v0.2.1\n")

    def test_rejects_other_crypto_providers_and_missing_provider(self) -> None:
        for package in ("ring", "aws-lc-rs", "aws-lc-sys", "openssl", "openssl-sys", "native-tls"):
            with self.subTest(package=package), self.assertRaises(TlsError):
                check_tree(f"rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\n{package} v1.0.0\n")
        required = ("rustls-ffi", "rustls-graviola", "graviola")
        for missing in required:
            graph = "\n".join(f"{package} v1.0.0" for package in required if package != missing)
            with self.subTest(missing=missing), self.assertRaises(TlsError) as error:
                check_tree(graph)
            self.assertEqual(str(error.exception), f"TLS dependency closure: missing ['{missing}'], forbidden []")


if __name__ == "__main__":
    unittest.main()
