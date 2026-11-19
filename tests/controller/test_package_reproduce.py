import socket
import unittest
from contextlib import chdir

from helpers import workspace

from buildsys import reproduce


class ReproduceTreeTest(unittest.TestCase):
    def test_reports_content_modes_types_and_link_targets(self) -> None:
        with workspace() as root:
            first, second = root / 'first', root / 'second'
            first.mkdir()
            second.mkdir()
            (first / 'a-without-second').touch()
            (second / 'b-without-first').touch()
            with chdir(root), socket.socket(socket.AF_UNIX) as left, socket.socket(socket.AF_UNIX) as right:
                left.bind('first/channel')
                right.bind('second/channel')
            (first / 'content').write_text('first')
            (second / 'content').write_text('second')
            (first / 'mode').write_text('same')
            (second / 'mode').write_text('same')
            (first / 'mode').chmod(0o644)
            (second / 'mode').chmod(0o755)
            (first / 'link').symlink_to('content')
            (second / 'link').symlink_to('mode')
            (first / 'kind').mkdir()
            (second / 'kind').write_text('file')
            self.assertEqual(reproduce.compare_trees(first, second), [
                'a-without-second: missing from second build',
                'b-without-first: missing from first build',
                'channel: unsupported file type',
                'content: content differs',
                'kind: type differs',
                'link: symlink target differs',
                'mode: mode differs',
            ])
            (first / 'channel').unlink()
            self.assertEqual(reproduce.compare_trees(first, first), [])


if __name__ == '__main__':
    unittest.main()
