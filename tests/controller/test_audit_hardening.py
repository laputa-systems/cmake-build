from __future__ import annotations

import struct
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
