from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import workspace

import build


class ReleaseAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root: Path = self.enterContext(workspace())
        self.work = self.root / ".work"
        self.target = build._target("aarch64-unknown-linux-musl")
        self.args = argparse.Namespace(target=self.target.triple)
        self.commit = "0123456789abcdef0123456789abcdef01234567"
        directory = self.work / "artifacts" / self.target.triple
        directory.mkdir(parents=True)
        self.archive = directory / f"cmake-4.4.5-{self.target.triple}.tar.xz"
        self.archive.write_bytes(b"fixture artifact")
        self.candidate = directory / "candidate.json"
        self.record: dict[str, object] = {
            "archive": self.archive.name, "commit": self.commit,
            "size": self.archive.stat().st_size, "sha256": build.digest_file(self.archive)[0],
        }
        self.save_candidate()
        self.enterContext(patch.multiple(build, ROOT=self.root, WORK=self.work))
        self.sources = self.enterContext(patch.object(build, "load_sources", return_value=[SimpleNamespace(name="cmake-source", version="4.4.5")]))
        self.enterContext(patch.object(build, "_source_commit", return_value=self.commit))
        self.package = self.enterContext(patch.object(build, "package_command", side_effect=AssertionError("unexpected packaging")))
        self.prepare = self.enterContext(patch.object(build, "test_command"))
        self.lock = object()
        self.load_lock = self.enterContext(patch.object(build, "load_bootstrap", return_value=self.lock))
        self.image = self.enterContext(patch.object(build.sandbox, "image_tag", return_value="fixture image"))
        self.read_budget = self.enterContext(patch.object(build.budgets, "read", return_value={"fixture": "budgets"}))
        self.size = self.enterContext(patch.object(build.budgets, "check_size", return_value={"fixture": 12}))
        self.suites = {
            name: self.enterContext(patch.object(build.qualify, name))
            for name in ("projects", "upstream", "basic", "parity", "network")
        }
        self.activate = self.enterContext(patch.object(build.generations, "qualify"))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def save_candidate(self, **changes: object) -> None:
        self.candidate.write_text(json.dumps({**self.record, **changes}))

    def assert_rejected(self, expected: str, *, prefix: bool = False) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as caught:
            build.qualify_command(self.args)
        self.assertEqual(caught.exception.code, 2)
        if prefix:
            self.assertTrue(error.getvalue().startswith(f"error: {expected}"))
        else:
            self.assertEqual(error.getvalue(), f"error: {expected}\n")

    def test_rejects_incomplete_or_mismatched_candidates_before_testing(self) -> None:
        mismatch = "candidate record does not match the archive or repository commit"
        self.candidate.write_text("{")
        self.assert_rejected("candidate record is missing or invalid: ", prefix=True)
        self.candidate.write_text("[]")
        self.assert_rejected(mismatch)
        for invalid in (
            {"archive": "other.tar.xz"},
            {"commit": "f" * 40},
            {"sha256": None},
            {"sha256": "e" * 63},
            {"size": -1},
        ):
            with self.subTest(invalid=invalid):
                self.save_candidate(**invalid)
                self.assert_rejected(mismatch)
        self.save_candidate(sha256="f" * 64)
        self.assert_rejected("candidate archive has been modified")
        self.save_candidate()
        self.archive.unlink()
        self.assert_rejected(mismatch)
        self.package.assert_not_called()
        self.read_budget.assert_not_called()
        self.prepare.assert_not_called()
        self.activate.assert_not_called()

    def test_missing_candidate_builds_before_qualifying(self) -> None:
        self.archive.unlink()
        self.candidate.unlink()

        def package(args: argparse.Namespace) -> int:
            self.assertEqual(args, argparse.Namespace(target=self.target.triple, in_container=False))
            self.archive.write_bytes(b"fixture artifact")
            self.save_candidate()
            return 0

        self.package.side_effect = package
        self.activate.return_value = self.root / "selected"
        self.assertEqual(build.qualify_command(self.args), 0)
        self.package.assert_called_once()
        self.prepare.assert_called_once()

    def test_activation_receives_checks_of_the_extracted_archive(self) -> None:
        report = self.root / "docs/qualification.md"
        report.parent.mkdir()
        report.write_text(f"## Latest upstream subset: {self.target.triple}\n\nFixture case passed\n\n## Other\nLater section.\n\n## Final\nLast section.\n")
        tree = self.root / "staged/tree"
        tree.mkdir(parents=True)
        qualification: dict[str, object] = {}

        def activate(root: Path, archive: Path, digest: str, check: Callable[[Path], dict[str, object]]) -> Path:
            self.assertEqual((root, archive, digest), (self.work / "generations" / self.target.triple, self.archive, self.record["sha256"]))
            qualification.update(check(tree))
            return self.root / "selected"

        self.activate.side_effect = activate
        self.assertEqual(build.qualify_command(self.args), 0)
        self.sources.assert_called_once_with(build.SOURCES_LOCK)
        self.load_lock.assert_called_once_with(build.BOOTSTRAP_LOCK)
        self.image.assert_called_once_with(self.lock, self.target, build.DOCKERFILE)
        self.read_budget.assert_called_once_with(self.root / "release-budgets.json")
        self.prepare.assert_called_once_with(
            argparse.Namespace(target=self.target.triple, suite="upstream", in_container=False), prepare_only=True,
        )
        self.size.assert_called_once_with({"fixture": "budgets"}, self.target.triple, tree, tree.parent / "artifact.tar.xz")
        for suite in self.suites.values():
            suite.assert_called_once_with(root=self.root, phase=tree / "usr", image="fixture image", target=self.target)
        self.assertEqual(qualification, {
            "basic": "passed", "parity": "passed", "network": "passed", "projects": "passed",
            "upstream": "Fixture case passed", "sizes": {"fixture": 12},
        })
        self.assertEqual(
            self.stdout.getvalue(),
            f"size budgets passed: {{'fixture': 12}}\nqualified generation: {self.root / 'selected'}\n",
        )
        report.write_text("## No matching upstream report\n")
        self.assert_rejected("upstream qualification report is missing")
