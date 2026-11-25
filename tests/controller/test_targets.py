from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from buildsys import targets

X86 = "x86_64-unknown-linux-musl"
ARM = "aarch64-unknown-linux-musl"
DARWIN = "aarch64-apple-darwin"
SUPPORTED = f"(supported: {[DARWIN, ARM, X86]})"


class TargetContractTests(unittest.TestCase):
    def test_linux_targets_preserve_architecture_and_cpu_baseline(self) -> None:
        cases = (
            (X86, ("x86_64", "x86_64", "linux/amd64", "/lib/ld-musl-x86_64.so.1", 62, "x86-64")),
            (ARM, ("aarch64", "aarch64", "linux/arm64", "/lib/ld-musl-aarch64.so.1", 183, "armv8-a")),
        )
        for triple, fields in cases:
            with self.subTest(triple=triple):
                description = targets.target(triple)
                self.assertEqual(description.triple, triple)
                self.assertEqual(targets._adopt(targets.shared.target_for_triple(triple)), description)
                self.assertEqual(description.family, "linux-musl")
                self.assertEqual(description.executable_format, "elf")
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

    def test_darwin_target_describes_apple_silicon_macho(self) -> None:
        description = targets.target(DARWIN)
        self.assertEqual(description.triple, DARWIN)
        self.assertEqual(description.machine, "arm64")
        self.assertEqual(description.family, "macos")
        self.assertEqual(description.executable_format, "mach-o")
        self.assertEqual(description.cpu_baseline, "apple-m1")
        self.assertEqual(description.cpu_baseline_cflag, "-mcpu=apple-m1")
        self.assertEqual(description.deployment_target, "27.0")
        self.assertTrue(description.is_macos)
        for field, empty in (("alpine_arch", ""), ("docker_platform", ""),
                              ("musl_loader", ""), ("elf_machine", 0)):
            self.assertEqual(getattr(description, field), empty)
        self.assertFalse(targets.target(X86).is_macos)

    def test_target_rejects_unsupported_triples_with_the_supported_list(self) -> None:
        for triple in ("riscv64-unknown-linux-musl", "x86_64-apple-darwin"):
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

    def test_native_target_matches_the_running_host(self) -> None:
        cases = (
            ("Darwin", "arm64", DARWIN),
            ("Darwin", "aarch64", DARWIN),
            ("Linux", "x86_64", X86),
            ("Linux", "amd64", X86),
            ("Linux", "aarch64", ARM),
            ("Linux", "arm64", ARM),
        )
        for system, machine, triple in cases:
            with (
                self.subTest(system=system, machine=machine),
                patch.object(targets.shared.platform, "system", return_value=system),
                patch.object(targets.shared.platform, "machine", return_value=machine),
            ):
                self.assertEqual(targets.native_target(), targets.target(triple))

        with (
            patch.object(targets.shared.platform, "system", return_value="Linux"),
            patch.object(targets.shared.platform, "machine", return_value="riscv64"),
            self.assertRaises(targets.UnsupportedTargetError) as caught,
        ):
            targets.native_target()
        self.assertIn("no target for host Linux riscv64", str(caught.exception))

        with (
            patch.object(targets.shared.platform, "system", return_value="Darwin"),
            patch.object(targets.shared.platform, "machine", return_value="x86_64"),
            self.assertRaises(targets.UnsupportedTargetError),
        ):
            targets.native_target()


if __name__ == "__main__":
    unittest.main()
