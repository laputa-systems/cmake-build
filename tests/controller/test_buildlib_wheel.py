from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

from helpers import ROOT, workspace

from buildsys import WHEEL
from buildsys.inputs import load_sources

LOADER = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('wheel_under_test', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
    "import buildlib.locks\n"
    "print(buildlib.locks.__file__)\n"
)


def pin() -> dict:
    return next(item for item in json.loads((ROOT / "sources.lock.json").read_text())["inputs"] if item["name"] == "buildlib-wheel")


class PinTests(unittest.TestCase):
    def test_lock_pin_matches_pyproject_and_uv_lock(self) -> None:
        item = pin()
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertIn(f"laputa-buildlib=={item['version']}", project["dependencies"])
        package = next(entry for entry in tomllib.loads((ROOT / "uv.lock").read_text())["package"] if entry["name"] == "laputa-buildlib")
        self.assertEqual(package["version"], item["version"])
        self.assertEqual([(wheel["url"], wheel["hash"]) for wheel in package["wheels"]], [(item["url"], f"sha256:{item['sha256']}")])

    def test_lock_pin_is_a_valid_input_and_the_cached_wheel_verifies(self) -> None:
        self.assertIn("buildlib-wheel", {item.name for item in load_sources(ROOT / "sources.lock.json")})
        self.assertEqual(WHEEL.stat().st_size, pin()["size"])
        self.assertEqual(WHEEL.name, f"{pin()['sha256']}.blob")


class ShimTests(unittest.TestCase):
    def run_shim(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", "-c", LOADER, str(root / "buildsys/buildlib_wheel.py")],
                              cwd=root, capture_output=True, text=True, check=False)

    def project(self, directory: Path, served: Path) -> Path:
        root = directory / "project"
        (root / "buildsys").mkdir(parents=True)
        shutil.copyfile(ROOT / "buildsys/buildlib_wheel.py", root / "buildsys/buildlib_wheel.py")
        item = pin()
        (root / "sources.lock.json").write_text(json.dumps({"schema_version": 1, "inputs": [{**item, "url": served.as_uri()}]}))
        return root

    def test_imports_buildlib_from_the_verified_cache_object(self) -> None:
        with workspace() as directory:
            root = self.project(directory, WHEEL)
            cached = root / ".work/cache/objects" / WHEEL.name
            cached.parent.mkdir(parents=True)
            shutil.copyfile(WHEEL, cached)
            result = self.run_shim(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith(str(cached)), result.stdout)

    def test_downloads_a_missing_wheel_into_the_cache(self) -> None:
        with workspace() as directory:
            root = self.project(directory, WHEEL)
            result = self.run_shim(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / ".work/cache/objects" / WHEEL.name).read_bytes(), WHEEL.read_bytes())

    def test_rejects_unpinned_bytes_from_cache_and_network(self) -> None:
        with workspace() as directory:
            forged = directory / "forged.whl"
            forged.write_bytes(b"x" + WHEEL.read_bytes()[1:])
            root = self.project(directory, forged)
            cached = root / ".work/cache/objects" / WHEEL.name
            cached.parent.mkdir(parents=True)
            cached.write_bytes(forged.read_bytes())
            result = self.run_shim(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("did not serve the pinned bytes", result.stderr)
            self.assertEqual(cached.read_bytes(), forged.read_bytes())


if __name__ == "__main__":
    unittest.main()
