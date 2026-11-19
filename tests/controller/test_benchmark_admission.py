from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from helpers import ROOT, workspace

from buildsys import benchmark
from buildsys.targets import target


class BenchmarkWorkspace(unittest.TestCase):
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
        self.which = self.enterContext(patch.object(benchmark.shutil, "which", return_value=None))
        self.local_process = self.enterContext(patch.object(benchmark.subprocess, "run", side_effect=AssertionError("unexpected benchmark process")))

    def write_results(self, digest: str, size: int, suites: dict[str, str]) -> None:
        self.result_path.write_text(json.dumps({"archive_sha256": digest, "archive_size": size, "qualification": suites}))

    def assert_rejected(self, message: str) -> None:
        with self.assertRaises(benchmark.BenchmarkError) as caught:
            benchmark.run(self.root, self.target)
        self.assertEqual(str(caught.exception), message)

    def prepare_reference(self) -> None:
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
        self.phases = phases
        self.reference = reference
        self.reference_digest = reference_digest
        self.reference_inputs = reference_inputs
        self.locks = locks
        self.digests = digests
        self.budget_path = budget_path
        self.budgets = self.enterContext(patch.object(benchmark.budgets, "read", return_value={}))
        self.enterContext(patch.object(benchmark.budgets, "validate_memory_source"))
        self.enterContext(patch.object(benchmark.sandbox, "image_fingerprint", return_value="fixture-image"))
        self.write_phase(reference, reference_digest, reference_inputs)

    @staticmethod
    def phase_digest(directory: Path) -> str:
        return benchmark.tree_digest(directory, exclude={"phase.json", "state.json"})

    @staticmethod
    def write_phase(directory: Path, digest: str, inputs: dict[str, str]) -> None:
        (directory / "phase.json").write_text(json.dumps({"output_digest": digest, "inputs": inputs}))


class BenchmarkAdmissionTests(BenchmarkWorkspace):
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
        self.prepare_reference()
        reference, reference_digest, reference_inputs = self.reference, self.reference_digest, self.reference_inputs
        self.write_phase(reference, "previous", reference_inputs)
        self.assert_rejected("unmodified baseline output does not match its phase record")
        self.write_phase(reference, reference_digest, {**reference_inputs, "image": "previous"})
        self.assert_rejected("unmodified baseline builder image has changed")
        for name, inputs in self.locks.items():
            with self.subTest(phase=name):
                directory = self.phases / name
                self.write_phase(reference, reference_digest, {**reference_inputs, name: "previous"})
                self.assert_rejected(f"unmodified baseline {name} input has changed")
                self.write_phase(reference, reference_digest, reference_inputs)
                self.write_phase(directory, "previous", inputs)
                self.assert_rejected(f"unmodified baseline {name} input has changed")
                self.write_phase(directory, self.digests[name], {**inputs, "image": "previous"})
                self.assert_rejected(f"unmodified baseline {name} lock inputs have changed")
                self.write_phase(directory, self.digests[name], inputs)
        self.assert_rejected("strace is required for file and process profiles")


class BenchmarkExecutionTests(BenchmarkWorkspace):
    def setUp(self) -> None:
        super().setUp()
        self.prepare_reference()
        self.tracer = self.root / "strace"
        self.loader = self.root / "trace-loader"
        self.library = self.root / "trace-library"
        self.cpuinfo: Path = self.root / "cpuinfo"
        self.official_archive = self.root / "official.tar.xz"
        self.official_archive.write_bytes(b"official archive bytes")
        self.official_directory = True
        self.report = self.root / "docs/performance.md"
        self.provenance = (
            self.root / "tests/benchmark/run.py",
            self.root / "buildsys/benchmark_process.py",
        )
        for source in (*self.provenance, self.report, self.root / "buildsys/qualify.py"):
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(f"original {source.name}\n")
        for tool in (self.tracer, self.loader, self.library):
            tool.write_bytes(tool.name.encode())
        self.cpuinfo.write_text("processor: 0\nHardware: fixture cpu\n")

        self.which.return_value = str(self.tracer)
        self.local_process.side_effect = self.process_response
        self.enterContext(patch.object(benchmark, "Path", side_effect=self.owned_path))
        self.enterContext(patch.object(benchmark.platform, "platform", return_value="fixture host"))
        self.cache = Mock()
        self.cache.require.side_effect = lambda item: self.official_archive if item.name.startswith("cmake-reference-") else self.archive
        self.enterContext(patch.object(benchmark, "Cache", return_value=self.cache))
        self.phase_cache = Mock()
        self.phase_cache.run.side_effect = lambda name, *_: SimpleNamespace(directory=self.phases / name)
        self.phase_cache_factory = self.enterContext(patch.object(benchmark, "PhaseCache", return_value=self.phase_cache))
        self.enterContext(patch.object(benchmark, "safe_extract", side_effect=self.extract_fixture))
        self.enterContext(patch.object(benchmark.stage, "stage", side_effect=self.stage_fixture))
        self.enterContext(patch.object(benchmark.sandbox, "image_tag", return_value="fixture-image"))
        self.copy_runtime = self.enterContext(patch.object(benchmark.sandbox, "copy_reference_runtime"))
        self.sealed = self.enterContext(patch.object(benchmark.sandbox, "run_sealed", side_effect=self.run_fixture))
        self.render = self.enterContext(patch.object(benchmark, "render", return_value="measured report\n"))
        self.check_size = self.enterContext(patch.object(benchmark.budgets, "check_size"))
        self.apply = self.enterContext(patch.object(benchmark.budgets, "apply_memory", return_value=False))
        self.evidence = {"fixture": "accepted"}
        self.release = self.enterContext(patch.object(benchmark.budgets, "release_evidence", return_value=self.evidence))
        self.result = {"rss_scope": benchmark.budgets.RSS_SCOPE, "records": [], "profiles": [], "cpus": [0, 2]}
        self.change_during_measurement: Path | None = None
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def owned_path(self, name: str | Path) -> Path:
        return self.cpuinfo if name == "/proc/cpuinfo" else Path(name)

    def process_response(self, command: list[str], **_: object) -> SimpleNamespace:
        if command == [str(self.tracer), "--version"]:
            return SimpleNamespace(stdout="fixture strace\nsecond line\n")
        self.assertEqual(command, ["ldd", str(self.tracer)])
        return SimpleNamespace(returncode=0, stdout=f"libfixture.so => {self.library} (0x1)\n{self.loader} (0x2)\n", stderr="")

    def extract_fixture(self, archive: Path, destination: Path) -> Path:
        if destination.name == "candidate":
            self.assertEqual(archive, self.archive)
            prefix = destination / "usr"
            self.write_variant(prefix, b"product executable")
        elif destination.name == "official":
            self.assertEqual(archive, self.official_archive)
            prefix = destination / "cmake-release"
            if self.official_directory:
                self.write_variant(prefix, b"official CMake")
            else:
                destination.mkdir()
                prefix.write_bytes(b"unexpected file")
        else:
            raise AssertionError(f"unexpected extraction destination: {destination}")
        return destination

    @staticmethod
    def write_variant(prefix: Path, executable: bytes) -> None:
        (prefix / "bin").mkdir(parents=True)
        (prefix / "bin/cmake").write_bytes(executable)
        (prefix / "NOTICE").write_bytes(b"notice")
        (prefix / "cmake").symlink_to("bin/cmake")

    def stage_fixture(self, reference: Path, destination: Path, *_: object) -> None:
        self.assertEqual(reference, self.reference)
        self.write_variant(destination, b"musl executable")

    def run_fixture(self, _image: str, _command: list[str], *, mounts: list[tuple[Path, str]], **_: object) -> SimpleNamespace:
        destinations = {destination: path for path, destination in mounts}
        workspace = destinations["/benchmark"]
        self.assertEqual((workspace / "trace/strace").read_bytes(), self.tracer.read_bytes())
        self.assertEqual((workspace / "trace/loader").read_bytes(), self.loader.read_bytes())
        self.assertEqual((workspace / "trace/lib/libfixture.so").read_bytes(), self.library.read_bytes())
        (workspace / "results.json").write_text(json.dumps(self.result))
        if self.change_during_measurement is not None:
            self.change_during_measurement.write_bytes(b"changed")
        return SimpleNamespace(returncode=0, stdout="stdout", stderr="stderr")

    def test_publishes_report_and_same_archive_budget_evidence_after_success(self) -> None:
        benchmark.run(self.root, self.target)
        self.assertEqual(self.report.read_text(), "measured report\n")
        path = self.root / ".work/benchmark-results" / f"{self.target.triple}.json"
        self.assertEqual(json.loads(path.read_text()), self.evidence)
        self.assertEqual(self.budget_path.read_text(), "{}")
        self.local_process.assert_has_calls([
            call([str(self.tracer), "--version"], capture_output=True, text=True, check=True),
            call(["ldd", str(self.tracer)], capture_output=True, text=True, check=False),
        ])
        lock = benchmark.load_bootstrap(self.root / "bootstrap.lock.json")
        self.assertEqual(self.sealed.call_args.args, (lock.reference_image, ["/opt/alpine/usr/python3", "/suite/run.py", "5"]))
        options = self.sealed.call_args.kwargs
        self.assertEqual(options["target"], self.target)
        self.assertEqual(options["env"], {"PYTHONHOME": "/opt/alpine/usr", "TMPDIR": "/benchmark"})
        self.assertEqual(options["workdir"], "/benchmark")
        self.assertEqual(options["timeout"], 28800)
        work = options["mounts"][0][0]
        scratch = work.parent
        runtime = scratch / "runtime"
        project_names = ("fmt-source", "zstd-source", "libjpeg-turbo-source", "llvm-project-source")
        expected_mounts = {
            "/benchmark": work,
            "/suite": self.root / "tests/benchmark",
            "/controller/buildsys": self.root / "buildsys",
            "/controller/sources.lock.json": self.root / "sources.lock.json",
            "/controller/.work": scratch / "controller/.work",
            "/variants/product": scratch / "candidate/usr",
            "/variants/musl": scratch / "baseline",
            "/variants/kitware": scratch / "official/cmake-release",
            "/opt/alpine": runtime,
            self.target.musl_loader: runtime / "lib" / Path(self.target.musl_loader).name,
            "/etc/ld-musl-aarch64.path": runtime / "etc/ld-musl-aarch64.path",
            "/usr/bin/make": runtime / "usr/make",
            "/src/.work/build/aarch64-unknown-linux-musl/phases/prepare": self.phases / "prepare",
            "/tools/toolchain.cmake": self.phases / "bootstrap/toolchain.cmake",
            "/tools/ninja": self.phases / "bootstrap/ninja-build/ninja",
            **{f"/inputs/{name}": self.phases / f"project-{name}/source" for name in project_names},
        }
        self.assertEqual(options["mounts"], [(path, destination) for destination, path in expected_mounts.items()])
        self.assertEqual(options["read_only"], expected_mounts.keys() - {"/benchmark"})
        self.copy_runtime.assert_called_once_with("fixture-image", self.target, runtime)
        self.phase_cache_factory.assert_called_once_with(self.phases)
        self.assertEqual([item.args[0] for item in self.phase_cache.run.call_args_list], [f"project-{name}" for name in project_names])
        self.assertEqual(self.stdout.getvalue(), f"size and memory budgets passed for {self.target.triple}; existing baseline retained\n")


        records, repetitions, metadata = self.render.call_args.args
        self.assertEqual((records, repetitions), ([], 5))
        self.assertEqual(metadata["archive_sha256"], self.digest)
        self.assertEqual(metadata["baseline_digest"], self.reference_digest)
        self.assertEqual(metadata["cpu_model"], "fixture cpu")
        self.assertEqual(metadata["strace_version"], "fixture strace")
        self.assertEqual(metadata["cpus"], [0, 2])
        sources = {item.name: item for item in benchmark.load_sources(self.root / "sources.lock.json")}
        self.assertEqual(metadata["target"], self.target.triple)
        self.assertEqual(metadata["host"], "fixture host")
        self.assertEqual(metadata["container"], lock.reference_image)
        self.assertEqual(metadata["official_sha256"], sources["cmake-reference-aarch64"].sha256)
        self.assertEqual(metadata["projects"], [sources[name] for name in project_names])
        self.assertEqual(metadata["cmake_sha256"], sources["cmake-source"].sha256)
        self.assertEqual(metadata["toolchain_sha256"], sources["llvm-toolchain-aarch64"].sha256)
        self.assertEqual(metadata["runner_sha256"], benchmark.sha256_file(self.provenance[0]))
        self.assertEqual(metadata["implementation_sha256"], benchmark.sha256_file(Path(benchmark.__file__)))
        self.assertEqual(metadata["rss_implementation_sha256"], benchmark.sha256_file(self.provenance[1]))
        self.assertEqual(metadata["profiles"], [])
        self.assertEqual(
            metadata["sizes"],
            {
                "product": {"executable": 18, "files": 24, "archive": self.archive.stat().st_size},
                "musl": {"executable": 15, "files": 21, "archive": "not packaged"},
                "kitware": {"executable": 14, "files": 20, "archive": self.official_archive.stat().st_size},
            },
        )
        self.check_size.assert_called_once_with({}, self.target.triple, scratch / "candidate", self.archive)
        self.apply.assert_called_once_with({}, self.target.triple, self.digest, self.archive.stat().st_size, [])
        self.release.assert_called_once_with(
            {}, self.target.triple, self.digest, self.archive.stat().st_size, benchmark.sha256_file(self.budget_path), 5, [],
        )

    def test_report_identifies_x86_cpu_or_uses_the_missing_label(self) -> None:
        for cpuinfo, expected in (
            ("processor: 0\nmodel name\t: x86 fixture CPU  \n", "x86 fixture CPU"),
            ("processor: 0\n", "not reported"),
        ):
            with self.subTest(cpuinfo=cpuinfo):
                self.cpuinfo.write_text(cpuinfo)
                benchmark.run(self.root, self.target)
                self.assertEqual(self.render.call_args.args[2]["cpu_model"], expected)

    def test_tracer_dependencies_must_be_complete_before_launch(self) -> None:
        cases = (
            (7, "", "cannot identify strace libraries: fixture ldd failure"),
            (0, "", "cannot identify the host strace dynamic loader"),
            (0, f"{self.loader} (0x1)\n{self.loader} (0x2)\n", "cannot identify the host strace dynamic loader"),
            (0, f"{self.root / 'missing-loader'} (0x1)\n", "cannot identify the host strace dynamic loader"),
            (0, f"libfixture.so => {self.root / 'missing-library'} (0x1)\n{self.loader} (0x2)\n", "strace library is missing: libfixture.so"),
        )
        for returncode, stdout, message in cases:
            with self.subTest(message=message):
                self.local_process.side_effect = [
                    SimpleNamespace(stdout="fixture strace\n"),
                    SimpleNamespace(returncode=returncode, stdout=stdout, stderr="fixture ldd failure"),
                ]
                self.assert_rejected(message)
        self.sealed.assert_not_called()

    def test_official_archive_must_contain_a_single_directory(self) -> None:
        self.official_directory = False
        self.assert_rejected("official archive has an invalid layout")
        self.sealed.assert_not_called()

    def test_failed_runner_reports_the_tail_of_each_stream(self) -> None:
        self.sealed.side_effect = None
        stdout = "extra" + "X" * 3993 + "stdout!"
        stderr = "extra" + "Y" * 3993 + "stderr!"
        self.sealed.return_value = SimpleNamespace(returncode=17, stdout=stdout, stderr=stderr)
        self.assert_rejected(f"benchmark failed (17):\n{stdout[5:]}\n{stderr[5:]}")
        self.assertEqual(self.report.read_text(), "original performance.md\n")
        self.apply.assert_not_called()

    def test_rejects_changed_inputs_or_wrong_rss_scope_before_publishing(self) -> None:
        checks = (
            (self.provenance[0], "benchmark implementation changed during measurement"),
            (self.provenance[1], "benchmark implementation changed during measurement"),
            (self.budget_path, "release budgets changed during measurement"),
            (self.archive, "qualified archive changed during measurement"),
        )
        for changed, message in checks:
            with self.subTest(changed=changed):
                original = changed.read_bytes()
                self.change_during_measurement = changed
                try:
                    self.assert_rejected(message)
                finally:
                    changed.write_bytes(original)
        self.change_during_measurement = None
        self.result["rss_scope"] = "different"
        self.assert_rejected("benchmark produced an incompatible RSS measurement")
        self.apply.assert_not_called()
        self.assertEqual(self.report.read_text(), "original performance.md\n")

    def test_rejected_budget_saves_diagnostic_without_replacing_report(self) -> None:
        self.apply.side_effect = benchmark.budgets.BudgetError("fixture memory budget exceeded")
        path = self.root / ".work/tmp/benchmark-rejected.md"
        self.assert_rejected(f"fixture memory budget exceeded; rejected report: {path}")
        self.assertEqual(path.read_text(), "measured report\n")
        self.assertEqual(self.report.read_text(), "original performance.md\n")

    def test_initializing_budget_does_not_publish_release_evidence(self) -> None:
        self.budgets.return_value = {"fixture": "first baseline"}
        self.apply.return_value = True
        benchmark.run(self.root, self.target)
        self.assertEqual(self.budget_path.read_text(), '{\n  "fixture": "first baseline"\n}\n')
        self.assertFalse((self.root / ".work/benchmark-results").exists())
        self.assertEqual(self.stdout.getvalue(), f"memory baseline established for {self.target.triple}; review and commit the budget\n")


class BenchmarkReportPublicationTests(unittest.TestCase):
    def test_removes_staged_bytes_if_report_replacement_fails(self) -> None:
        with workspace() as directory:
            scratch = directory / "scratch"
            scratch.mkdir()
            report = directory / "report.md"
            report.write_text("previous report")
            failure = OSError("replacement failed")

            def fail_replace(source: str, destination: Path) -> None:
                temporary = Path(source)
                self.assertEqual(destination, report)
                self.assertEqual(temporary.parent, scratch)
                self.assertTrue(temporary.name.startswith("benchmark-report-"))
                self.assertEqual(temporary.read_text(), "fresh report")
                raise failure

            with patch.object(benchmark.os, "replace", side_effect=fail_replace), self.assertRaises(OSError) as caught:
                benchmark._write_atomic(report, "fresh report", scratch)
            self.assertIs(caught.exception, failure)
            self.assertEqual(report.read_text(), "previous report")
            self.assertEqual(list(scratch.iterdir()), [])
