from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, workspace

from buildsys import buildlib_wheel
from buildsys.inputs import load_sources

PROBE = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('admission_under_test', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
    "import buildlib.locks\n"
    "print(buildlib.locks.__file__)\n"
)


def pin() -> dict[str, object]:
    return next(item for item in json.loads((ROOT / "sources.lock.json").read_text())["inputs"] if item["name"] == "buildlib-wheel")


def copied_tree(directory: Path) -> Path:
    root = directory / "project"
    (root / "buildsys").mkdir(parents=True)
    shutil.copyfile(ROOT / "buildsys/buildlib_wheel.py", root / "buildsys/buildlib_wheel.py")
    shutil.copytree(ROOT / "bootstrap", root / "bootstrap")
    (root / "sources.lock.json").write_text(json.dumps({"schema_version": 1, "inputs": [pin()]}))
    return root


def run_admission(root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", PROBE, str(root / "buildsys/buildlib_wheel.py")],
        cwd=root, capture_output=True, text=True, check=False,
        env={**os.environ, "BUILDLIB_CACHE": str(root / ".work/buildlib-cache"), **env},
    )


class PinTests(unittest.TestCase):
    def test_lock_pin_matches_pyproject_uv_lock_and_vendored_bootstrap(self) -> None:
        item = pin()
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertIn(f"laputa-buildlib=={item['version']}", project["dependencies"])
        package = next(entry for entry in tomllib.loads((ROOT / "uv.lock").read_text())["package"] if entry["name"] == "laputa-buildlib")
        self.assertEqual(package["version"], item["version"])
        self.assertEqual([(wheel["url"], wheel["hash"]) for wheel in package["wheels"]], [(item["url"], f"sha256:{item['sha256']}")])
        shim_wheel = next(line.split() for line in (ROOT / "bootstrap/python.lock").read_text().splitlines() if line.startswith("wheel "))
        self.assertEqual((shim_wheel[1], shim_wheel[2]), (item["url"], item["sha256"]))

    def test_lock_pin_is_a_valid_input_and_the_cache_object_verifies(self) -> None:
        self.assertIn("buildlib-wheel", {item.name for item in load_sources(ROOT / "sources.lock.json")})
        admitted = buildlib_wheel.wheel_path()
        self.assertEqual(admitted.name, f"{pin()['sha256']}.blob")
        self.assertEqual(admitted.stat().st_size, pin()["size"])


class ProvenanceTests(unittest.TestCase):
    def test_controller_imports_buildlib_from_the_verified_cache_object(self) -> None:
        import buildlib

        expected = buildlib_wheel.wheel_path()
        self.assertTrue(Path(buildlib.__file__).is_relative_to(expected), buildlib.__file__)
        self.assertEqual(hashlib.sha256(expected.read_bytes()).hexdigest(), pin()["sha256"])


@unittest.skipIf(shutil.which("curl") is None, "provisioning runs bootstrap/buildlib-run, which downloads with curl")
class AdmissionTests(unittest.TestCase):
    def test_admission_refuses_a_local_source_tree_pretending_to_be_the_wheel(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            impostor = root / "buildlib"
            impostor.mkdir()
            (impostor / "__init__.py").write_text("raise SystemExit('impostor imported')\n")
            result = run_admission(root, PYTHONPATH=str(root))
            self.assertIn("impostor imported", result.stderr)

    def test_copies_the_shim_verified_wheel_into_the_cache_once(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            first = run_admission(root)
            self.assertEqual(first.returncode, 0, first.stderr)
            cache = root / ".work/cache/objects" / f"{pin()['sha256']}.blob"
            self.assertTrue(first.stdout.startswith(str(cache)), first.stdout)
            self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), pin()["sha256"])
            second = run_admission(root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout, first.stdout)
            self.assertEqual(list(cache.parent.iterdir()), [cache])

    def test_replaces_corrupt_and_symlinked_cache_objects_before_using_them(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            cache = root / ".work/cache/objects" / f"{pin()['sha256']}.blob"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"corrupt")
            result = run_admission(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), pin()["sha256"])

            source = directory / "host.whl"
            source.write_bytes(b"not the wheel")
            cache.unlink()
            cache.symlink_to(source)
            result = run_admission(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing cache symlink", result.stderr)
            self.assertEqual(source.read_bytes(), b"not the wheel")

    def test_injected_wrong_wheel_digest_fails_before_importing(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            lock = json.loads((root / "sources.lock.json").read_text())
            lock["inputs"][0]["sha256"] = "0" * 64
            (root / "sources.lock.json").write_text(json.dumps(lock))
            result = run_admission(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("copied bytes that do not match the pin", result.stderr)
            self.assertNotIn("commands from the wheel", result.stdout)
            self.assertFalse((root / ".work/cache/objects" / f"{'0' * 64}.blob").exists())

    def test_injected_wrong_wheel_size_fails_before_importing(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            lock = json.loads((root / "sources.lock.json").read_text())
            lock["inputs"][0]["size"] = int(lock["inputs"][0]["size"]) + 1
            (root / "sources.lock.json").write_text(json.dumps(lock))
            result = run_admission(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("do not match the pin", result.stderr)
            self.assertNotIn("imported from", result.stdout)

    def test_truncated_cached_wheel_is_replaced_rather_than_imported(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            cache = root / ".work/cache/objects" / f"{pin()['sha256']}.blob"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(Path(buildlib_wheel.wheel_path()).read_bytes()[:512])
            result = run_admission(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith(str(cache)), result.stdout)
            self.assertEqual(cache.stat().st_size, pin()["size"])

    def test_reports_a_shim_that_writes_no_wheel(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            (root / "bootstrap/buildlib-run").write_text("#!/bin/sh\nexit 0\n")
            result = run_admission(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No such file or directory", result.stderr)
            self.assertFalse((root / ".work/cache/objects" / f"{pin()['sha256']}.blob").exists())

    def test_reports_absent_shim_and_malformed_pins(self) -> None:
        with (
            workspace() as root,
            patch.object(buildlib_wheel, "ROOT", root),
            patch.object(buildlib_wheel, "SHIM", root / "bootstrap/buildlib-run"),
        ):
            (root / "bootstrap").mkdir()
            lock = root / "sources.lock.json"
            item = {"name": "buildlib-wheel", "url": "https://fixture/wheel.whl", "sha256": "a" * 64, "size": 0}
            lock.write_text(json.dumps({"schema_version": 1, "inputs": [item]}))
            with (
                patch.object(buildlib_wheel, "SOURCES_LOCK", lock),
                self.assertRaisesRegex(ImportError, "could not provision it"),
            ):
                buildlib_wheel.locate()
            with patch.object(buildlib_wheel, "SOURCES_LOCK", lock):
                for data in (None, "{", "[]", "{}", '{"inputs":[]}'):
                    with self.subTest(data=data):
                        if data is None:
                            lock.unlink(missing_ok=True)
                        else:
                            lock.write_text(data)
                        with self.assertRaisesRegex(ImportError, "does not pin buildlib-wheel"):
                            buildlib_wheel._pin()
                for field, value, reason in (
                    ("url", "", "url must be a nonempty string"),
                    ("sha256", "invalid", "sha256 must be a lowercase hexadecimal digest"),
                    ("sha256", 42, "sha256 must be a lowercase hexadecimal digest"),
                    ("size", True, "size must be a nonnegative integer"),
                    ("size", -1, "size must be a nonnegative integer"),
                ):
                    with self.subTest(field=field, value=value):
                        lock.write_text(json.dumps({"inputs": [item | {field: value}]}))
                        with self.assertRaises(ImportError) as invalid:
                            buildlib_wheel._pin()
                        self.assertEqual(str(invalid.exception.__cause__), reason)
                lock.write_text(json.dumps({"inputs": [item]}))
                self.assertEqual(buildlib_wheel._pin(), {key: item[key] for key in ("url", "sha256", "size")})

    def test_admission_verifies_the_cache_even_when_buildlib_is_importable(self) -> None:
        wheel = buildlib_wheel.wheel_path()
        before = list(buildlib_wheel.sys.path)
        with (
            patch.object(buildlib_wheel.importlib.util, "find_spec", return_value=object()),
            patch.object(buildlib_wheel, "locate", return_value=wheel) as locate,
        ):
            self.assertEqual(buildlib_wheel.admit(), wheel)
        locate.assert_called_once_with()
        self.assertEqual(buildlib_wheel.sys.path, before)


if __name__ == "__main__":
    unittest.main()
