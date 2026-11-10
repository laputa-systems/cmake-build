from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import build
from buildsys import package
from helpers import workspace


class PackageCommandTests(unittest.TestCase):
    def test_qualify_runs_project_and_upstream_suites_against_the_extracted_archive(self) -> None:
        target = 'x86_64-unknown-linux-musl'
        commit = 'a' * 40
        with workspace() as root:
            work = root / 'work'
            directory = work / 'artifacts' / target
            directory.mkdir(parents=True)
            stage = root / 'stage'
            (stage / 'bin').mkdir(parents=True)
            (stage / 'bin/cmake').write_bytes(b'packaged candidate')
            archive = directory / f'cmake-4.4.5-{target}.tar.xz'
            package.create(stage, archive, {'target': 'fixture'}, 1)
            (directory / 'candidate.json').write_text(json.dumps({
                'archive': archive.name, 'commit': commit, 'size': archive.stat().st_size,
                'sha256': package.digest(archive),
            }))
            (root / 'release-budgets.json').write_text(json.dumps({'schema_version': 2, 'targets': {target: {
                'metrics': {name: {'value': 100000, 'allowed_regression': 0}
                            for name in ('executable_bytes', 'unpacked_bytes', 'archive_bytes')}
            }}}))
            (root / 'docs').mkdir()
            (root / 'docs/qualification.md').write_text(f'## Latest upstream subset: {target}\n\nExecuted one test.\n')
            seen = []
            def projects(*, root, phase, image, target):
                seen.append(('projects', (phase / 'bin/cmake').read_bytes()))
            def upstream(*, root, phase, image, target):
                seen.append(('upstream', (phase / 'bin/cmake').read_bytes()))
            with patch.object(build, 'ROOT', root), patch.object(build, 'WORK', work), \
                    patch.object(build, 'load_sources', return_value=[SimpleNamespace(name='cmake-source', version='4.4.5')]), \
                    patch.object(build, '_source_commit', return_value=commit), \
                    patch.object(build, 'test_command'), patch.object(build, 'load_bootstrap'), \
                    patch.object(build.sandbox, 'image_tag', return_value='image'), \
                    patch.object(build.qualify, 'projects', side_effect=projects), \
                    patch.object(build.qualify, 'upstream', side_effect=upstream), \
                    patch.object(build.qualify, 'basic'), patch.object(build.qualify, 'parity'), \
                    patch.object(build.qualify, 'network'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build.qualify_command(argparse.Namespace(target=target)), 0)
            self.assertEqual(seen, [('projects', b'packaged candidate'), ('upstream', b'packaged candidate')])

    def test_qualify_rejects_tampered_archive_before_running_suites(self) -> None:
        target = 'x86_64-unknown-linux-musl'
        commit = 'a' * 40
        with workspace() as root:
            directory = root / 'artifacts' / target
            directory.mkdir(parents=True)
            archive = directory / f'cmake-4.4.5-{target}.tar.xz'
            archive.write_bytes(b'archive')
            (directory / 'candidate.json').write_text(json.dumps({
                'archive': archive.name, 'commit': commit, 'size': 7, 'sha256': '0' * 64,
            }))
            with patch.object(build, 'WORK', root), \
                    patch.object(build, 'load_sources', return_value=[SimpleNamespace(name='cmake-source', version='4.4.5')]), \
                    patch.object(build, '_source_commit', return_value=commit), \
                    patch.object(build, 'test_command') as suite, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    build.qualify_command(argparse.Namespace(target=target))
                suite.assert_not_called()


if __name__ == '__main__':
    unittest.main()
