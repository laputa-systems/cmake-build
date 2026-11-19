from __future__ import annotations

import os
import re
import shlex
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import ROOT, archive, workspace

from buildsys import bootstrap
from buildsys.targets import target


class BootstrapTests(unittest.TestCase):
    def test_rejects_wrong_or_missing_bootstrap_cmake_version(self) -> None:
        for output, observed in (("cmake version 1.0\n", "cmake version 1.0"), ("", "missing")):
            diagnostic = f"bootstrap CMake version {observed!r} != '4.3.4'"
            with (
                self.subTest(output=output),
                workspace() as directory,
                patch.object(bootstrap, "_run", return_value=output),
                patch.object(bootstrap, "_source") as source,
                self.assertRaisesRegex(bootstrap.BootstrapError, f"^{re.escape(diagnostic)}$"),
            ):
                bootstrap.build(
                    cmake_archive=Path("source"), samurai_archive=Path("samurai"), ninja_archive=Path("ninja"),
                    directory=directory, tc=directory, sysroot=directory, target=target("x86_64-unknown-linux-musl"),
                    bootstrap_version="4.3.4",
                )
            source.assert_not_called()

    def test_stages_sources_builds_samurai_and_configures_ninja(self) -> None:
        for cpu_count, jobs in ((3, 3), (None, 1)):
            with self.subTest(cpu_count=cpu_count):
                self._verify_stage(cpu_count, jobs)

    def _verify_stage(self, cpu_count: int | None, jobs: int) -> None:
        with workspace() as root:
            directory = root / "bootstrap"
            directory.mkdir()
            cmake = archive(root / "cmake.tar.gz", [("cmake-release/version", b"cmake", None)])
            samurai = archive(root / "samurai.tar.gz", [("samurai-release/version", b"samurai", None)])
            ninja = archive(root / "ninja.tar.gz", [("ninja-release/version", b"ninja", None)])
            tc = root / "fixture tools"
            sysroot = root / "fixture sysroot"
            description = target("aarch64-unknown-linux-musl")
            with (
                patch.dict(os.environ, {"BOOTSTRAP_FIXTURE": "inherited"}, clear=True),
                patch.object(bootstrap.os, "process_cpu_count", return_value=cpu_count),
                patch.object(bootstrap, "run_process",
                             side_effect=["cmake version 4.3.4\nsecond line\n", "", "", ""]) as process,
            ):
                bootstrap.build(
                    cmake_archive=cmake, samurai_archive=samurai, ninja_archive=ninja,
                    directory=directory, tc=tc, sysroot=sysroot, target=description,
                    bootstrap_version="4.3.4",
                )
            samurai_source = directory / "samurai/samurai-release"
            ninja_build = directory / "ninja-build"
            toolchain = directory / "toolchain.cmake"
            flags = [
                "--target=aarch64-unknown-linux-musl", f"--sysroot={sysroot}", "-fuse-ld=lld",
                "--rtlib=compiler-rt", "--unwindlib=libunwind",
            ]
            env = {
                "BOOTSTRAP_FIXTURE": "inherited",
                "CC": str(tc / "bin/clang"),
                "CXX": str(tc / "bin/clang++"),
                "AR": str(tc / "bin/llvm-ar"),
                "RANLIB": str(tc / "bin/llvm-ranlib"),
                "NM": str(tc / "bin/llvm-nm"),
                "STRIP": str(tc / "bin/llvm-strip"),
                "OBJCOPY": str(tc / "bin/llvm-objcopy"),
                "READELF": str(tc / "bin/llvm-readelf"),
                "TARGET": description.triple,
                "CFLAGS": shlex.join(flags),
                "CXXFLAGS": shlex.join([*flags, "-stdlib=libc++"]),
                "LDFLAGS": shlex.join(flags),
            }
            samu = samurai_source / "samu"
            self.assertEqual(process.call_args_list, [
                call(["/usr/bin/cmake", "--version"], cwd=directory, env=env),
                call(["make", f"-j{jobs}", f"CC={shlex.join([str(tc / 'bin/clang'), *flags])}"],
                     cwd=samurai_source, env=env),
                call([
                    "/usr/bin/cmake", "-S", str(directory / "ninja-source/ninja-release"), "-B", str(ninja_build),
                    "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={samu}", f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
                    "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
                ], cwd=directory, env=env),
                call([str(samu), "-C", str(ninja_build), f"-j{jobs}"], cwd=directory, env=env),
            ])
            self.assertEqual({path.name for path in directory.iterdir()},
                             {"samurai", "source", "toolchain.cmake", "ninja-source"})
            self.assertEqual((samurai_source / "version").read_bytes(), b"samurai")
            self.assertEqual((directory / "source/cmake-release/version").read_bytes(), b"cmake")
            self.assertEqual((directory / "ninja-source/ninja-release/version").read_bytes(), b"ninja")
            hardening = ["-fstack-protector-strong", "-fstack-clash-protection"]
            definitions = {
                "CMAKE_C_COMPILER": tc / "bin/clang",
                "CMAKE_CXX_COMPILER": tc / "bin/clang++",
                "CMAKE_AR": tc / "bin/llvm-ar",
                "CMAKE_RANLIB": tc / "bin/llvm-ranlib",
                "CMAKE_NM": tc / "bin/llvm-nm",
                "CMAKE_STRIP": tc / "bin/llvm-strip",
                "CMAKE_OBJCOPY": tc / "bin/llvm-objcopy",
                "CMAKE_READELF": tc / "bin/llvm-readelf",
                "CMAKE_LINKER": tc / "bin/ld.lld",
                "CMAKE_SYSROOT": sysroot,
                "CMAKE_C_FLAGS_INIT": shlex.join([*flags, *hardening]),
                "CMAKE_CXX_FLAGS_INIT": shlex.join([*flags, "-stdlib=libc++", *hardening]),
                "CMAKE_EXE_LINKER_FLAGS_INIT": "-static-pie -Wl,-z,relro,-z,now,-z,noexecstack",
            }
            self.assertEqual(toolchain.read_text(), "".join(f'set({key} "{value}")\n'
                                                            for key, value in definitions.items()))

    def test_rejects_a_source_archive_without_one_wrapping_directory(self) -> None:
        with workspace() as root:
            sources = (
                archive(root / "file.tar.gz", [("README", b"fixture", None)]),
                archive(root / "two.tar.gz", [("one/file", b"x", None), ("two/file", b"y", None)]),
            )
            for source in sources:
                with self.subTest(source=source.name), self.assertRaisesRegex(
                    bootstrap.BootstrapError, "expected one source directory$",
                ):
                    bootstrap._source(source, root / source.stem)

    def test_configures_cmake_and_the_native_toolchain_check(self) -> None:
        with workspace() as root:
            staged = root / "bootstrap"
            source = staged / "source/cmake-release"
            source.mkdir(parents=True)
            config = root / "configure"
            tc = root / "toolchain"
            description = target("x86_64-unknown-linux-musl")
            with (
                patch.dict(os.environ, {"BOOTSTRAP_FIXTURE": "inherited"}, clear=True),
                patch.object(bootstrap, "run_process", return_value="") as process,
            ):
                bootstrap.configure(staged, config, tc, description)
            environment = process.call_args_list[0].kwargs["env"]
            self.assertEqual(environment["CC"], str(tc / "bin/clang"))
            self.assertEqual(environment["BOOTSTRAP_FIXTURE"], "inherited")
            self.assertEqual(environment["TARGET"], description.triple)
            toolchain = f"-DCMAKE_TOOLCHAIN_FILE={staged / 'toolchain.cmake'}"
            self.assertEqual(process.call_args_list, [
                call([
                    "/usr/bin/cmake", "-S", str(source), "-B", str(config), "-G", "Ninja",
                    f"-DCMAKE_MAKE_PROGRAM={staged / 'ninja-build/ninja'}", toolchain, "-DCMAKE_BUILD_TYPE=Release",
                    "-DCMAKE_USE_OPENSSL=OFF", "-DBUILD_CursesDialog=OFF", "-DBUILD_QtDialog=OFF",
                    "-DCMAKE_USE_SYSTEM_LIBRARIES=OFF", "-DCMake_ENABLE_DEBUGGER=ON",
                ], cwd=config, env=environment),
                call(["/usr/bin/cmake", "-S", str(ROOT / "tests/fixtures/native"), "-B", str(config / "native-check"),
                      toolchain], cwd=config, env=environment),
            ])


if __name__ == "__main__":
    unittest.main()
