from __future__ import annotations

import io
import re
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import archive, file_sha256, workspace, write_lock

from buildsys import inputs, qualify, sandbox, targets


class NetworkQualificationTests(unittest.TestCase):
    def test_rejects_missing_or_wrong_target_input_before_starting_either_child(self) -> None:
        target = targets.target('x86_64-unknown-linux-musl')
        source: dict[str, object] = {
            'name': 'cmake-source', 'version': '1', 'role': 'source', 'target': 'all',
            'url': 'https://example.invalid/cmake.tar.gz', 'sha256': 'a' * 64, 'size': 10,
        }
        openssl = {**source, 'name': 'openssl-test-x86_64', 'role': 'test',
                   'target': 'aarch64-unknown-linux-musl'}
        for entries in ([source, openssl], [{**openssl, 'target': target.triple}]):
            with (
                self.subTest(entries=entries),
                workspace() as root,
                patch.object(sandbox, 'run_sealed') as sealed,
                patch.object(sandbox, 'run_networked') as networked,
                self.assertRaisesRegex(qualify.QualificationError, '^network qualification inputs are missing from the lock$'),
            ):
                write_lock(root / 'sources.lock.json', entries)
                qualify.network(root=root, phase=root / 'absent', image='fixture-image', target=target)
            sealed.assert_not_called()
            networked.assert_not_called()

    def test_locked_inputs_and_child_results(self) -> None:
        target = targets.target('x86_64-unknown-linux-musl')
        source_url = 'https://example.invalid/cmake.tar.gz'
        source_digest = 'a' * 64
        local_success = 'local HTTPS qualification: 11 cases passed\n'
        internet_success = 'internet FetchContent: locked CMake source downloaded and verified\n'
        cases = (
            (0, local_success, 0, internet_success, ''),
            (9, local_success, 0, internet_success, 'local network qualification failed (9):\nlocal error'),
            (0, 'local HTTPS qualification: 10 cases passed\n', 0, internet_success,
             'local network qualification failed (0):\nlocal error'),
            (0, local_success, 8, internet_success, 'internet network qualification failed (8):\ninternet error'),
            (0, local_success, 0, f'{internet_success}skipped: no network\n',
             'internet network qualification skipped: no network'),
            (0, local_success, 0, 'unrelated output\n', 'internet network qualification produced no result'),
        )
        for local_code, local_log, internet_code, internet_log, message in cases:
            with self.subTest(message=message), workspace() as root:
                if message:
                    (root / '.work/tmp').mkdir(parents=True)
                package = archive(root / 'openssl.apk', [('usr/bin/openssl', b'locked openssl', None)])
                lock = root / 'sources.lock.json'
                write_lock(lock, [
                    {'name': 'openssl-test-x86_64', 'version': '1', 'role': 'test', 'target': target.triple,
                     'url': 'https://example.invalid/openssl.apk', 'sha256': file_sha256(package),
                     'size': package.stat().st_size},
                    {'name': 'cmake-source', 'version': '1', 'role': 'source', 'target': 'all',
                     'url': source_url, 'sha256': source_digest, 'size': 10},
                ])
                cache = inputs.Cache(root / '.work/cache', offline=True)
                openssl, _ = inputs.load_sources(lock)
                cache.store(package, openssl)
                phase = root / 'candidate'
                (phase / 'bin').mkdir(parents=True)
                (phase / 'bin/cmake').write_bytes(b'staged cmake')
                (phase / 'bin/ctest').symlink_to('cmake')
                for state in ('phase.json', 'state.json'):
                    (phase / state).write_text('private controller state')

                def assert_mounts(
                    mounts: list[tuple[Path, str]], options: dict[str, object], *, networked: bool,
                ) -> None:
                    paths = {destination: source for source, destination in mounts}
                    qualification = paths['/qualification']
                    candidate = qualification / 'relocated cmake'
                    suite = root / 'tests/acceptance/network'
                    expected = {
                        '/qualification': qualification,
                        '/qualification/relocated cmake': candidate,
                        '/suite': suite / 'internet' if networked else suite,
                    }
                    if not networked:
                        expected['/tools/openssl'] = qualification.parent / 'openssl/usr/bin/openssl'
                        self.assertEqual(paths['/tools/openssl'].read_bytes(), b'locked openssl')
                    self.assertEqual(paths, expected)
                    self.assertEqual(qualification.parent.parent, root / '.work/tmp')
                    self.assertEqual(qualification.name, 'qualification')
                    self.assertEqual({item.name for item in qualification.iterdir()}, {'relocated cmake'})
                    self.assertEqual((candidate / 'bin/cmake').read_bytes(), b'staged cmake')
                    self.assertEqual((candidate / 'bin/ctest').readlink(), Path('cmake'))
                    self.assertEqual({item.name for item in candidate.iterdir()}, {'bin'})
                    self.assertEqual(options, {
                        'target': target, 'env': {'TMPDIR': '/qualification'}, 'workdir': '/qualification',
                        'timeout': 1200 if networked else 1800, 'read_only': frozenset(expected) - {'/qualification'},
                    })

                local_result = sandbox.SealedResult(local_code, local_log, 'local error', 'none', {})
                internet_result = sandbox.SealedResult(internet_code, internet_log, 'internet error', 'none', {})

                def run_local(image, command, *, mounts, result=local_result, **options):
                    self.assertEqual((image, command), ('fixture-image', ['python3', '/suite/run.py']))
                    assert_mounts(mounts, options, networked=False)
                    return result

                def run_internet(image, command, *, mounts, result=internet_result, **options):
                    self.assertEqual(
                        (image, command), ('fixture-image', ['python3', '/suite/run.py', source_url, source_digest]),
                    )
                    assert_mounts(mounts, options, networked=True)
                    return result

                expected_error = self.assertRaisesRegex(
                    qualify.QualificationError, f'^{re.escape(message)}$',
                ) if message else nullcontext()
                with (
                    patch.object(sandbox, 'run_sealed', side_effect=run_local) as sealed,
                    patch.object(sandbox, 'run_networked', side_effect=run_internet) as networked,
                    redirect_stdout(io.StringIO()) as stdout,
                    expected_error,
                ):
                    qualify.network(root=root, phase=phase, image='fixture-image', target=target)
                self.assertEqual(sealed.call_count, 1)
                if message.startswith('local'):
                    networked.assert_not_called()
                    self.assertEqual(stdout.getvalue(), local_log)
                else:
                    networked.assert_called_once()
                    self.assertEqual(stdout.getvalue(), local_log + internet_log)
                self.assertEqual(list((root / '.work/tmp').iterdir()), [])
