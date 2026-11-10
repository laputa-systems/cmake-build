from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import build
from helpers import workspace


class PackageCommandTests(unittest.TestCase):
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
