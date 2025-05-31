import unittest
import os
from unittest.mock import patch, mock_open, MagicMock

from src.viewer import FileViewer

class TestFileViewer(unittest.TestCase):

    def setUp(self):
        # Can be minimal if most tests mock 'open' directly.
        # This setup could be used for tests that don't involve file I/O directly,
        # or where the FileViewer instance is created with already mocked data.
        pass

    def tearDown(self):
        # If any tests create actual files for the viewer, clean them up here.
        # For now, assuming all file operations are mocked.
        pass

    # --- Tests for _load_file (indirectly via __init__) ---

    def test_load_file_success(self):
        mock_file_content = "\n".join([f"Line {i}" for i in range(10)])
        # mock_open correctly simulates readlines() and iteration for line counting
        with patch('builtins.open', mock_open(read_data=mock_file_content)) as mo:
            viewer = FileViewer("dummy.txt")
            self.assertEqual(viewer.total_lines, 10, "Total lines should be 10")
            self.assertIsNone(viewer.error_message, "Error message should be None on success")
            # Check if file was rewound - mock_open's seek is a MagicMock
            # The actual implementation of FileViewer calls seek(0) after counting.
            if viewer.total_lines > 0 : # seek is only called if total_lines > 0
                 mo.return_value.seek.assert_called_with(0)


    def test_load_file_not_found(self):
        with patch('builtins.open', side_effect=FileNotFoundError("File not here")) as mock_builtin_open:
            viewer = FileViewer("nonexistent.txt")
            self.assertIsNotNone(viewer.error_message, "Error message should be set for FileNotFoundError")
            self.assertIn("File not here", viewer.error_message, "Error message content mismatch")
            self.assertIn("Error loading file", viewer.error_message) # Check generic prefix
            self.assertEqual(viewer.total_lines, 0, "Total lines should be 0 on error")

    def test_load_empty_file(self):
        with patch('builtins.open', mock_open(read_data="")) as mo:
            viewer = FileViewer("empty.txt")
            self.assertEqual(viewer.total_lines, 0, "Total lines should be 0 for an empty file")
            self.assertIsNone(viewer.error_message, "Error message should be None for an empty file")
            # In FileViewer._load_file, seek(0) is only called if total_lines > 0.
            mo.return_value.seek.assert_not_called()

    # --- Tests for get_display_lines ---

    def test_get_display_lines_basic(self):
        mock_lines = [f"Line content {i}" for i in range(20)]
        mock_file_content = "\n".join(mock_lines)

        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            viewer = FileViewer("dummy.txt")
            self.assertEqual(viewer.total_lines, 20)

        viewer.top_line_num = 5 # User has scrolled, top_line_num is 0-indexed
        display_lines = viewer.get_display_lines(num_display_lines=10)

        self.assertEqual(len(display_lines), 10)
        # Line numbers in display are 1-indexed. "Line content 5" is at 0-indexed 5.
        # So it should be displayed as "   6 Line content 5"
        self.assertTrue(display_lines[0].strip().startswith("6"), f"First line should be 6, got: {display_lines[0]}")
        self.assertIn("Line content 5", display_lines[0])

        # The 10th line displayed (index 9) started from top_line_num 5 (0-indexed)
        # So it's line number 5+9 = 14 (0-indexed), which is "Line content 14"
        # Displayed as "  15 Line content 14"
        self.assertTrue(display_lines[9].strip().startswith("15"), f"Last line should be 15, got: {display_lines[9]}")
        self.assertIn("Line content 14", display_lines[9])

    def test_get_display_lines_less_than_total_and_at_top(self):
        mock_lines = [f"Line {i}" for i in range(5)]
        mock_file_content = "\n".join(mock_lines)
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            viewer = FileViewer("dummy.txt")
            self.assertEqual(viewer.total_lines, 5)

        # Request more lines than available
        display_lines = viewer.get_display_lines(num_display_lines=10)
        self.assertEqual(len(display_lines), 5, "Should return all available lines if less than requested")
        self.assertEqual(viewer.top_line_num, 0, "top_line_num should be 0 if total lines < display_height")
        self.assertIn("Line 0", display_lines[0]) # "   1 Line 0"
        self.assertIn("Line 4", display_lines[4]) # "   5 Line 4"

    def test_get_display_lines_empty_file(self):
        with patch('builtins.open', mock_open(read_data="")):
            viewer = FileViewer("empty.txt")
            self.assertEqual(viewer.total_lines, 0)

        display_lines = viewer.get_display_lines(10)
        self.assertEqual(display_lines, ["(Empty File)"])

    def test_get_display_lines_error_state(self):
        with patch('builtins.open', side_effect=IOError("Permissions error")):
            viewer = FileViewer("no_access.txt")
        self.assertIsNotNone(viewer.error_message)
        lines = viewer.get_display_lines(10)
        self.assertEqual(len(lines), 1)
        self.assertTrue("Permissions error" in lines[0])


    # --- Tests for scroll_to_line ---

    def _setup_viewer_for_scroll_tests(self, num_lines):
        # This helper avoids repeatedly patching 'open' for scroll tests
        # by directly setting total_lines and mocking the file_handle if needed.
        viewer = FileViewer("dummy_scroll_test.txt") # Initial open might be real or need mock
        viewer.total_lines = num_lines
        # Mock the file_handle to prevent actual I/O if get_display_lines were called by scroll_to_line
        # (it's not, but good for isolation if behavior changes)
        viewer.file_handle = MagicMock()
        viewer.error_message = None # Ensure no error state
        return viewer

    def test_scroll_to_line_middle(self):
        viewer = self._setup_viewer_for_scroll_tests(100)
        display_height = 20
        target_line = 50 # 1-indexed

        viewer.scroll_to_line(line_number=target_line, display_height=display_height)

        # Expected logic:
        # target_line_0_indexed = 49
        # desired_offset_from_top = min(max(2, 20 // 3), 19) = min(max(2,6), 19) = 6
        # new_top_line = max(0, 49 - 6) = 43
        # max_possible_top_line = 100 - 20 = 80
        # self.top_line_num = min(43, 80) = 43
        self.assertEqual(viewer.top_line_num, 43)

    def test_scroll_to_line_near_start(self):
        viewer = self._setup_viewer_for_scroll_tests(100)
        display_height = 20

        viewer.scroll_to_line(line_number=1, display_height=display_height)
        self.assertEqual(viewer.top_line_num, 0)

        viewer.scroll_to_line(line_number=5, display_height=display_height)
        # target_line_0_indexed = 4
        # desired_offset_from_top = 6
        # new_top_line = max(0, 4 - 6) = 0
        self.assertEqual(viewer.top_line_num, 0)

        viewer.scroll_to_line(line_number=8, display_height=display_height)
        # target_line_0_indexed = 7
        # desired_offset_from_top = 6
        # new_top_line = max(0, 7 - 6) = 1
        self.assertEqual(viewer.top_line_num, 1)


    def test_scroll_to_line_near_end(self):
        viewer = self._setup_viewer_for_scroll_tests(100)
        display_height = 20

        viewer.scroll_to_line(line_number=95, display_height=display_height)
        # target_line_0_indexed = 94
        # desired_offset_from_top = 6
        # new_top_line = max(0, 94 - 6) = 88
        # max_possible_top_line = 100 - 20 = 80
        # self.top_line_num = min(88, 80) = 80
        self.assertEqual(viewer.top_line_num, 80)

        viewer.scroll_to_line(line_number=100, display_height=display_height)
        # target_line_0_indexed = 99
        # new_top_line = max(0, 99 - 6) = 93
        # self.top_line_num = min(93, 80) = 80
        self.assertEqual(viewer.top_line_num, 80)


    def test_scroll_to_line_target_beyond_total(self):
        viewer = self._setup_viewer_for_scroll_tests(30)
        display_height = 20
        viewer.scroll_to_line(line_number=40, display_height=display_height) # Target beyond end
        # target_line_0_indexed = 39
        # new_top_line = max(0, 39 - 6) = 33 (offset = 6)
        # max_possible_top_line = 30 - 20 = 10
        # self.top_line_num = min(33, 10) = 10
        self.assertEqual(viewer.top_line_num, 10)

    def test_scroll_to_line_less_lines_than_display(self):
        viewer = self._setup_viewer_for_scroll_tests(10)
        display_height = 20
        viewer.scroll_to_line(line_number=5, display_height=display_height)
        # total_lines (10) <= display_height (20), so top_line_num should be 0
        self.assertEqual(viewer.top_line_num, 0)

    def test_scroll_to_line_zero_or_negative_target(self):
        viewer = self._setup_viewer_for_scroll_tests(100)
        display_height = 20

        viewer.scroll_to_line(line_number=0, display_height=display_height)
        self.assertEqual(viewer.top_line_num, 0)

        viewer.scroll_to_line(line_number=-5, display_height=display_height)
        self.assertEqual(viewer.top_line_num, 0)

    # --- Tests for scroll() method (boundary conditions) ---
    def test_scroll_boundaries(self):
        viewer = self._setup_viewer_for_scroll_tests(50)

        # Scroll up from top
        viewer.top_line_num = 0
        viewer.scroll('up', amount=10)
        self.assertEqual(viewer.top_line_num, 0)

        # Scroll down from bottom (max top_line_num is total_lines - 1)
        viewer.top_line_num = 49 # Last line is at the top
        viewer.scroll('down', amount=10)
        self.assertEqual(viewer.top_line_num, 49) # Cannot scroll further if last line is already top

        # Simulate a full view area to test page down correctly
        # If display_height = 10, and total_lines = 50
        # Max top_line_num for a full page is 50 - 10 = 40
        # But scroll() aims for `total_lines - 1` as max, so let's test that behavior.

        viewer.total_lines = 50
        viewer.top_line_num = 35
        viewer.scroll('pagedown', page_amount=10) # display_height = 10
        # current logic: min(35 + 10, 50 - 1) = min(45, 49) = 45
        self.assertEqual(viewer.top_line_num, 45)

        viewer.top_line_num = 45
        viewer.scroll('pagedown', page_amount=10)
        # min(45+10, 49) = min(55,49) = 49
        self.assertEqual(viewer.top_line_num, 49)

        viewer.top_line_num = 49
        viewer.scroll('pagedown', page_amount=10)
        # min(49+10, 49) = 49
        self.assertEqual(viewer.top_line_num, 49) # Stays at max

        # Page up from bottom
        viewer.top_line_num = 45
        viewer.scroll('pageup', page_amount=10)
        # max(0, 45 - 10) = 35
        self.assertEqual(viewer.top_line_num, 35)


if __name__ == '__main__':
    unittest.main()
