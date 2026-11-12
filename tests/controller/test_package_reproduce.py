import unittest

from helpers import workspace

from buildsys import reproduce


class ReproduceTest(unittest.TestCase):
    def test_reports_content_modes_types_and_link_targets(self) -> None:
        with workspace() as root:
            first, second = root / 'first', root / 'second'
            first.mkdir()
            second.mkdir()
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
            self.assertEqual(set(reproduce.compare_trees(first, second)), {
                'content: content differs', 'mode: mode differs', 'link: symlink target differs', 'kind: type differs',
            })
            self.assertEqual(reproduce.compare_trees(first, first), [])


if __name__ == '__main__':
    unittest.main()
