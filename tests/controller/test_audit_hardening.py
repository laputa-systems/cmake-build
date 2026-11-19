from __future__ import annotations

import json
import struct
import subprocess
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import workspace

from buildsys import elf
from buildsys.targets import target

PT_LOAD, PT_DYNAMIC, PT_GNU_STACK, PT_GNU_RELRO = 1, 2, 0x6474E551, 0x6474E552
DT_NULL, DT_FLAGS_1 = 0, 0x6FFFFFFB


def image(*, machine: int = 62, stack_flags: int = 6, relro: bool = True, bind_now: bool = True) -> bytes:
    kinds = [(PT_LOAD, 6), (PT_GNU_STACK, stack_flags), (PT_DYNAMIC, 6)]
    if relro:
        kinds.append((PT_GNU_RELRO, 4))
    table = 64 + 56 * len(kinds)
    dynamic = struct.pack("<qQqQ", DT_FLAGS_1 if bind_now else DT_NULL, 1, DT_NULL, 0)
    total = table + len(dynamic)
    header = b"\x7fELF" + bytes([2, 1, 1]) + bytes(9) + struct.pack("<HHIQQQIHHHHHH", 3, machine, 1, 0, 64, 0, 0, 64, 56, len(kinds), 0, 0, 0)
    headers = b"".join(
        struct.pack("<IIQQQQQQ", kind, flags, *((0, 0, 0, total, total, 4096) if kind == PT_LOAD else (table, table, table, len(dynamic), len(dynamic), 8) if kind == PT_DYNAMIC else (0,) * 6))
        for kind, flags in kinds
    )
    return header + headers + dynamic


class HardeningTests(unittest.TestCase):
    def audit(self, directory: Path, data: bytes) -> str:
        path = directory / "binary"
        path.write_bytes(data)
        with patch.object(elf, "_tool", side_effect=elf.AuditError("llvm-readelf reached")), self.assertRaises(elf.AuditError) as caught:
            elf.audit(path, target("x86_64-unknown-linux-musl"), directory)
        return str(caught.exception)

    def test_hardened_image_reaches_the_tool_based_checks(self) -> None:
        with workspace() as directory:
            self.assertEqual(self.audit(directory, image()), "llvm-readelf reached")

    def test_rejects_each_hardening_gap_before_running_tools(self) -> None:
        cases = [
            (image(machine=183), "machine is aarch64, expected x86_64"),
            (image(stack_flags=7), "executable stack"),
            (image(relro=False), "PT_GNU_RELRO"),
            (image(bind_now=False), "lazy binding"),
        ]
        with workspace() as directory:
            for data, message in cases:
                with self.subTest(message=message):
                    self.assertIn(message, self.audit(directory, data))

    def test_rejects_unreadable_images(self) -> None:
        with workspace() as directory:
            path = directory / "binary"
            path.write_bytes(b"not an elf")
            with self.assertRaisesRegex(elf.AuditError, "invalid ELF"):
                elf.audit(path, target("x86_64-unknown-linux-musl"), directory)


def static_report() -> dict[str, object]:
    return {
        "ProgramHeaders": [],
        "DynamicSection": [{"Type": "FLAGS_1", "Flags": ["PIE"]}],
        "Sections": [{"Section": {"Name": {"Name": ".comment"}}}],
    }


class ReadelfReportTests(unittest.TestCase):
    def test_static_and_musl_dynamic_pie_use_the_locked_tools(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        loader = description.musl_loader.encode("ascii") + b"\0"
        for linked in (False, True):
            with self.subTest(linked=linked), workspace() as directory:
                binary = directory / "binary"
                binary.write_bytes(b"fixture prefix" + loader + b"following section")
                tools = directory / "locked tools"
                report = static_report()
                if linked:
                    report["ProgramHeaders"] = [
                        {"ProgramHeader": {"Type": {"Name": "PT_INTERP"}, "Offset": 14, "FileSize": len(loader)}},
                    ]
                    report["DynamicSection"] = [
                        {"Type": "FLAGS_1", "Flags": ["PIE"]},
                        {"Type": "NEEDED", "Library": "libc.musl-x86_64.so.1"},
                    ]
                allowed = "openssl\nopenssl/\narchive_openssl_version\nOpenSSL_probe\ntry_init_openssl_env_vars\n"
                with patch.object(elf, "hardening_violations", return_value=[]) as hardening, \
                        patch.object(elf, "_tool", side_effect=[
                            json.dumps([report]), "clang fixture build", "", "0000 T rustls_fixture", allowed,
                        ]) as tool:
                    elf.audit(binary, description, tools)
                hardening.assert_called_once_with(binary, machine=description.elf_machine)
                self.assertEqual(tool.call_args_list, [
                    call(tools / "llvm-readelf", "-h", "-l", "-d", "-S", "--elf-output-style=JSON", binary),
                    call(tools / "llvm-readelf", "--string-dump=.comment", binary),
                    call(tools / "llvm-objdump", "-s", "-j", ".comment", binary),
                    call(tools / "llvm-nm", binary),
                    call(tools / "llvm-strings", binary),
                ])

    def test_rejects_unreadable_or_incomplete_tool_reports(self) -> None:
        description = target("aarch64-unknown-linux-musl")
        with workspace() as directory:
            binary = directory / "binary"
            for report, diagnostic in (
                ("{", f"invalid ELF report for {binary}"),
                ("[{}]", f"invalid ELF report for {binary}"),
                ("[null]", f"invalid ELF report for {binary}"),
                ("[]", "expected exactly one ELF"),
                ("[{},{}]", "expected exactly one ELF"),
            ):
                with self.subTest(report=report), patch.object(elf, "hardening_violations", return_value=[]), \
                        patch.object(elf, "_tool", return_value=report) as tool, self.assertRaises(elf.AuditError) as failure:
                    elf.audit(binary, description, directory)
                self.assertEqual(str(failure.exception), diagnostic)
                tool.assert_called_once()
            no_dynamic = static_report()
            del no_dynamic["DynamicSection"]
            with patch.object(elf, "hardening_violations", return_value=[]), \
                    patch.object(elf, "_tool", return_value=json.dumps([no_dynamic])), self.assertRaises(elf.AuditError) as failure:
                elf.audit(binary, description, directory)
            self.assertEqual(str(failure.exception), "ELF is not marked PIE")

    def test_rejects_unapproved_linkage_and_missing_provenance_reports(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        flags = {"Type": "FLAGS_1", "Flags": ["PIE"]}
        for updates, diagnostic in (
            ({"DynamicSection": [{"Type": "FLAGS_1", "Flags": ["NOW"]}]}, "ELF is not marked PIE"),
            ({"DynamicSection": [flags, {"Type": "RPATH"}]}, "ELF contains RPATH or RUNPATH"),
            ({"DynamicSection": [flags, {"Type": "RUNPATH"}]}, "ELF contains RPATH or RUNPATH"),
            ({"DynamicSection": [flags, {"Type": "NEEDED", "Library": "libfixture.so"}]}, "static PIE has dynamic dependencies"),
            ({"Sections": [{"Section": {"Name": {"Name": ".gnu.version_r"}}}]}, "ELF contains unapproved symbol versions"),
            ({"Sections": []}, "ELF lacks compiler provenance"),
        ):
            report = static_report()
            report.update(updates)
            with self.subTest(diagnostic=diagnostic), workspace() as directory, \
                    patch.object(elf, "hardening_violations", return_value=[]), \
                    patch.object(elf, "_tool", return_value=json.dumps([report])) as tool, self.assertRaises(elf.AuditError) as failure:
                elf.audit(directory / "binary", description, directory)
            self.assertEqual(str(failure.exception), diagnostic)
            tool.assert_called_once()

    def test_rejects_dynamic_pie_with_wrong_library_or_interpreter_report(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            binary = directory / "binary"
            report = static_report()
            for loader, library in (
                (description.musl_loader, "libfixture.so"),
                ("/lib/other-loader.so", "libc.musl-x86_64.so.1"),
                (description.musl_loader + "X", "libc.musl-x86_64.so.1"),
            ):
                contents = loader.encode("ascii") + b"\0"
                binary.write_bytes(contents)
                report["ProgramHeaders"] = [
                    {"ProgramHeader": {"Type": {"Name": "PT_INTERP"}, "Offset": 0, "FileSize": len(contents)}},
                ]
                report["DynamicSection"] = [
                    {"Type": "FLAGS_1", "Flags": ["PIE"]}, {"Type": "NEEDED", "Library": library},
                ]
                with self.subTest(loader=loader, library=library), patch.object(elf, "hardening_violations", return_value=[]), \
                        patch.object(elf, "_tool", return_value=json.dumps([report])), self.assertRaises(elf.AuditError) as failure:
                    elf.audit(binary, description, directory)
                self.assertEqual(str(failure.exception), "ELF uses an unapproved interpreter or dynamic dependency")

    def test_checks_compiler_symbols_runtime_strings_and_host_paths(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        report = json.dumps([static_report()])
        cases = [
            ("GCC: fixture", "", "", "ELF contains GCC compiler provenance"),
            ("clang fixture", "0000 T SSL_fixture", "", "ELF contains OpenSSL API symbols"),
            ("clang fixture", "", "libstdc++.so", "ELF contains an unapproved runtime or OpenSSL library"),
            ("clang fixture", "", "GLIBC_2.30", "ELF contains an unapproved runtime or OpenSSL library"),
            ("clang fixture", "", "linked OpenSSL provider", "ELF contains unapproved OpenSSL text"),
            ("clang fixture", "", "/src/.work/build/file.c", "ELF contains a build-host path"),
            ("clang fixture", "", "/home/fixture/build/file.c", "ELF contains a build-host path"),
            ("clang fixture", "", ".work/build/file.c", "ELF contains a build-host path"),
        ]
        with workspace() as directory:
            for comment, symbols, strings, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic), patch.object(elf, "hardening_violations", return_value=[]), \
                        patch.object(elf, "_tool", side_effect=[report, comment, "", symbols, strings]), \
                        self.assertRaises(elf.AuditError) as failure:
                    elf.audit(directory / "binary", description, directory)
                self.assertEqual(str(failure.exception), diagnostic)

    def test_reports_all_hardening_diagnostics_before_invoking_tools(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        binary = Path("/fixture/binary")
        with patch.object(elf, "hardening_violations", return_value=["first gap", "second gap"]), \
                patch.object(elf, "_tool") as tool, self.assertRaises(elf.AuditError) as failure:
            elf.audit(binary, description, Path("/locked/tools"))
        self.assertEqual(str(failure.exception), "ELF hardening: first gap; second gap")
        tool.assert_not_called()

    def test_tool_preserves_arguments_stdout_and_stderr_diagnostics(self) -> None:
        tool = Path("/locked tools/llvm-readelf")
        artifact = Path("/fixture data/binary")
        command = [str(tool), "-h", str(artifact)]
        with patch.object(subprocess, "run", side_effect=[
            subprocess.CompletedProcess(command, 0, stdout="headers", stderr=""),
            subprocess.CompletedProcess(command, 7, stdout="", stderr="  invalid report\n"),
        ]) as run:
            self.assertEqual(elf._tool(tool, "-h", artifact), "headers")
            with self.assertRaises(elf.AuditError) as failure:
                elf._tool(tool, "-h", artifact)
        self.assertEqual(str(failure.exception), "llvm-readelf failed (7): invalid report")
        expected = call(command, text=True, capture_output=True, check=False)
        self.assertEqual(run.call_args_list, [expected, expected])


if __name__ == "__main__":
    unittest.main()
