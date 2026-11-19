from __future__ import annotations

import contextlib
import io
import json
import os
import tomllib
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import ROOT, archive, file_sha256, workspace

from buildsys import rust
from buildsys.inputs import Cache, bootstrap_inputs, load_bootstrap, load_sources
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


if __name__ == "__main__":
    unittest.main()
