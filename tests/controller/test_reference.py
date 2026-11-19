from __future__ import annotations

import os
import unittest
from unittest.mock import call, patch

from helpers import workspace

from buildsys import reference
from buildsys.targets import target


class ReferenceBuildTests(unittest.TestCase):
    def test_reference_build_uses_the_unmodified_source_and_locked_toolchain(self) -> None:
        description = target("aarch64-unknown-linux-musl")
        for cpu_count, jobs in ((6, 6), (None, 1)):
            with self.subTest(cpu_count=cpu_count), workspace() as directory:
                bootstrap = directory / "bootstrap"
                source = bootstrap / "source/cmake-release"
                source.mkdir(parents=True)
                (source / "CMakeLists.txt").write_bytes(b"upstream source")
                (source / "alias.txt").symlink_to("CMakeLists.txt")
                prepared = directory / "prepared"
                toolchain = prepared / "toolchain"
                output = directory / "reference output"
                output.mkdir()
                build_tree = output / "build"
                ninja = bootstrap / "ninja-build/ninja"
                inherited = {
                    "PATH": "/host/bin", "CC": "/host/cc", "REFERENCE_FIXTURE": "retained",
                    "CFLAGS": "host-cflags", "CXXFLAGS": "host-cxxflags", "LDFLAGS": "host-ldflags",
                }
                environment = {
                    "PATH": "/host/bin", "REFERENCE_FIXTURE": "retained",
                    "CC": str(toolchain / "bin/clang"), "CXX": str(toolchain / "bin/clang++"),
                    "AR": str(toolchain / "bin/llvm-ar"), "RANLIB": str(toolchain / "bin/llvm-ranlib"),
                    "NM": str(toolchain / "bin/llvm-nm"), "STRIP": str(toolchain / "bin/llvm-strip"),
                    "OBJCOPY": str(toolchain / "bin/llvm-objcopy"), "READELF": str(toolchain / "bin/llvm-readelf"),
                    "TARGET": description.triple,
                }
                with patch.dict(os.environ, inherited, clear=True), \
                        patch.object(os, "process_cpu_count", return_value=cpu_count), \
                        patch.object(reference, "_run", side_effect=["", "", "cmake version 4.4.5\n\nfixture\n"]) as run:
                    reference.build(
                        bootstrap=bootstrap, prepared=prepared, directory=output, target=description, version="4.4.5",
                    )

                copied = output / "source"
                self.assertEqual((copied / "CMakeLists.txt").read_bytes(), b"upstream source")
                self.assertEqual((copied / "alias.txt").readlink().as_posix(), "CMakeLists.txt")
                self.assertEqual((source / "CMakeLists.txt").read_bytes(), b"upstream source")
                self.assertEqual(run.call_args_list, [
                    call([
                        "/usr/bin/cmake", "-S", str(copied), "-B", str(build_tree), "-G", "Ninja",
                        f"-DCMAKE_MAKE_PROGRAM={ninja}",
                        f"-DCMAKE_TOOLCHAIN_FILE={bootstrap / 'toolchain.cmake'}",
                        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_USE_OPENSSL=OFF", "-DBUILD_CursesDialog=OFF",
                        "-DBUILD_QtDialog=OFF", "-DCMAKE_USE_SYSTEM_LIBRARIES=OFF", "-DCMake_ENABLE_DEBUGGER=ON",
                    ], cwd=output, env=environment),
                    call([str(ninja), "-C", str(build_tree), f"-j{jobs}"], cwd=output, env=environment),
                    call([str(build_tree / "bin/cmake"), "--version"], cwd=output, env=environment),
                ])

    def test_rejects_invalid_source_layout_before_running_tools(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory, patch.object(reference, "_run") as run:
            bootstrap = directory / "bootstrap"
            source = bootstrap / "source"
            source.mkdir(parents=True)
            (source / "plain-file").touch()
            ambiguous = directory / "ambiguous"
            (ambiguous / "source/first").mkdir(parents=True)
            (ambiguous / "source/second").mkdir()
            empty = directory / "empty"
            (empty / "source").mkdir(parents=True)
            for invalid in (bootstrap, ambiguous, empty):
                with self.subTest(layout=invalid.name), self.assertRaisesRegex(
                    reference.ReferenceError, "^reference source has an invalid layout$",
                ):
                    reference.build(
                        bootstrap=invalid, prepared=directory / "prepared",
                        directory=directory / "output", target=description, version="4.4.5",
                    )
            run.assert_not_called()
            self.assertFalse((directory / "output").exists())

    def test_requires_the_exact_reported_version(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            bootstrap = directory / "bootstrap"
            (bootstrap / "source/cmake-release").mkdir(parents=True)
            for name, reported in (("missing", ""), ("wrong", "cmake version 4.4.4\n")):
                with self.subTest(name=name), patch.object(reference, "_run", side_effect=["", "", reported]), \
                        self.assertRaisesRegex(reference.ReferenceError, r"^unmodified reference does not report CMake 4\.4\.5$"):
                    reference.build(
                        bootstrap=bootstrap, prepared=directory / "prepared",
                        directory=directory / name, target=description, version="4.4.5",
                    )


if __name__ == "__main__":
    unittest.main()
