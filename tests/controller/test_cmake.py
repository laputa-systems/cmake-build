from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import workspace

import build
from buildsys import cmake
from buildsys.cmake import CMakeBuildError, check_capabilities
from buildsys.dependencies import DependencyError, graph_reachability
from buildsys.patches import Patch
from buildsys.targets import target


class CMakeBuildTests(unittest.TestCase):
    def test_build_rejects_networked_container(self) -> None:
        args = build._parser().parse_args(["build", "--target", "x86_64-unknown-linux-musl", "--in-container"])
        with patch.object(build.sandbox, "in_container", return_value=True), \
                patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            args.handler(args)

    def test_dependency_reachability_uses_actual_target_edges(self) -> None:
        graph = '''digraph "CMake" {
    "node0" [ label = "cmake", shape = egg ];
    "node1" [ label = "ctest", shape = egg ];
    "node2" [ label = "cpack", shape = egg ];
    "node3" [ label = "cmcurl\\n(CURL::libcurl)", shape = octagon ];
    "node4" [ label = "cmtestonly", shape = octagon ];
    "node0" -> "node3";
    "node1" -> "node3";
    "node1" -> "node4";
}'''
        reachable = graph_reachability(graph)
        self.assertEqual(reachable["cmcurl"], {"cmake", "ctest"})
        self.assertEqual(reachable["cmtestonly"], {"ctest"})
        with self.assertRaises(DependencyError):
            graph_reachability(graph.replace('label = "cpack"', 'label = "other"'))

    def test_requires_exact_version_tls_and_debugger(self) -> None:
        capabilities = {"version": {"string": "4.4.5"}, "tls": True, "debugger": True}
        check_capabilities(json.dumps(capabilities), "4.4.5")
        expectations = (
            ("not json", "CMake capabilities are not valid JSON"),
            ("[]", "CMake capabilities lack a version"),
            ('{"version":"4.4.5"}', "CMake capabilities lack a version"),
            ('{"version":{}}', r"CMake version does not match 4\.4\.5"),
            (json.dumps({**capabilities, "version": {"string": "4.4.4"}}),
             r"CMake version does not match 4\.4\.5"),
            (json.dumps({**capabilities, "tls": 1}), "CMake must include TLS and the debugger"),
            (json.dumps({**capabilities, "debugger": "true"}), "CMake must include TLS and the debugger"),
            (json.dumps({**capabilities, "debugger": False}), "CMake must include TLS and the debugger"),
        )
        for output, message in expectations:
            with self.subTest(output=output), self.assertRaisesRegex(CMakeBuildError, f"^{message}$"):
                check_capabilities(output, "4.4.5")

    def test_build_passes_the_pinned_inputs_and_requires_link_evidence(self) -> None:
        for mode, failure in (
            (cmake.BuildMode.QUALIFICATION, None),
            (cmake.BuildMode.DEVELOPMENT, None),
            (cmake.BuildMode.QUALIFICATION, "layout"),
            (cmake.BuildMode.QUALIFICATION, "version"),
            (cmake.BuildMode.QUALIFICATION, "missing"),
            (cmake.BuildMode.QUALIFICATION, "malformed"),
        ):
            with self.subTest(mode=mode, failure=failure):
                self._exercise_build(mode, failure)

    def test_development_can_reuse_an_existing_compiler_cache(self) -> None:
        self._exercise_build(cmake.BuildMode.DEVELOPMENT, None, existing_cache=True)

    def _exercise_build(self, mode: cmake.BuildMode, failure: str | None, *, existing_cache: bool = False) -> None:
        with workspace() as root:
            bootstrap = root / "fixture bootstrap"
            original = bootstrap / "source/cmake-release"
            original.mkdir(parents=True)
            (original / "CMakeLists.txt").write_text("fixture CMakeLists")
            (original / "cmake-link").symlink_to("CMakeLists.txt")
            if failure == "layout":
                (original.parent / "extra").mkdir()
            output = root / "fixture output"
            build_tree = output / "build"
            binary = build_tree / "bin"
            binary.mkdir(parents=True)
            prepared = root / "fixture prepared"
            archive = root / "rustls/a/b/c/archive.a"
            tools = prepared / "toolchain"
            kache = root / "fixture kache"
            cache = root / "fixture cache" / "compiler"
            if existing_cache:
                cache.mkdir(parents=True)
            description = target("aarch64-unknown-linux-musl")
            inventory = (
                Patch("rustls-ffi/fixture.patch", "b" * 64, b"applied by the Rust build"),
                Patch("cmake/fixture.patch", "a" * 64, b"apply this patch"),
            )
            for program in ("cmake", "ctest", "cpack"):
                (binary / program).touch()
                if program == "ctest" and failure == "missing":
                    continue
                content = "wrong header\n" if program == "ctest" and failure == "malformed" else (
                    "reference\textracted\tsymbol\n"
                )
                (build_tree / f"{program}.extract").write_text(content)

            version = "" if failure == "version" else "cmake version 4.4.5\n"
            capabilities = '{"version":{"string":"4.4.5"},"tls":true,"debugger":true}'
            patch_contents: list[bytes] = []

            def child(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
                if command[0] == "patch":
                    self.assertEqual(cwd, output / "source")
                    self.assertEqual(Path(command[-1]).parent, output)
                    patch_contents.append(Path(command[-1]).read_bytes())
                elif command[1:] == ["--version"]:
                    return version
                elif command[1:] == ["-E", "capabilities"]:
                    return capabilities
                return ""

            if failure == "layout":
                expected_error = self.assertRaisesRegex(CMakeBuildError, "^bootstrap source has an invalid layout$")
            elif failure == "version":
                expected_error = self.assertRaisesRegex(CMakeBuildError, r"^built CMake does not report version 4\.4\.5$")
            elif failure in {"missing", "malformed"}:
                expected_error = self.assertRaisesRegex(
                    CMakeBuildError, "^linker did not produce archive extraction evidence for ctest$"
                )
            else:
                expected_error = contextlib.nullcontext()
            with (
                patch.object(cmake, "_run", side_effect=child) as runner,
                patch.object(cmake.elf, "audit") as audit,
                patch.object(cmake.dependencies, "inventory", return_value="fixture report\n") as report,
                patch.dict(os.environ, {"CFLAGS": "host-c", "CXXFLAGS": "host-cxx", "LDFLAGS": "host-ld"}),
                patch.object(cmake.os, "process_cpu_count", return_value=None),
                expected_error,
            ):
                cmake.build(
                    bootstrap=bootstrap, prepared=prepared, archive=archive, inventory=inventory, directory=output,
                    target=description, cmake_version="4.4.5", rustls_version="0.16.2", mode=mode,
                    kache=kache, compiler_cache=cache,
                )

            source = output / "source"
            if failure == "layout":
                runner.assert_not_called()
                self.assertFalse(source.exists())
                return
            self.assertEqual((source / "cmake-link").readlink(), Path("CMakeLists.txt"))
            self.assertEqual((source / "cmake-link").read_text(), "fixture CMakeLists")
            self.assertEqual(patch_contents, [b"apply this patch"])
            launches = runner.call_args_list
            patch_command = launches[0].args[0]
            self.assertEqual(patch_command[:5], ["patch", "--batch", "--forward", "-p1", "-i"])
            self.assertFalse(Path(patch_command[-1]).exists())
            configure = launches[1]
            graph = output / "dependencies.dot"
            evidence = output / "link-evidence.cmake"
            ninja = bootstrap / "ninja-build/ninja"
            self.assertEqual(configure.args[0][:9], [
                "/usr/bin/cmake", f"--graphviz={graph}", "-S", str(source), "-B", str(build_tree),
                "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
            ])
            self.assertEqual(configure.kwargs["cwd"], output)
            environment = configure.kwargs["env"]
            for variable in ("CFLAGS", "CXXFLAGS", "LDFLAGS"):
                self.assertNotIn(variable, environment)
            self.assertEqual(environment["TARGET"], description.triple)
            self.assertEqual(environment["CC"], str(tools / "bin/clang"))
            options = dict(arg[2:].split("=", 1) for arg in configure.args[0] if arg.startswith("-D"))
            release_flags = ["-O3", "-DNDEBUG", f"-ffile-prefix-map={source}=/usr/src/cmake"]
            libraries = f"-L{tools / 'lib'} -lunwind -ldl -lm -lpthread"
            expected_options = {
                "CMAKE_MAKE_PROGRAM": str(ninja),
                "CMAKE_TOOLCHAIN_FILE": str(bootstrap / "toolchain.cmake"),
                "CMAKE_PROJECT_INCLUDE": str(evidence),
                "CMAKE_BUILD_TYPE": "Release",
                "CMAKE_C_FLAGS_RELEASE": shlex.join(release_flags),
                "CMAKE_CXX_FLAGS_RELEASE": shlex.join(release_flags),
                "BUILD_CursesDialog": "OFF",
                "BUILD_QtDialog": "OFF",
                "CMAKE_USE_SYSTEM_LIBRARIES": "OFF",
                "CMake_ENABLE_DEBUGGER": "ON",
                "CMAKE_USE_OPENSSL": "OFF",
                "CURL_USE_RUSTLS": "ON",
                "CURL_USE_LIBPSL": "OFF",
                "CURL_CA_BUNDLE": "none",
                "CURL_CA_PATH": "none",
                "RUSTLS_VERSION": "0.16.2",
                "RUSTLS_INCLUDE_DIR": str(root / "rustls/source/src"),
                "RUSTLS_LIBRARY": str(archive),
                "CMAKE_C_STANDARD_LIBRARIES": libraries,
                "CMAKE_CXX_STANDARD_LIBRARIES": libraries,
                **dict.fromkeys((
                    "SPHINX_INFO", "SPHINX_MAN", "SPHINX_HTML", "SPHINX_SINGLEHTML", "SPHINX_LINKCHECK",
                    "SPHINX_QTHELP", "SPHINX_LATEXPDF", "SPHINX_TEXT", "SPHINX_INCLUDE_IN_ALL",
                ), "OFF"),
            }
            self.assertEqual(evidence.read_text().splitlines(), [
                'function(cmake_build_link_evidence)',
                '  foreach(tool cmake ctest cpack)',
                '    if(NOT TARGET ${tool})',
                '      message(FATAL_ERROR "${tool} target is missing")',
                '    endif()',
                ('    target_link_options(${tool} PRIVATE "LINKER:--gc-sections" '
                 '"LINKER:-Map,${CMAKE_BINARY_DIR}/${tool}.map" '
                 '"LINKER:--why-extract=${CMAKE_BINARY_DIR}/${tool}.extract")'),
                (f'    set_property(TARGET ${{tool}} PROPERTY RULE_LAUNCH_LINK '
                 f'"python3 -m buildsys.elf {shlex.quote(str(tools / "bin"))}")'),
                '  endforeach()',
                'endfunction()',
                'if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)',
                '  cmake_language(DEFER CALL cmake_build_link_evidence)',
                'endif()',
            ])
            if mode is cmake.BuildMode.DEVELOPMENT:
                compile_flags = [
                    f"--target={description.triple}", f"--sysroot={prepared / 'sysroot'}",
                ]
                hardening_flags = ["-fstack-protector-strong", "-fstack-clash-protection"]
                link_flags = ["-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=libunwind"]
                expected_options.update({
                    "CMAKE_C_COMPILER_LAUNCHER": str(kache),
                    "CMAKE_CXX_COMPILER_LAUNCHER": str(kache),
                    "CMAKE_C_FLAGS": shlex.join([*compile_flags, *hardening_flags]),
                    "CMAKE_CXX_FLAGS": shlex.join([*compile_flags, "-stdlib=libc++", *hardening_flags]),
                    "CMAKE_EXE_LINKER_FLAGS": shlex.join([
                        *link_flags, "-static-pie", "-Wl,-z,relro,-z,now,-z,noexecstack",
                    ]),
                    "CMAKE_SHARED_LINKER_FLAGS": shlex.join(link_flags),
                    "CMAKE_MODULE_LINKER_FLAGS": shlex.join(link_flags),
                })
                cache_environment = {
                    "XDG_CACHE_HOME": str(cache),
                    "XDG_CONFIG_HOME": str(cache / "config"),
                    "KACHE_CC_PATH_NORMALIZE": "0",
                    "KACHE_CC_SOURCE_DATE_EPOCH": "passthrough",
                }
                self.assertEqual({key: environment.get(key) for key in cache_environment}, cache_environment)
                self.assertTrue(cache.is_dir())
            else:
                self.assertFalse(cache.exists())
            self.assertEqual(options, expected_options)
            self.assertEqual(launches[0].kwargs.get("env"), environment)
            self.assertEqual(launches[2], call([str(ninja), "-C", str(build_tree), "-j1"], cwd=output, env=environment))
            self.assertEqual(launches[3], call([str(binary / "cmake"), "--version"], cwd=output, env=environment))
            if failure == "version":
                self.assertEqual(len(launches), 4)
                audit.assert_not_called()
            else:
                self.assertEqual(launches[4], call(
                    [str(binary / "cmake"), "-E", "capabilities"], cwd=output, env=environment,
                ))
            if failure is None:
                self.assertEqual(audit.call_args_list, [
                    call(binary / program, description, tools / "bin") for program in ("cmake", "ctest", "cpack")
                ])
                report.assert_called_once_with(source, graph, build_tree / "cmake.map", "4.4.5", "0.16.2")
                self.assertIn("dependencies.md", {path.name for path in output.iterdir()})
                self.assertEqual((output / "dependencies.md").read_text(), "fixture report\n")
            else:
                report.assert_not_called()
                self.assertFalse((output / "dependencies.md").exists())


if __name__ == "__main__":
    unittest.main()
