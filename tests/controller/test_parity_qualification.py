from __future__ import annotations

import io
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import ROOT, archive, file_sha256, workspace, write_lock

from buildsys import inputs, qualify, sandbox, targets


class ParityQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = self.enterContext(workspace())
        self.target = targets.target('x86_64-unknown-linux-musl')
        self.phase = self.root / 'candidate'
        (self.phase / 'bin').mkdir(parents=True)
        (self.phase / 'bin/cmake').write_bytes(b'candidate')
        (self.phase / 'bin/ctest').symlink_to('cmake')
        for state in ('phase.json', 'state.json'):
            (self.phase / state).write_text('controller state')
        (self.root / 'docs').mkdir()
        self.report = self.root / 'docs/qualification.md'
        self.marker = f'## Latest automated parity differences: {self.target.triple}'
        self.original = f'# Qualification\n\n{self.marker}\n\nstale results\n\n## Other scope\n\nkeep\n'
        self.report.write_text(self.original)
        self.bootstrap = self.root / 'bootstrap.lock.json'
        shutil.copyfile(ROOT / self.bootstrap.name, self.bootstrap)
        self.sources = self.root / 'sources.lock.json'

    def cache_reference(self, members: list[tuple[str, bytes | None, str | None]]) -> None:
        package = archive(self.root / 'reference.tar.gz', members)
        write_lock(self.sources, [
            {'name': 'cmake-reference-x86_64', 'version': '1', 'role': 'reference', 'target': self.target.triple,
             'url': 'https://example.invalid/reference.tar.gz', 'sha256': file_sha256(package),
             'size': package.stat().st_size},
        ])
        cache = inputs.Cache(self.root / '.work/cache', offline=True)
        cache.store(package, inputs.load_sources(self.sources)[0])

    def test_compares_graph_outputs_and_replaces_only_the_current_report(self) -> None:
        self.cache_reference([('kitware/bin/cmake', b'reference', None)])
        runtime_paths: list[Path] = []
        files = ('ninja build/build.ninja', 'ninja-file-api.json', 'make-file-api.json', 'system-information-subset.txt')
        phases = self.root / '.work/build' / self.target.triple / 'phases'
        calls = [('graph', 'candidate'), ('graph', 'reference'), ('archive', 'candidate'), ('archive', 'reference')]
        reference_image = inputs.load_bootstrap(self.bootstrap).reference_image

        def copy_runtime(image, target, destination):
            self.assertEqual((image, target), ('fixture-image', self.target))
            self.assertEqual(destination.name, 'runtime')
            self.assertEqual(destination.parent.parent, self.root / '.work/tmp')
            destination.mkdir()
            runtime_paths.append(destination)

        for changed in (False, True):
            remaining_calls = iter(calls)

            def run(image, command, *, mounts, changed_graph=changed, next_call=remaining_calls, **options):
                suite, label = next(next_call)
                paths = {container: source for source, container in mounts}
                runtime = runtime_paths[-1]
                work = paths['/qualification']
                prefix = paths['/qualification/relocated cmake']
                use_reference = label == 'reference'
                expected = {
                    '/qualification': runtime.parent / label,
                    '/qualification/relocated cmake': runtime.parent / (
                        'reference-source/kitware' if use_reference else 'candidate/relocated cmake'
                    ),
                    '/suite': self.root / 'tests/acceptance' / suite,
                    f'/src/.work/build/{self.target.triple}/phases/prepare': phases / 'prepare',
                    '/tools/toolchain.cmake': phases / 'bootstrap/toolchain.cmake',
                    '/tools/ninja': phases / 'bootstrap/ninja-build/ninja',
                }
                env = {'TMPDIR': '/qualification'}
                executable = 'python3'
                expected_image = 'fixture-image'
                if use_reference:
                    executable = '/opt/alpine/usr/python3'
                    expected_image = reference_image
                    env['PYTHONHOME'] = '/opt/alpine/usr'
                    selected_loader = self.target.musl_loader
                    loader_config = f'ld-musl-{self.target.machine}.path'
                    expected.update({
                        '/opt/alpine': runtime, selected_loader: runtime / 'lib' / Path(selected_loader).name,
                        f'/etc/{loader_config}': runtime / 'etc' / loader_config,
                        '/usr/bin/make': runtime / 'usr/make',
                    })
                else:
                    self.assertEqual((prefix / 'bin/ctest').readlink(), Path('cmake'))
                    self.assertEqual({entry.name for entry in prefix.iterdir()}, {'bin'})
                    if suite == 'graph':
                        self.assertEqual({entry.name for entry in work.iterdir()}, {'relocated cmake'})
                self.assertEqual(paths, expected)
                self.assertEqual((prefix / 'bin/cmake').read_bytes(), label.encode())
                self.assertEqual((image, command), (expected_image, [executable, '/suite/run.py']))
                self.assertEqual(options, {
                    'target': self.target, 'env': env, 'workdir': '/qualification', 'timeout': 3600,
                    'read_only': frozenset(paths) - {'/qualification'},
                })
                if suite == 'graph':
                    for name in files:
                        output = work / 'graph suite' / name
                        output.parent.mkdir(parents=True, exist_ok=True)
                        changed_file = changed_graph and not use_reference and name == 'ninja build/build.ninja'
                        graph = 'candidate graph' if changed_file else 'shared graph'
                        output.write_text(f'first\n\n{graph}\nlast\n')
                return sandbox.SealedResult(0, 'qualification: passed\n', '', 'none', {})

            with (
                self.subTest(changed=changed),
                patch.object(sandbox, 'copy_reference_runtime', side_effect=copy_runtime) as copy,
                patch.object(sandbox, 'run_sealed', side_effect=run) as sealed,
                redirect_stdout(io.StringIO()) as stdout,
            ):
                qualify.parity(root=self.root, phase=self.phase, image='fixture-image', target=self.target)
            copy.assert_called_once()
            self.assertEqual(sealed.call_count, 4)
            self.assertEqual(list((self.root / '.work/tmp').iterdir()), [])
            child_log = ''.join(f'{label} {suite}: qualification: passed\n' for suite, label in calls)
            self.assertEqual(stdout.getvalue().rstrip('\n'), (
                f'{child_log}parity: compared 4 outputs; {int(changed)} differ and are recorded in {self.report}'
            ))
            difference = (
                '### ninja build/build.ninja\n\n```diff\n'
                '--- reference/ninja build/build.ninja\n+++ candidate/ninja build/build.ninja\n'
                '@@ -1,4 +1,4 @@\n first\n\n-shared graph\n+candidate graph\n last\n```'
            )
            content = difference if changed else 'No differences were observed in the compared outputs.'
            self.assertEqual(self.report.read_text(), self.original.replace('stale results', content))

    def test_admits_only_a_single_reference_directory_and_leaves_report_on_failure(self) -> None:
        archives: tuple[list[tuple[str, bytes | None, str | None]], ...] = (
            [], [('kitware', b'not a directory', None)], [('one', None, None), ('two', None, None)],
        )
        for invalid in archives:
            with self.subTest(invalid=invalid), patch.object(sandbox, 'copy_reference_runtime') as copy:
                self.cache_reference(invalid)
                with self.assertRaisesRegex(qualify.QualificationError, '^reference CMake archive has an invalid layout$'):
                    qualify.parity(root=self.root, phase=self.phase, image='fixture-image', target=self.target)
                copy.assert_not_called()
                self.assertEqual(self.report.read_text(), self.original)
                self.assertEqual(list((self.root / '.work/tmp').iterdir()), [])

    def test_rejects_a_missing_reference_before_creating_the_runtime(self) -> None:
        write_lock(self.sources, [])
        with (
            patch.object(sandbox, 'copy_reference_runtime') as copy,
            self.assertRaisesRegex(qualify.QualificationError, '^reference CMake is missing from the source lock$'),
        ):
            qualify.parity(root=self.root, phase=self.phase, image='fixture-image', target=self.target)
        copy.assert_not_called()
        self.assertEqual(self.report.read_text(), self.original)

    def test_unqualified_children_cannot_publish_a_report(self) -> None:
        self.cache_reference([('kitware/bin/cmake', b'reference', None)])
        for code, stdout in ((7, 'qualification: passed\n'), (0, 'unrelated output\n')):
            with (
                self.subTest(code=code),
                patch.object(sandbox, 'copy_reference_runtime'),
                patch.object(sandbox, 'run_sealed', return_value=sandbox.SealedResult(code, stdout, 'failed', 'none', {})) as sealed,
                redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(qualify.QualificationError, rf'^candidate graph qualification failed \({code}\):\nfailed$'),
            ):
                qualify.parity(root=self.root, phase=self.phase, image='fixture-image', target=self.target)
            sealed.assert_called_once()
            self.assertEqual(self.report.read_text(), self.original)
            self.assertEqual(list((self.root / '.work/tmp').iterdir()), [])
