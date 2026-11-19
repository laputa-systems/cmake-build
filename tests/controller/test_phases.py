from __future__ import annotations

import hashlib
import json
import locale
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
            self.assertIs(first.reused, False)
            self.assertIs(second.reused, True)
            self.assertIsInstance(first.fingerprint, str)
            self.assertEqual(second.fingerprint, first.fingerprint)
            self.assertEqual(second.directory, first.directory)
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

    def test_invalid_utf8_phase_record_is_rebuilt(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            inputs = {"source": DIGEST_A}
            calls = []

            def action(path):
                calls.append(len(calls) + 1)
                (path / "output").write_text(str(calls[-1]))

            first = cache.run("configure", inputs, action)
            (first.directory / "phase.json").write_bytes(bytes([255]))
            recovered = cache.run("configure", inputs, action)
            reused = cache.run("configure", inputs, action)
            self.assertFalse(recovered.reused)
            self.assertTrue(reused.reused)
            self.assertEqual(recovered.fingerprint, first.fingerprint)
            self.assertEqual((recovered.directory / "output").read_text(), "2")
            self.assertEqual(calls, [1, 2])

    def test_reuses_a_utf8_phase_record(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            inputs = {"révision": DIGEST_A}

            def write_output(path):
                (path / "output").write_bytes(b"ready")

            first = cache.run("configure", inputs, write_output)
            record_path = first.directory / "phase.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            self.addCleanup(locale.setlocale, locale.LC_CTYPE, locale.setlocale(locale.LC_CTYPE))
            locale.setlocale(locale.LC_CTYPE, "C")
            self.assertTrue(cache.run("configure", inputs, write_output).reused)

    def test_completed_phase_can_clear_an_already_removed_state(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            inputs = {"source": DIGEST_A}

            def write_output(path):
                (path / "state.json").unlink()
                (path / "output").write_bytes(b"ready")

            first = cache.run("configure", inputs, write_output)
            self.assertFalse(first.reused)
            self.assertFalse((first.directory / "state.json").exists())
            self.assertTrue(cache.run("configure", inputs, write_output).reused)

    def test_invalid_record_claims_force_a_rebuild(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            inputs = {"source": DIGEST_A}

            def action(path):
                (path / "output").write_text("ready")

            first = cache.run("configure", inputs, action)
            record_path = first.directory / "phase.json"
            original = json.loads(record_path.read_text())
            for value in ([], {**original, "schema_version": 2}, {**original, "inputs": {"source": DIGEST_B}}):
                with self.subTest(record=value):
                    record_path.write_text(json.dumps(value))
                    self.assertFalse(cache.run("configure", inputs, action).reused)
                    self.assertTrue(cache.run("configure", inputs, action).reused)

    def test_interrupted_phase_is_never_complete(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")

            fingerprint = cache.fingerprint("build", {"source": DIGEST_A})
            running = {"schema_version": 1, "phase": "build", "fingerprint": fingerprint, "status": "running"}

            def fail(path):
                self.assertEqual(json.loads((path / "state.json").read_text()), running)
                (path / "partial").write_text("half")
                raise RuntimeError("interrupted")

            with self.assertRaises(RuntimeError):
                cache.run("build", {"source": DIGEST_A}, fail)
            state = json.loads((directory / "phases" / "build" / "state.json").read_text())
            self.assertEqual(state, {**running, "status": "interrupted"})
            self.assertFalse((directory / "phases" / "build" / "phase.json").exists())

            def success(path):
                (path / "complete").write_text("yes")

            result = cache.run("build", {"source": DIGEST_A}, success)
            self.assertFalse(result.reused)
            self.assertFalse((result.directory / "state.json").exists())
            record = json.loads((result.directory / "phase.json").read_text())
            self.assertEqual(record["phase"], "build")
            self.assertEqual(record["inputs"], {"source": DIGEST_A})
            self.assertRegex(record["output_digest"], r"^[0-9a-f]{64}$")
            self.assertFalse((directory / "phases" / "build" / "partial").exists())

    def test_phase_requires_content_digests(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            for value in ("latest", "A" * 64, "X" * 64, "g" * 64, DIGEST_A + "a"):
                with self.subTest(digest=value), self.assertRaisesRegex(PhaseError, "sha256 digest"):
                    cache.fingerprint("build", {"source": value})
            with self.assertRaisesRegex(PhaseError, "invalid input name"):
                cache.fingerprint("build", {"": DIGEST_A})
            with self.assertRaisesRegex(PhaseError, "at least one input"):
                cache.fingerprint("build", {})


    def test_phase_name_participates_in_the_fingerprint(self) -> None:
        with workspace() as directory:
            cache = PhaseCache(directory / "phases")
            inputs = {"source": DIGEST_A, "toolchain": DIGEST_B}
            digest = cache.fingerprint("build", inputs)
            material = f'{{"inputs":{{"source":"{DIGEST_A}","toolchain":"{DIGEST_B}"}},"phase":"build"}}'
            self.assertEqual(digest, hashlib.sha256(material.encode()).hexdigest())
            self.assertEqual(cache.fingerprint("build", dict(reversed(inputs.items()))), digest)
            self.assertNotEqual(cache.fingerprint("configure", inputs), digest)
            for name in ("", "nested/build", ".staging"):
                with self.subTest(name=name), self.assertRaisesRegex(PhaseError, "invalid phase name"):
                    cache.fingerprint(name, inputs)


if __name__ == "__main__":
    unittest.main()
