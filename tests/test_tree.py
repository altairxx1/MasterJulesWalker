import unittest
import os
import sys

# Ensure src directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from tree import FileTree # Assuming FileTree is in src/tree.py

class TestFileTree(unittest.TestCase):

    def setUp(self):
        self.mock_project_items = [
            ("README.md", "file"),
            ("src", "dir"),
            ("src/app.py", "file"),
            ("src/config.py", "file"),
            ("src/utils", "dir"),
            ("src/utils/helper.py", "file"),
            ("src/utils/network.py", "file"),
            ("tests", "dir"),
            ("tests/test_app.py", "file"),
            ("tests/test_config.py", "file"),
            ("requirements.txt", "file"),
            ("data", "dir"),
            ("data/logs", "dir"),
            ("data/logs/latest.log", "file"),
            ("data/images", "dir"),
            ("data/images/img1.png", "file"),
            ("data/images/img2.jpg", "file"),
        ]
        # Ensure items are sorted as get_project_files would (depth, type, name)
        self.mock_project_items.sort(key=lambda x: (x[0].count(os.sep), x[1] == 'file', x[0]))
        self.file_tree = FileTree(self.mock_project_items)

    def test_initialization(self):
        self.assertEqual(self.file_tree.filter_term, "")
        self.assertEqual(len(self.file_tree.filtered_project_items), len(self.mock_project_items))
        self.assertEqual(self.file_tree.filtered_project_items, self.mock_project_items)

    def test_set_filter_term_no_change(self):
        self.file_tree.set_filter_term("app")
        initial_filtered_items = list(self.file_tree.filtered_project_items)
        # Call again with same term
        self.file_tree.set_filter_term("app")
        self.assertEqual(self.file_tree.filtered_project_items, initial_filtered_items, "Setting same filter term should not change items.")

    def test_filter_matching_files_and_parents(self):
        self.file_tree.set_filter_term("app.py") # Matches src/app.py and tests/test_app.py

        # Expected: src, src/app.py, tests, tests/test_app.py
        # (Order as per master sort)
        expected_paths = {
            "src",
            "src/app.py",
            "tests",
            "tests/test_app.py"
        }
        filtered_paths = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths, expected_paths)

        # Check display lines count (can be more complex due to tree structure)
        # For this specific filter, all items are unique paths, so count should be 4
        self.assertEqual(self.file_tree.get_filtered_items_count(), 4)

    def test_filter_matching_directory_and_contents_and_parents(self):
        self.file_tree.set_filter_term("utils")
        # Matches src/utils (dir), src/utils/helper.py, src/utils/network.py
        # Parents: src
        expected_paths = {
            "src",
            "src/utils",
            "src/utils/helper.py",
            "src/utils/network.py"
        }
        filtered_paths = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths, expected_paths)
        self.assertEqual(self.file_tree.get_filtered_items_count(), 4)

    def test_filter_no_matches(self):
        self.file_tree.set_filter_term("nonexistentZZZ")
        self.assertEqual(self.file_tree.filtered_project_items, [])
        self.assertEqual(self.file_tree.get_filtered_items_count(), 0)
        display_lines = self.file_tree.get_display_lines()
        self.assertEqual(len(display_lines), 0)

    def test_filter_partial_match_case_insensitive(self):
        self.file_tree.set_filter_term("readme") # Should match README.md
        expected_paths = {"README.md"}
        filtered_paths = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths, expected_paths)

        self.file_tree.set_filter_term("CONF") # Should match src/config.py and tests/test_config.py
        expected_paths_conf = {"src", "src/config.py", "tests", "tests/test_config.py"}
        filtered_paths_conf = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths_conf, expected_paths_conf)

    def test_clear_filter(self):
        self.file_tree.set_filter_term("app")
        self.assertNotEqual(len(self.file_tree.filtered_project_items), len(self.mock_project_items))

        self.file_tree.set_filter_term("") # Clear filter
        self.assertEqual(len(self.file_tree.filtered_project_items), len(self.mock_project_items))
        self.assertEqual(self.file_tree.filtered_project_items, self.mock_project_items)

    def test_get_display_lines_structure_and_selection(self):
        # Test with a known small set to check structure
        simple_items = [("a", "dir"), ("a/b.txt", "file"), ("c.txt", "file")]
        simple_items.sort(key=lambda x: (x[0].count(os.sep), x[1] == 'file', x[0]))
        tree = FileTree(simple_items)

        # Select "a/b.txt"
        lines_with_paths = tree.get_display_lines(selected_item_path="a/b.txt")
        display_lines = [lp[0] for lp in lines_with_paths]

        # Expected:
        # a/
        # > └── b.txt  (or similar, glyphs depend on more complex logic not fully replicated here)
        # c.txt
        self.assertEqual(len(display_lines), 3)
        self.assertTrue(display_lines[0].strip().startswith("a/"))
        self.assertTrue(display_lines[1].strip().startswith("> ")) # Selection marker
        self.assertTrue("b.txt" in display_lines[1])
        self.assertTrue(display_lines[2].strip().startswith("c.txt"))

    def test_filter_then_get_display_lines(self):
        self.file_tree.set_filter_term("helper") # Matches src/utils/helper.py
        # Expected filtered: src, src/utils, src/utils/helper.py

        lines_with_paths = self.file_tree.get_display_lines(selected_item_path="src/utils/helper.py")
        display_lines = [lp[0] for lp in lines_with_paths]

        self.assertEqual(len(display_lines), 3)
        self.assertTrue(display_lines[0].strip().startswith("src/"))
        self.assertTrue("utils/" in display_lines[1])
        self.assertTrue("helper.py" in display_lines[2])
        self.assertTrue(display_lines[2].strip().startswith("> ")) # Selection

    def test_get_item_by_index_with_filter(self):
        self.file_tree.set_filter_term("app.py")
        # Expected filtered items sorted: src, src/app.py, tests, tests/test_app.py
        # (This order depends on the initial sort and preservation)

        # To verify, let's find the expected items in the master list first
        # and then assume they appear in the same relative order in filtered list.

        item0 = self.file_tree.get_item_by_index(0) # Should be "src"
        item1 = self.file_tree.get_item_by_index(1) # Should be "src/app.py"

        self.assertIsNotNone(item0)
        self.assertEqual(item0[0], "src")
        self.assertIsNotNone(item1)
        self.assertEqual(item1[0], "src/app.py")

        self.assertIsNone(self.file_tree.get_item_by_index(100)) # Out of bounds
        self.assertIsNone(self.file_tree.get_item_by_index(-1))

    def test_filter_multiple_levels_parent_inclusion(self):
        self.file_tree.set_filter_term("latest.log")
        # Matches: data/logs/latest.log
        # Parents: data, data/logs
        expected_paths = {
            "data",
            "data/logs",
            "data/logs/latest.log"
        }
        filtered_paths = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths, expected_paths)

    def test_filter_term_is_directory_name(self):
        self.file_tree.set_filter_term("images")
        # Matches: data/images (dir), data/images/img1.png, data/images/img2.jpg
        # Parents: data
        expected_paths = {
            "data",
            "data/images",
            "data/images/img1.png",
            "data/images/img2.jpg"
        }
        filtered_paths = {item[0] for item in self.file_tree.filtered_project_items}
        self.assertEqual(filtered_paths, expected_paths)

if __name__ == '__main__':
    unittest.main()
```
