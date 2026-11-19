from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from buildsys import targets

X86 = "x86_64-unknown-linux-musl"
ARM = "aarch64-unknown-linux-musl"
SUPPORTED = f"(supported: {[ARM, X86]})"


class TargetContractTests(unittest.TestCase):
    def test_linux_targets_preserve_architecture_and_cpu_baseline(self) -> None:
        cases = (
            (X86, ("x86_64", "x86_64", "linux/amd64", "/lib/ld-musl-x86_64.so.1", 62, "x86-64")),
            (ARM, ("aarch64", "aarch64", "linux/arm64", "/lib/ld-musl-aarch64.so.1", 183, "armv8-a")),
        )
        self.assertEqual(set(targets.TARGETS), {X86, ARM})
        for triple, fields in cases:
            with self.subTest(triple=triple):
                description = targets.target(triple)
                self.assertEqual(description.triple, triple)
                self.assertEqual(targets._adopt(targets.shared.target_for_triple(triple)), description)
                self.assertEqual(
                    (
                        description.machine,
                        description.alpine_arch,
                        description.docker_platform,
                        description.musl_loader,
                        description.elf_machine,
                        description.cpu_baseline,
                    ),
                    fields,
                )

    def test_target_rejects_unsupported_triples_with_the_supported_list(self) -> None:
        for triple in ("aarch64-apple-darwin", "riscv64-unknown-linux-musl"):
            with self.subTest(triple=triple), self.assertRaises(targets.UnsupportedTargetError) as caught:
                targets.target(triple)
            self.assertEqual(str(caught.exception), f"target not implemented: {triple} {SUPPORTED}")

    def test_rejects_incomplete_shared_target_descriptions(self) -> None:
        description = targets.shared.target_for_triple(ARM)
        cases = (
            replace(description, triple="riscv64-unknown-linux-musl"),
            replace(description, docker_platform=None),
            replace(description, alpine_arch=None),
            replace(description, musl_loader=None),
            replace(description, elf_machine=None),
        )
        for item in cases:
            with self.subTest(item=item), self.assertRaises(targets.UnsupportedTargetError) as caught:
                targets._adopt(item)
            self.assertEqual(str(caught.exception), f"target not implemented: {item.triple} {SUPPORTED}")

    def test_native_build_uses_linux_target_for_each_supported_machine(self) -> None:
        for machine, triple in (("x86_64", X86), ("amd64", X86), ("aarch64", ARM), ("arm64", ARM)):
            with (
                self.subTest(machine=machine),
                patch.object(targets.platform, "system", return_value="Darwin"),
                patch.object(targets.platform, "machine", return_value=machine),
            ):
                self.assertEqual(targets.native_target(), targets.target(triple))

        with (
            patch.object(targets.platform, "machine", return_value="riscv64"),
            self.assertRaises(targets.UnsupportedTargetError) as caught,
        ):
            targets.native_target()
        self.assertIn("no target for host Linux riscv64", str(caught.exception))
