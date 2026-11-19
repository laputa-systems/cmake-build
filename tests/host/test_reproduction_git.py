import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from buildsys import package, reproduce


class ReproduceTest(unittest.TestCase):
    def test_two_clean_builds_keep_only_the_base_worktree(self) -> None:
        self.check_attempts('identical', [])

    def test_reports_archive_and_checkout_path_differences(self) -> None:
        self.check_attempts('divergent', [
            'usr/bin/cmake: content differs',
            'usr/share/doc/cmake-build/artifact.json: content differs',
            'archive bytes differ',
            'build 1: executable contains its checkout path',
        ])

    def test_failed_second_build_removes_both_worktrees(self) -> None:
        self.check_attempts('failed build', [])

    def test_failed_cleanup_attempt_still_retires_the_other_worktree(self) -> None:
        self.check_attempts('cleanup failed', [])

    def check_attempts(self, scenario: str, differences: list[str]) -> None:
        target = 'aarch64-unknown-linux-musl'
        version = '4.4.5'
        with TemporaryDirectory(prefix='reproduction-git-') as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run([
                'git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                'commit', '--allow-empty', '-qm', 'test fixture',
            ], cwd=root, check=True)
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            work = root / '.work'
            cache = work / 'cache'
            cache.mkdir(parents=True)
            (cache / 'fixture').write_bytes(b'cached input')
            (cache / 'alias').symlink_to('fixture')
            phases = work / 'rust' / target / 'phases'
            for name in ('tools', 'vendor'):
                (phases / name).mkdir(parents=True)
                (phases / name / 'marker').write_text(name, encoding='utf-8')

            git = subprocess.run
            builds: list[Path] = []

            def command(arguments, *, cwd, check, env=None):
                self.assertFalse(check)
                if arguments[0] == 'git':
                    result = git(arguments, cwd=cwd, check=check, capture_output=True)
                    if scenario == 'cleanup failed' and arguments[1:3] == ['worktree', 'remove'] and Path(arguments[-1]).name == 'build-2':
                        return subprocess.CompletedProcess(arguments, 7)
                    return result
                self.assertEqual(arguments, [sys.executable, 'build.py', 'package', '--target', target])
                builds.append(cwd)
                local = cwd / '.work'
                assert env is not None
                self.assertEqual(env.get('TMPDIR'), str(local / 'tmp'))
                self.assertTrue((local / 'tmp').is_dir())
                self.assertEqual(os.stat(local / 'cache' / 'fixture').st_ino, os.stat(cache / 'fixture').st_ino)
                self.assertTrue((local / 'cache' / 'alias').is_symlink())
                for name in ('tools', 'vendor'):
                    marker_file = local / 'rust' / target / 'phases' / name / 'marker'
                    self.assertEqual(marker_file.read_text(encoding='utf-8'), name)
                    self.assertEqual(marker_file.stat().st_ino, (phases / name / 'marker').stat().st_ino)
                if scenario == 'failed build' and len(builds) == 2:
                    return subprocess.CompletedProcess(arguments, 7)
                stage = local / 'staged'
                (stage / 'bin').mkdir(parents=True)
                body = str(cwd).encode() if scenario == 'divergent' and len(builds) == 1 else b'fixture cmake'
                (stage / 'bin' / 'cmake').write_bytes(body)
                archive = local / 'artifacts' / target / f'cmake-{version}-{target}.tar.xz'
                package.create(stage, archive, {'target': target}, 0)
                return subprocess.CompletedProcess(arguments, 0)

            with patch.object(reproduce.subprocess, 'run', side_effect=command):
                if scenario == 'failed build':
                    with self.assertRaisesRegex(reproduce.ReproduceError, r'^clean build 2 failed \(7\)$'):
                        reproduce.run(root, target, version, commit)
                elif scenario == 'cleanup failed':
                    with self.assertRaisesRegex(reproduce.ReproduceError, r'could not remove reproduction worktree .*/build-2'):
                        reproduce.run(root, target, version, commit)
                else:
                    self.assertEqual(reproduce.run(root, target, version, commit), differences)

            self.assertEqual([checkout.name for checkout in builds], ['build-1', 'build-2'])
            self.assertTrue(all(not checkout.exists() for checkout in builds))
            self.assertEqual(list((work / 'wt').iterdir()), [])
            worktrees = subprocess.check_output(['git', 'worktree', 'list', '--porcelain'], cwd=root, text=True)
            self.assertEqual([line for line in worktrees.splitlines() if line.startswith('worktree ')], [f'worktree {root.resolve()}'])


if __name__ == '__main__':
    unittest.main()
