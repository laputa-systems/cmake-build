from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, workspace

from buildsys import benchmark
from buildsys.targets import target


class BenchmarkAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = self.enterContext(workspace())
        self.target = target("aarch64-unknown-linux-musl")
        self.generation = self.root / ".work/generations" / self.target.triple / "generation"
        self.generation.mkdir(parents=True)
        (self.generation / "usr").mkdir()
        self.active = self.generation.parent / "active"
        self.active.symlink_to("generation/usr")
        self.archive = self.generation / "artifact.tar.xz"
        self.archive.write_bytes(b"candidate archive fixture")
        self.digest = benchmark.sha256_file(self.archive)
        self.result_path = self.generation / "results.json"
        self.suites = dict.fromkeys(("basic", "parity", "network", "projects", "upstream"), "passed")
        self.write_results(self.digest, self.archive.stat().st_size, self.suites)
        self.artifact: dict[str, object] = {
            "target": {"triple": self.target.triple},
            "build": {"mode": "qualification"},
        }
        self.inspect = self.enterContext(patch.object(benchmark.package, "inspect", return_value=self.artifact))
        self.enterContext(patch.object(benchmark.platform, "system", return_value="Linux"))
        self.enterContext(patch.object(benchmark.shutil, "which", return_value=None))
        self.enterContext(patch.object(benchmark.subprocess, "run", side_effect=AssertionError("unexpected benchmark process")))

    def write_results(self, digest: str, size: int, suites: dict[str, str]) -> None:
        self.result_path.write_text(json.dumps({"archive_sha256": digest, "archive_size": size, "qualification": suites}))

    def assert_rejected(self, message: str) -> None:
        with self.assertRaises(benchmark.BenchmarkError) as caught:
            benchmark.run(self.root, self.target)
        self.assertEqual(str(caught.exception), message)

    def test_requires_a_native_host_and_an_active_generation(self) -> None:
        with patch.object(benchmark.platform, "system", return_value="Darwin"):
            self.assert_rejected("benchmarking requires a native Linux host")
        self.active.unlink()
        self.active.mkdir()
        self.assert_rejected("qualify a candidate before benchmarking")
        self.inspect.assert_not_called()

    def test_archive_digest_and_size_must_match_independently(self) -> None:
        actual_size = self.archive.stat().st_size
        for digest, size in (("previous", actual_size), (self.digest, actual_size + 1)):
            with self.subTest(digest=digest, size=size):
                self.write_results(digest, size, self.suites)
                self.assert_rejected("qualified archive digest or size does not match results")
        self.inspect.assert_not_called()

    def test_reports_invalid_archive_with_the_package_error(self) -> None:
        self.inspect.side_effect = benchmark.package.PackageError("fixture header is invalid")
        with self.assertRaises(benchmark.BenchmarkError) as caught:
            benchmark.run(self.root, self.target)
        self.assertEqual(str(caught.exception), "qualified archive is invalid: fixture header is invalid")
        self.assertIs(caught.exception.__cause__, self.inspect.side_effect)
        self.inspect.assert_called_once_with(self.archive)

    def test_requires_exact_target_build_mode_and_every_suite(self) -> None:
        message = "archive lacks qualification for the requested target"
        for changes in (
            {"target": self.target.triple},
            {"target": {"triple": "x86_64-unknown-linux-musl"}},
            {"build": "qualification"},
            {"build": {"mode": "production"}},
        ):
            with self.subTest(changes=changes):
                self.inspect.return_value = {**self.artifact, **changes}
                self.assert_rejected(message)
        self.inspect.return_value = self.artifact
        for suite in self.suites:
            with self.subTest(suite=suite):
                self.write_results(self.digest, self.archive.stat().st_size, {**self.suites, suite: ""})
                self.assert_rejected(message)

    def test_validates_the_qualified_archive_before_requiring_a_baseline(self) -> None:
        budget_path = self.root / "release-budgets.json"
        budget_path.write_text("{}")
        with (
            patch.object(benchmark.budgets, "read", return_value={}) as read,
            patch.object(benchmark.budgets, "validate_memory_source") as validate,
        ):
            self.assert_rejected("build the unmodified static-musl baseline with the upstream suite first")
        read.assert_called_once_with(budget_path)
        validate.assert_called_once_with({}, self.target.triple, self.digest, self.archive.stat().st_size)

    def test_checks_reference_output_and_the_locked_prepare_and_bootstrap_inputs(self) -> None:
        budget_path = self.root / "release-budgets.json"
        budget_path.write_text("{}")
        for name in ("sources.lock.json", "bootstrap.lock.json"):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        phases = self.root / ".work/build" / self.target.triple / "phases"
        reference = phases / "reference"
        executable = reference / "build/bin/cmake"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"reference executable fixture")
        sources = {item.name: item for item in benchmark.load_sources(self.root / "sources.lock.json")}
        lock = benchmark.load_bootstrap(self.root / "bootstrap.lock.json")
        headers = next(item for item in benchmark.bootstrap_inputs(lock, self.target.triple) if item.name == "linux-headers")
        locks = {
            "prepare": {
                "toolchain": sources["llvm-toolchain-aarch64"].sha256,
                "musl": sources["musl-source"].sha256,
                "linux-headers": headers.sha256,
                "image": "fixture-image",
            },
            "bootstrap": {
                "cmake": sources["cmake-source"].sha256,
                "ninja": sources["ninja-source"].sha256,
                "samurai": sources["samurai-source"].sha256,
                "image": "fixture-image",
            },
        }
        digests = {}
        for name, inputs in locks.items():
            directory = phases / name
            directory.mkdir()
            (directory / "output").write_text(name)
            digests[name] = self.phase_digest(directory)
            self.write_phase(directory, digests[name], inputs)
        reference_digest = self.phase_digest(reference)
        reference_inputs = {"image": "fixture-image", **digests}
        with (
            patch.object(benchmark.budgets, "read", return_value={}),
            patch.object(benchmark.budgets, "validate_memory_source"),
            patch.object(benchmark.sandbox, "image_fingerprint", return_value="fixture-image"),
        ):
            self.write_phase(reference, "previous", reference_inputs)
            self.assert_rejected("unmodified baseline output does not match its phase record")
            self.write_phase(reference, reference_digest, {**reference_inputs, "image": "previous"})
            self.assert_rejected("unmodified baseline builder image has changed")
            for name, inputs in locks.items():
                with self.subTest(phase=name):
                    directory = phases / name
                    self.write_phase(reference, reference_digest, {**reference_inputs, name: "previous"})
                    self.assert_rejected(f"unmodified baseline {name} input has changed")
                    self.write_phase(reference, reference_digest, reference_inputs)
                    self.write_phase(directory, "previous", inputs)
                    self.assert_rejected(f"unmodified baseline {name} input has changed")
                    self.write_phase(directory, digests[name], {**inputs, "image": "previous"})
                    self.assert_rejected(f"unmodified baseline {name} lock inputs have changed")
                    self.write_phase(directory, digests[name], inputs)
            self.assert_rejected("strace is required for file and process profiles")

    @staticmethod
    def phase_digest(directory: Path) -> str:
        return benchmark.tree_digest(directory, exclude={"phase.json", "state.json"})

    @staticmethod
    def write_phase(directory: Path, digest: str, inputs: dict[str, str]) -> None:
        (directory / "phase.json").write_text(json.dumps({"output_digest": digest, "inputs": inputs}))
