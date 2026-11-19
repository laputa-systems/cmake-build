from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import call, patch

from helpers import workspace

from buildsys import elf
from buildsys.targets import target

HEADER = "reference\textracted\tsymbol\n"


def evidence(member: str) -> str:
    return f"main.o\t{member}\tentry\n"


class ArchiveEvidenceTests(unittest.TestCase):
    def test_checks_relative_and_absolute_archives_and_deduplicates_members(self) -> None:
        with workspace() as directory:
            extract = directory / "link.extract"
            relative = "lib example.a"
            absolute = directory / "libextra.a"
            extract.write_text(HEADER + (evidence(f"{relative}(one.o)").rstrip("\n") + "\tentry alias\n") * 2 + evidence(f"{relative}(two.o)") + evidence(f"{absolute}(extra.o)"))
            reports = {
                directory / relative: "Archive inspection\nFile: lib example.a(one.o)\nclang\nFile: lib example.a(two.o)\nclang\nFile: lib example.a(unselected.o)\nGCC: unused\n",
                absolute: "File: libextra.a(extra.o)\nclang\n",
            }

            def read_report(tool: Path, option: str, section: str, archive: Path) -> str:
                self.assertEqual((tool, option, section), (directory / "llvm-readelf", "-p", ".comment"))
                return reports[archive]

            with patch.object(elf, "_tool", side_effect=read_report) as readelf:
                elf.audit_archives(extract, directory, directory)
            self.assertCountEqual(readelf.call_args_list, [call(directory / "llvm-readelf", "-p", ".comment", archive) for archive in reports])

    def test_rejects_missing_or_malformed_member_evidence_before_inspection(self) -> None:
        cases = (
            ("", "invalid linker extraction evidence"),
            ("symbol\textracted\treference\n", "invalid linker extraction evidence"),
            (HEADER, "linker extracted no archive members"),
            (HEADER + "main.o\n", "invalid extracted archive member"),
            (HEADER + evidence("ordinary.o"), "invalid extracted archive member"),
        )
        with workspace() as directory:
            extract = directory / "link.extract"
            for content, message in cases:
                with self.subTest(content=content):
                    extract.write_text(content)
                    with patch.object(elf, "_tool") as readelf, self.assertRaisesRegex(elf.AuditError, f"^{re.escape(message)}$"):
                        elf.audit_archives(extract, directory, directory)
                    readelf.assert_not_called()

    def test_rejects_failed_archive_provenance_checks(self) -> None:
        cases = (
            ("libssl.a", "", "unapproved linked archive"),
            ("libexample.a", "File: ordinary.o\nclang\n", "invalid archive member report"),
            ("libexample.a", "File: libexample.a(one.o)\nGCC: fixture\n", "GCC compiler provenance"),
            ("libexample.a", "File: libexample.a(two.o)\nclang\n", "archive members missing from inspection"),
        )
        with workspace() as directory:
            extract = directory / "link.extract"
            for archive, report, message in cases:
                with self.subTest(message=message):
                    extract.write_text(HEADER + evidence(f"{archive}(one.o)"))
                    with patch.object(elf, "_tool", return_value=report) as readelf, self.assertRaisesRegex(elf.AuditError, message):
                        elf.audit_archives(extract, directory, directory)
                    if archive == "libssl.a":
                        readelf.assert_not_called()
                    else:
                        readelf.assert_called_once_with(directory / "llvm-readelf", "-p", ".comment", directory / archive)


class StripTests(unittest.TestCase):
    def test_strips_to_separate_destination_and_audits_result(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            binary = directory / "original"
            destination = directory / "stripped"
            binary.write_bytes(b"original")

            def strip(tool: Path, *arguments: str | Path) -> str:
                self.assertEqual(tool, directory / "llvm-strip")
                self.assertEqual(arguments, ("--strip-debug", "-o", destination, binary))
                destination.write_bytes(b"stripped")
                return ""

            with patch.object(elf, "_tool", side_effect=strip), patch.object(elf, "audit") as audit:
                elf.strip_debug(binary, destination, description, directory)
            audit.assert_called_once_with(destination, description, directory)
            self.assertEqual(destination.read_bytes(), b"stripped")
            self.assertEqual(binary.read_bytes(), b"original")

    def test_rejects_alias_and_removes_failed_output(self) -> None:
        description = target("x86_64-unknown-linux-musl")
        with workspace() as directory:
            binary = directory / "original"
            binary.write_bytes(b"original")
            alias = directory / "alias"
            alias.symlink_to(binary)
            with patch.object(elf, "_tool") as strip, self.assertRaisesRegex(elf.AuditError, "^stripping requires a separate destination$"):
                elf.strip_debug(binary, alias, description, directory)
            strip.assert_not_called()
            self.assertEqual(alias.read_bytes(), b"original")
            destination = directory / "stripped"
            for error in (elf.AuditError("audit failed"), OSError("unreadable output")):
                with self.subTest(error=error):
                    destination.write_bytes(b"unfinished")
                    with patch.object(elf, "_tool"), patch.object(elf, "audit", side_effect=error), self.assertRaises(type(error)) as caught:
                        elf.strip_debug(binary, destination, description, directory)
                    self.assertIs(caught.exception, error)
                    self.assertFalse(destination.exists())
                    self.assertEqual(binary.read_bytes(), b"original")
            error = elf.AuditError("strip failed before writing output")
            with patch.object(elf, "_tool", side_effect=error), patch.object(elf, "audit") as audit, self.assertRaises(elf.AuditError) as caught:
                elf.strip_debug(binary, destination, description, directory)
            self.assertIs(caught.exception, error)
            audit.assert_not_called()
            self.assertFalse(destination.exists())


class PrelinkTests(unittest.TestCase):
    def test_probe_is_isolated_and_final_link_must_repeat_audited_members(self) -> None:
        cases = (
            (0, 0, "libexample.a(one.o)", 0, None),
            (19, 0, "libexample.a(one.o)", 19, None),
            (0, 23, "libexample.a(one.o)", 23, None),
            (0, 0, "libexample.a(two.o)", None, "final link selected different archive members from the audited probe"),
            (0, 0, "libexample.a(three.o)", None, "final link selected different archive members from the audited probe"),
            (0, 0, "", None, "invalid linker extraction evidence"),
            (0, 0, None, None, "missing"),
        )
        for probe_exit, final_exit, final_member, exit_code, message in cases:
            with self.subTest(probe_exit=probe_exit, final_exit=final_exit, final_member=final_member), workspace() as directory:
                self.check_link(directory, probe_exit, final_exit, final_member, exit_code, message)

    def check_link(
        self,
        directory: Path,
        probe_exit: int,
        final_exit: int,
        final_member: str | None,
        exit_code: int | None,
        message: str | None,
    ) -> None:
        output = directory / "final"
        extract = directory / "final=link.extract"
        command = ["ld.lld", "-o", str(output), "-Map", "=", str(directory / "final.map"), f"--why-extract={extract}", f"--dependency-file={directory / 'final.d'}", "main.o"]
        original_command = command.copy()
        scratch_dirs: list[Path] = []

        def execute(arguments: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
            self.assertFalse(check)
            if not scratch_dirs:
                scratch = Path(arguments[2]).parent
                scratch_dirs.append(scratch)
                self.assertEqual(scratch.parent, directory)
                self.assertTrue(scratch.name.startswith("link-audit-"))
                self.assertEqual(arguments, ["ld.lld", "-o", str(scratch / "cmake"), "-Map", "=", str(scratch / "cmake.map"), f"--why-extract={scratch / 'cmake.extract'}", f"--dependency-file={scratch / 'link.d'}", "main.o"])
                (scratch / "cmake.extract").write_text(HEADER + evidence("libexample.a(one.o)"))
                self.assertFalse(output.exists())
                return subprocess.CompletedProcess(arguments, probe_exit)
            self.assertEqual(arguments, original_command)
            if final_member in ("libexample.a(one.o)", "libexample.a(two.o)", ""):
                output.write_bytes(b"final output")
            if final_member is not None:
                extract.write_text(HEADER + evidence(final_member) if final_member else "")
            return subprocess.CompletedProcess(arguments, final_exit)

        with patch.object(elf.Path, "cwd", return_value=directory), patch.object(elf.subprocess, "run", side_effect=execute) as run, patch.object(elf, "audit_archives") as audit:
            if message == "missing":
                with self.assertRaises(FileNotFoundError) as caught:
                    elf.prelink(directory, command)
                self.assertEqual(caught.exception.filename, str(extract))
            elif message:
                with self.assertRaisesRegex(elf.AuditError, f"^{re.escape(message)}$"):
                    elf.prelink(directory, command)
            else:
                self.assertEqual(elf.prelink(directory, command), exit_code)
        self.assertEqual(command, original_command)
        self.assertEqual(run.call_count, 1 if probe_exit else 2)
        if probe_exit:
            audit.assert_not_called()
        else:
            audit.assert_called_once_with(scratch_dirs[0] / "cmake.extract", directory, directory)
        self.assertFalse(scratch_dirs[0].exists())
        if message or probe_exit:
            self.assertFalse(output.exists())
        else:
            self.assertEqual(output.read_bytes(), b"final output")

    def test_incomplete_command_is_rejected_before_starting_linker(self) -> None:
        cases = (
            ["ld.lld"],
            ["ld.lld", "-o"],
            ["ld.lld", "-o", "final", "-Map"],
            ["ld.lld", "-o", "final", "-Map", "=", "final.map"],
        )
        with workspace() as directory, patch.object(elf.Path, "cwd", return_value=directory), patch.object(elf.subprocess, "run") as run:
            for command in cases:
                with self.subTest(command=command), self.assertRaisesRegex(elf.AuditError, "^link command lacks output or extraction evidence$"):
                    elf.prelink(directory, command)
            run.assert_not_called()
