import unittest
import os
import sys

# Ensure src directory is in path for imports if running tests from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from diff_utils import generate_diff

class TestDiffUtils(unittest.TestCase):

    def test_generate_diff_identical_text(self):
        text = "line1\nline2\nline3\n"
        diff = generate_diff(text, text)
        self.assertEqual(diff, [], "Diff of identical texts should be empty.")

    def test_generate_diff_simple_addition(self):
        original = "line1\nline3\n"
        new = "line1\nline2_added\nline3\n"
        diff = generate_diff(original, new, fromfile="original.txt", tofile="new.txt")

        self.assertTrue(any("--- original.txt" in line for line in diff))
        self.assertTrue(any("+++ new.txt" in line for line in diff))
        self.assertTrue(any("+line2_added" in line for line in diff))
        # Check line numbers in hunk header, e.g., @@ -1,2 +1,3 @@
        self.assertTrue(any("@@ -1,2 +1,3 @@" in line for line in diff), f"Diff: {diff}")


    def test_generate_diff_simple_deletion(self):
        original = "line1\nline2_to_delete\nline3\n"
        new = "line1\nline3\n"
        diff = generate_diff(original, new, fromfile="a/original", tofile="b/new")

        self.assertTrue(any("--- a/original" in line for line in diff))
        self.assertTrue(any("+++ b/new" in line for line in diff))
        self.assertTrue(any("-line2_to_delete" in line for line in diff))
        self.assertTrue(any("@@ -1,3 +1,2 @@" in line for line in diff), f"Diff: {diff}")

    def test_generate_diff_simple_modification(self):
        original = "line1\nline_to_change\nline3\n"
        new = "line1\nline_was_changed\nline3\n"
        diff = generate_diff(original, new) # Test with default filenames

        self.assertTrue(any("--- original" in line for line in diff)) # Default filename
        self.assertTrue(any("+++ new" in line for line in diff))      # Default filename
        self.assertTrue(any("-line_to_change" in line for line in diff))
        self.assertTrue(any("+line_was_changed" in line for line in diff))
        self.assertTrue(any("@@ -1,3 +1,3 @@" in line for line in diff))

    def test_generate_diff_multiline_changes(self):
        original = "line1\ncommon_prefix_line2_original\nline3_original\nline4_common\nline5_original\n"
        new = "line1\ncommon_prefix_line2_new\nline3_new\nline4_common\nline5_new\n"
        diff = generate_diff(original, new, fromfile="ver1.py", tofile="ver2.py")

        self.assertTrue(any("--- ver1.py" in line for line in diff))
        self.assertTrue(any("+++ ver2.py" in line for line in diff))
        self.assertTrue(any("-common_prefix_line2_original" in line for line in diff))
        self.assertTrue(any("+common_prefix_line2_new" in line for line in diff))
        self.assertTrue(any("-line3_original" in line for line in diff))
        self.assertTrue(any("+line3_new" in line for line in diff))
        self.assertTrue(any("-line5_original" in line for line in diff))
        self.assertTrue(any("+line5_new" in line for line in diff))
        # Example: @@ -1,5 +1,5 @@
        self.assertTrue(any(line.startswith("@@ ") for line in diff))


    def test_generate_diff_no_trailing_newline_handling(self):
        original = "line1\nline2" # No trailing newline
        new_added_line = "line1\nline2\nline3_added" # line3 added, line2 now has newline implicitly

        diff = generate_diff(original, new_added_line)
        # difflib adds newline to lines for diffing if missing, then indicates original lack of newline
        self.assertTrue(any(r"-line2" in line for line in diff))
        self.assertTrue(any(r"\ No newline at end of file" in line for line in diff if line.startswith("-") or line.startswith(" ")), f"Diff: {diff}")
        self.assertTrue(any("+line2" in line for line in diff)) # line2 is now part of the change context
        self.assertTrue(any("+line3_added" in line for line in diff))


    def test_generate_diff_trailing_newline_added(self):
        original = "line1\nline2"
        new = "line1\nline2\n" # Trailing newline added
        diff = generate_diff(original, new)

        # Expect something like:
        # --- original
        # +++ new
        # @@ -1,2 +1,2 @@
        #  line1
        # -line2
        # \ No newline at end of file
        # +line2
        self.assertTrue(any(r"-line2" in line and r"\ No newline at end of file" not in line for line in diff)) # The line itself
        self.assertTrue(any(r"\ No newline at end of file" in line for line in diff if line.startswith("-") or line.startswith(" "))) # The marker for original
        self.assertTrue(any(r"+line2" in line and r"\ No newline at end of file" not in line for line in diff)) # The new line with newline
        # Ensure the new file doesn't have the "No newline" marker if it ends with one
        self.assertFalse(any(r"\ No newline at end of file" in line for line in diff if line.startswith("+")))


    def test_generate_diff_trailing_newline_removed(self):
        original = "line1\nline2\n"
        new = "line1\nline2" # Trailing newline removed
        diff = generate_diff(original, new)

        # Expect something like:
        # --- original
        # +++ new
        # @@ -1,2 +1,2 @@
        #  line1
        # -line2
        # +line2
        # \ No newline at end of file
        self.assertTrue(any(r"-line2" in line and r"\ No newline at end of file" not in line for line in diff))
        self.assertTrue(any(r"+line2" in line and r"\ No newline at end of file" not in line for line in diff))
        self.assertTrue(any(r"\ No newline at end of file" in line for line in diff if line.startswith("+") or line.startswith(" ")))


    def test_generate_diff_empty_original(self):
        original = ""
        new = "line1\nline2\n"
        diff = generate_diff(original, new)
        self.assertTrue(any("@@ -0,0 +1,2 @@" in line for line in diff))
        self.assertTrue(any("+line1" in line for line in diff))
        self.assertTrue(any("+line2" in line for line in diff))

    def test_generate_diff_empty_new(self):
        original = "line1\nline2\n"
        new = ""
        diff = generate_diff(original, new)
        self.assertTrue(any("@@ -1,2 +0,0 @@" in line for line in diff))
        self.assertTrue(any("-line1" in line for line in diff))
        self.assertTrue(any("-line2" in line for line in diff))

    def test_generate_diff_both_empty(self):
        original = ""
        new = ""
        diff = generate_diff(original, new)
        self.assertEqual(diff, [], "Diff of two empty strings should be empty.")

if __name__ == '__main__':
    unittest.main()
