from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, workspace

from buildsys import WHEEL, buildlib_wheel
from buildsys.inputs import load_sources

LOADER = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('wheel_under_test', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
    "import buildlib.locks\n"
    "print(buildlib.locks.__file__)\n"
)


def pin() -> dict[str, object]:
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
    def run_shim(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-I", "-c", LOADER, str(root / "buildsys/buildlib_wheel.py")],
                              cwd=root, capture_output=True, text=True, check=False)

    def project(self, directory: Path, served: Path) -> Path:
        root = directory / "project"
        (root / "buildsys").mkdir(parents=True)
        shutil.copyfile(ROOT / "buildsys/buildlib_wheel.py", root / "buildsys/buildlib_wheel.py")
        item = pin()
        (root / "sources.lock.json").write_text(json.dumps({"schema_version": 1, "inputs": [{**item, "url": served.as_uri()}]}))
        return root

    def test_rejects_invalid_pin_fields_before_cache_access(self) -> None:
        for field, value in (("url", 123), ("sha256", "../outside"), ("size", True)):
            with self.subTest(field=field), workspace() as directory:
                root = self.project(directory, WHEEL)
                lock = root / "sources.lock.json"
                document = json.loads(lock.read_text())
                document["inputs"][0][field] = value
                lock.write_text(json.dumps(document))
                result = self.run_shim(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"{field} must be", result.stderr)
                self.assertFalse((root / ".work/cache").exists())

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


class CacheAdmissionTests(unittest.TestCase):
    def test_replaces_cache_symlink_then_reuses_verified_regular_file(self) -> None:
        with workspace() as root:
            source = root / "wheel.whl"
            body = b"wheel fixture bytes"
            source.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            lock = root / "sources.lock.json"
            lock.write_text(json.dumps({"inputs": [
                {"name": "other"},
                {"name": "buildlib-wheel", "url": source.as_uri(), "sha256": digest, "size": len(body)},
            ]}))
            cached = root / ".work" / "cache" / "objects" / f"{digest}.blob"
            cached.parent.mkdir(parents=True)
            cached.symlink_to(source)
            with patch.object(buildlib_wheel, "ROOT", root), patch.object(buildlib_wheel, "SOURCES_LOCK", lock):
                self.assertEqual(buildlib_wheel.locate(), cached)
                self.assertFalse(cached.is_symlink())
                self.assertEqual(cached.read_bytes(), body)
                self.assertEqual(source.read_bytes(), body)
                cached.write_bytes(b"!" * len(body))
                self.assertEqual(buildlib_wheel.locate(), cached)
                self.assertEqual(cached.read_bytes(), body)
                source.unlink()
                self.assertEqual(buildlib_wheel.locate(), cached)
                self.assertEqual(list(cached.parent.iterdir()), [cached])

    def test_wheel_download_bounds_reads_and_preserves_destination_after_failed_replace(self) -> None:
        body = b"known wheel bytes"
        pin: buildlib_wheel.WheelPin = {
            "url": "https://example.invalid/wheel",
            "sha256": hashlib.sha256(body).hexdigest(),
            "size": len(body),
        }
        with workspace() as root:
            cache = root / "objects"
            cache.mkdir()
            cached = cache / "wheel.blob"
            cached.write_bytes(b"prior object")
            with (
                patch.object(buildlib_wheel.urllib.request, "urlopen", return_value=io.BytesIO(body + b"overflow")) as fetch,
                self.assertRaisesRegex(ImportError, "^buildlib-wheel: .* did not serve the pinned bytes$"),
            ):
                buildlib_wheel._download(pin, cached)
            self.assertEqual(cached.read_bytes(), b"prior object")
            self.assertEqual(list(cache.iterdir()), [cached])
            request = fetch.call_args.args[0]
            self.assertEqual(request.full_url, pin["url"])
            self.assertEqual(request.get_header("User-agent"), "cmake-build/1")
            self.assertEqual(fetch.call_args.kwargs["timeout"], 120)

            with (
                patch.object(buildlib_wheel.urllib.request, "urlopen", side_effect=OSError("fixture offline")),
                self.assertRaises(ImportError) as offline,
            ):
                buildlib_wheel._download(pin, cached)
            self.assertEqual(
                str(offline.exception),
                f"buildlib-wheel is absent from {root} and cannot be downloaded "
                f"from {pin['url']}: fixture offline; run `python3 build.py fetch` with network access first",
            )

            def refuse_replace(staged: str, destination: Path) -> None:
                temporary = Path(staged)
                self.assertEqual(destination, cached)
                self.assertEqual(temporary.parent, cache)
                self.assertTrue(temporary.name.startswith(".buildlib-wheel."))
                self.assertEqual(temporary.suffix, ".part")
                self.assertEqual(temporary.read_bytes(), body)
                raise OSError("unavailable")

            response = io.BytesIO(body)
            with (
                patch.object(response, "read", wraps=response.read) as read,
                patch.object(buildlib_wheel.urllib.request, "urlopen", return_value=response),
                patch.object(buildlib_wheel.os, "replace", side_effect=refuse_replace),
                self.assertRaisesRegex(OSError, "^unavailable$"),
            ):
                buildlib_wheel._download(pin, cached)
            read.assert_called_once_with(len(body) + 1)
            self.assertEqual(cached.read_bytes(), b"prior object")
            self.assertEqual(list(cache.iterdir()), [cached])

            nested = root / "new-cache" / "objects" / "wheel.blob"
            with patch.object(buildlib_wheel.urllib.request, "urlopen", return_value=io.BytesIO(body)):
                buildlib_wheel._download(pin, nested)
            self.assertEqual(nested.read_bytes(), body)
            self.assertEqual(list(nested.parent.iterdir()), [nested])

    def test_reports_unavailable_and_malformed_wheel_pins(self) -> None:
        with workspace() as root:
            lock = root / "sources.lock.json"
            item = {"name": "buildlib-wheel", "url": "file:///fixture", "sha256": "a" * 64, "size": 0}
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


if __name__ == "__main__":
    unittest.main()
