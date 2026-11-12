from __future__ import annotations

import json
import unittest

from helpers import workspace

from buildsys.phases import PhaseCache, PhaseError

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class PhaseTests(unittest.TestCase):
    def test_reuses_phase_while_inputs_match(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            runs = []

            def action(path):
                runs.append(1)
                (path / "output").write_text("one")

            first = cache.run("configure", {"source": DIGEST_A}, action)
            second = cache.run("configure", {"source": DIGEST_A}, action)
            self.assertFalse(first.reused)
            self.assertTrue(second.reused)
            self.assertEqual(len(runs), 1)
            self.assertEqual((directory / "phases" / "configure" / "output").read_text(), "one")

    def test_stale_reuse_after_fingerprint_change(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            runs = []

            def action(path):
                runs.append(1)
                (path / "output").write_text(str(len(runs)))

            cache.run("configure", {"source": DIGEST_A}, action)
            changed = cache.run("configure", {"source": DIGEST_B}, action)
            self.assertFalse(changed.reused)
            self.assertEqual(len(runs), 2)
            self.assertEqual((directory / "phases" / "configure" / "output").read_text(), "2")

    def test_tampered_outputs_force_rerun(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            runs = []

            def action(path):
                runs.append(1)
                (path / "output").write_text("expected")

            cache.run("configure", {"source": DIGEST_A}, action)
            (directory / "phases" / "configure" / "output").write_text("tampered")
            result = cache.run("configure", {"source": DIGEST_A}, action)
            self.assertFalse(result.reused)
            self.assertEqual(len(runs), 2)

    def test_interrupted_phase_is_never_complete(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")

            def fail(path):
                (path / "partial").write_text("half")
                raise RuntimeError("interrupted")

            with self.assertRaises(RuntimeError):
                cache.run("build", {"source": DIGEST_A}, fail)
            state = json.loads((directory / "phases" / "build" / "state.json").read_text())
            self.assertEqual(state["status"], "interrupted")
            self.assertFalse((directory / "phases" / "build" / "phase.json").exists())

            def success(path):
                (path / "complete").write_text("yes")

            result = cache.run("build", {"source": DIGEST_A}, success)
            self.assertFalse(result.reused)
            self.assertTrue((directory / "phases" / "build" / "phase.json").is_file())
            self.assertFalse((directory / "phases" / "build" / "partial").exists())

    def test_phase_requires_content_digests(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            with self.assertRaisesRegex(PhaseError, "sha256 digest"):
                cache.fingerprint("build", {"source": "latest"})
            with self.assertRaisesRegex(PhaseError, "at least one input"):
                cache.fingerprint("build", {})


if __name__ == "__main__":
    unittest.main()
