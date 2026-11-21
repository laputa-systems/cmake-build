from __future__ import annotations

import hashlib
import json
import os
import shlex
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
    "import importlib.util, os, sys\n"
    "if os.environ.get('COMPETING_PATH'):\n"
    "    sys.path.insert(0, os.environ['COMPETING_PATH'])\n"
    "if os.environ.get('PREIMPORT'):\n"
    "    import buildlib\n"
    "spec = importlib.util.spec_from_file_location('admission_under_test', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
    "import buildlib.locks\n"
    "print(buildlib.locks.__file__)\n"
)

IMPOSTOR = "import pathlib\npathlib.Path(__file__).parent.parent.joinpath('impostor-ran').write_text('{module}')\n"

# Both shims finish copying before either exits; the second exits only after the first caller published.
RENDEZVOUS_SHIM = """#!/bin/sh
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
wait_for() {{
    tries=0
    until eval "$1"; do
        tries=$((tries + 1))
        [ "$tries" -lt 300 ] || exit 3
        sleep 0.1
    done
}}
: > "$here/ready.$$"
wait_for '[ "$(ls "$here" | grep -c "^ready\\.")" -ge 2 ]'
sh "$here/real-buildlib-run" "$@"
: > "$here/copied.$$"
wait_for '[ "$(ls "$here" | grep -c "^copied\\.")" -ge 2 ]'
if (set -C; : > "$here/first") 2>/dev/null; then exit 0; fi
wait_for '[ -f {blob} ]'
sleep 0.5
"""


def pin() -> dict[str, object]:
    return next(item for item in json.loads((ROOT / "sources.lock.json").read_text())["inputs"] if item["name"] == "buildlib-wheel")


def copied_tree(directory: Path) -> Path:
    root = directory / "project"
    (root / "buildsys").mkdir(parents=True)
    shutil.copyfile(ROOT / "buildsys/buildlib_wheel.py", root / "buildsys/buildlib_wheel.py")
    shutil.copytree(ROOT / "bootstrap", root / "bootstrap")
    (root / "sources.lock.json").write_text(json.dumps({"schema_version": 1, "inputs": [pin()]}))
    return root


def admission_command(root: Path) -> list[str]:
    return [sys.executable, "-I", "-c", PROBE, str(root / "buildsys/buildlib_wheel.py")]


def admission_env(root: Path, **env: str) -> dict[str, str]:
    return {**os.environ, "BUILDLIB_CACHE": str(root / ".work/buildlib-cache"), **env}


def run_admission(root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        admission_command(root), cwd=root, capture_output=True, text=True, check=False, env=admission_env(root, **env),
    )


def plant_impostor(root: Path) -> Path:
    package = root / "buildlib"
    package.mkdir()
    (package / "__init__.py").write_text(IMPOSTOR.format(module="buildlib"))
    (package / "locks.py").write_text(IMPOSTOR.format(module="buildlib.locks"))
    return root / "impostor-ran"


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
    def test_competing_local_package_never_executes_with_an_empty_or_populated_cache(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            marker = plant_impostor(root)
            cache = root / ".work/cache/objects" / f"{pin()['sha256']}.blob"
            for state in ("empty", "populated"):
                with self.subTest(cache=state):
                    self.assertEqual(cache.is_file(), state == "populated")
                    result = run_admission(root, COMPETING_PATH=str(root), PYTHONPATH=str(root))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(result.stdout.startswith(str(cache)), result.stdout)
                    self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")
                    self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), pin()["sha256"])

    def test_refuses_a_buildlib_imported_before_admission(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            plant_impostor(root)
            result = run_admission(root, COMPETING_PATH=str(root), PREIMPORT="1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not the pinned wheel", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_simultaneous_provisioning_callers_both_admit_intact_bytes(self) -> None:
        with workspace() as directory:
            root = copied_tree(directory)
            shim = root / "bootstrap/buildlib-run"
            shim.rename(root / "bootstrap/real-buildlib-run")
            cache = root / ".work/cache/objects" / f"{pin()['sha256']}.blob"
            shim.write_text(RENDEZVOUS_SHIM.format(blob=shlex.quote(str(cache))))
            callers = [
                subprocess.Popen(admission_command(root), cwd=root, env=admission_env(root),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(2)
            ]
            results = [(caller.wait(timeout=120), *caller.communicate()) for caller in callers]
            self.assertEqual(len(list((root / "bootstrap").glob("ready.*"))), 2)
            for returncode, stdout, stderr in results:
                self.assertEqual(returncode, 0, stderr)
                self.assertTrue(stdout.startswith(str(cache)), stdout)
            self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), pin()["sha256"])
            self.assertEqual(list(cache.parent.iterdir()), [cache])

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
            self.assertIn("the bootstrap shim copied bytes that do not match the pin", result.stderr)
            self.assertEqual(list((root / ".work/cache/objects").iterdir()), [])

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

    def test_admission_accepts_buildlib_already_imported_from_the_cache_object(self) -> None:
        import buildlib

        before = list(buildlib_wheel.sys.path)
        self.assertEqual(buildlib_wheel.admit(), buildlib_wheel.wheel_path())
        self.assertEqual(buildlib_wheel.sys.path, before)
        self.assertTrue(Path(buildlib.__file__).is_relative_to(buildlib_wheel.wheel_path()))


if __name__ == "__main__":
    unittest.main()
