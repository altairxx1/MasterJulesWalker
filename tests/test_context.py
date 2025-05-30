import unittest
import os
from unittest.mock import patch, mock_open, MagicMock

# Assuming src.context is the module to test
from src.context import ContextManager

# Define constants for testing. These will be used to patch the module-level constants in src.context
TEST_MAX_FILE_SIZE_BYTES = 1000
TEST_MAX_CONTEXT_FILES = 3
TEST_MAX_TOTAL_CONTEXT_SIZE_BYTES = 2500

class TestContextManager(unittest.TestCase):

    def setUp(self):
        self.project_root = os.path.abspath("test_project_dir_for_context_tests")
        if not os.path.exists(self.project_root):
            os.makedirs(self.project_root)

        # Patch module-level constants in src.context
        self.patch_mfsb = patch('src.context.MAX_FILE_SIZE_BYTES', TEST_MAX_FILE_SIZE_BYTES)
        self.patch_mcf = patch('src.context.MAX_CONTEXT_FILES', TEST_MAX_CONTEXT_FILES)
        self.patch_mtcsb = patch('src.context.MAX_TOTAL_CONTEXT_SIZE_BYTES', TEST_MAX_TOTAL_CONTEXT_SIZE_BYTES)

        self.mock_mfsb = self.patch_mfsb.start()
        self.mock_mcf = self.patch_mcf.start()
        self.mock_mtcsb = self.patch_mtcsb.start()

        self.manager = ContextManager(project_root=self.project_root)
        self.manager.clear_errors() # Ensure clean error state for each test

    def tearDown(self):
        self.patch_mfsb.stop()
        self.patch_mcf.stop()
        self.patch_mtcsb.stop()
        if os.path.exists(self.project_root):
            # Basic cleanup
            for root_dir, dirs, files_in_dir in os.walk(self.project_root, topdown=False):
                for name in files_in_dir:
                    os.remove(os.path.join(root_dir, name))
                for name in dirs:
                    os.rmdir(os.path.join(root_dir, name))
            if os.path.exists(self.project_root): # check if rmdir is needed
                 os.rmdir(self.project_root)


    def test_initialization(self):
        self.assertEqual(self.manager.project_root, self.project_root)
        self.assertEqual(self.manager.context_files, [])
        self.assertEqual(self.manager.context_content, {})
        self.assertEqual(self.manager.current_context_size_bytes, 0)
        self.assertIsNone(self.manager.get_latest_error())

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="file content")
    def test_add_file_success(self, mock_file_open, mock_getsize, mock_isfile):
        mock_isfile.return_value = True
        mock_getsize.return_value = 12

        file_path_relative = "src/main.py"
        expected_abs_path = os.path.join(self.manager.project_root, file_path_relative)

        result = self.manager.add_file(file_path_relative)

        self.assertTrue(result)
        self.assertIn("Added", self.manager.get_latest_error())
        self.assertIn(expected_abs_path, self.manager.context_files)
        self.assertIn(expected_abs_path, self.manager.context_content)
        self.assertEqual(self.manager.context_content[expected_abs_path], "file content")
        self.assertEqual(self.manager.current_context_size_bytes, 12)
        mock_file_open.assert_called_once_with(expected_abs_path, 'r', encoding='utf-8')
        self.assertEqual(mock_getsize.call_count, 2)


    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="file content")
    def test_add_file_already_in_context(self, mock_file_open, mock_getsize, mock_isfile):
        mock_isfile.return_value = True
        mock_getsize.return_value = 12
        file_path_relative = "src/main.py"
        expected_abs_path = os.path.join(self.manager.project_root, file_path_relative)

        self.manager.add_file(file_path_relative)
        self.manager.clear_errors()
        result = self.manager.add_file(file_path_relative)

        self.assertFalse(result)
        self.assertIn("already in context", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 1)
        self.assertEqual(self.manager.current_context_size_bytes, 12)
        mock_file_open.assert_called_once_with(expected_abs_path, 'r', encoding='utf-8')
        self.assertEqual(mock_getsize.call_count, 2)


    @patch('os.path.isfile')
    def test_add_file_does_not_exist(self, mock_isfile):
        mock_isfile.return_value = False
        file_path_relative = "src/ghost.py"
        result = self.manager.add_file(file_path_relative)

        self.assertFalse(result)
        self.assertIn("File not found", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 0)

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    def test_add_file_too_large(self, mock_getsize, mock_isfile):
        mock_getsize.return_value = TEST_MAX_FILE_SIZE_BYTES + 1
        file_path = "src/large_file.bin"
        result = self.manager.add_file(file_path)

        self.assertFalse(result)
        self.assertIn("exceeds max size", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 0)

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="content")
    def test_add_file_max_context_files_reached(self, mock_file_open, mock_getsize, mock_isfile):
        mock_getsize.return_value = 10

        for i in range(TEST_MAX_CONTEXT_FILES):
            self.assertTrue(self.manager.add_file(f"src/file{i}.txt"), f"Failed to add file{i}")
            self.manager.clear_errors()

        self.assertEqual(len(self.manager.context_files), TEST_MAX_CONTEXT_FILES)

        result = self.manager.add_file("src/another_file.txt")

        self.assertFalse(result)
        self.assertIn("Cannot add more than", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), TEST_MAX_CONTEXT_FILES)

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_add_file_total_size_exceeded(self, mock_file_open_method, mock_getsize_method, mock_isfile):
        # Using TEST_MAX_FILE_SIZE_BYTES = 1000, TEST_MAX_TOTAL_CONTEXT_SIZE_BYTES = 2500
        file1_rel = "src/file1.txt"; file1_size = 900; file1_content = "a" * file1_size
        file1_abs_path = os.path.join(self.manager.project_root, file1_rel)

        file2_rel = "src/file2.txt"; file2_size = 900; file2_content = "b" * file2_size
        file2_abs_path = os.path.join(self.manager.project_root, file2_rel)

        file3_rel = "src/file3.txt"; file3_size = 800; file3_content = "c" * file3_size
        file3_abs_path = os.path.join(self.manager.project_root, file3_rel)

        def getsize_side_effect(path):
            if path == file1_abs_path: return file1_size
            if path == file2_abs_path: return file2_size
            if path == file3_abs_path: return file3_size
            return 50
        mock_getsize_method.side_effect = getsize_side_effect

        def open_side_effect(path, *args, **kwargs):
            if path == file1_abs_path: return mock_open(read_data=file1_content).return_value
            if path == file2_abs_path: return mock_open(read_data=file2_content).return_value
            if path == file3_abs_path: return mock_open(read_data=file3_content).return_value
            return mock_open(read_data="default content").return_value
        mock_file_open_method.side_effect = open_side_effect

        self.assertTrue(self.manager.add_file(file1_rel), "Adding file1 failed")
        self.assertEqual(self.manager.current_context_size_bytes, file1_size)
        self.manager.clear_errors()

        self.assertTrue(self.manager.add_file(file2_rel), "Adding file2 failed")
        self.assertEqual(self.manager.current_context_size_bytes, file1_size + file2_size) # 1800
        self.manager.clear_errors()

        result = self.manager.add_file(file3_rel) # 1800 + 800 = 2600, exceeds 2500

        self.assertFalse(result, "Adding file3 should have failed due to total size")
        self.assertIn("would exceed total context size", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 2) # Only first two files
        self.assertEqual(self.manager.current_context_size_bytes, file1_size + file2_size)

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="content")
    def test_add_file_clears_error_on_success(self, mock_file_open, mock_getsize, mock_isfile):
        mock_isfile.return_value = False
        self.manager.add_file("non_existent.txt")
        self.assertIn("File not found", self.manager.get_latest_error())

        mock_isfile.return_value = True
        mock_getsize.return_value = 10
        self.manager.add_file("existent.txt")

        latest_message = self.manager.get_latest_error()
        self.assertIsNotNone(latest_message)
        self.assertIn("Added existent.txt", latest_message)
        self.assertEqual(len(self.manager.error_messages), 1)


    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="file content")
    def test_remove_file_success(self, mock_file_open_add, mock_getsize_method, mock_isfile_add):
        mock_getsize_method.return_value = 12
        file_path_rel = "src/main.py"
        expected_abs_path = os.path.join(self.manager.project_root, file_path_rel)

        self.manager.add_file(file_path_rel)
        self.manager.clear_errors()

        result = self.manager.remove_file(file_path_rel)
        self.assertTrue(result)
        self.assertIn("Removed", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 0)
        self.assertNotIn(expected_abs_path, self.manager.context_content)
        self.assertEqual(self.manager.current_context_size_bytes, 0)

    def test_remove_file_not_in_context(self):
        result = self.manager.remove_file("src/not_added.py")
        self.assertFalse(result)
        self.assertIn("not found in context", self.manager.get_latest_error())
        self.assertEqual(len(self.manager.context_files), 0)

    def test_get_context_string_empty(self):
        self.assertEqual(self.manager.get_context_string(), "No files currently in context.")

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_context_string_multiple_files(self, mock_file_open_method, mock_getsize_method, mock_isfile_method):
        file1_rel = "src/file1.py"
        file1_abs = os.path.join(self.manager.project_root, file1_rel)
        file1_content = "content of file1"

        file2_rel = "lib/mod.rs"
        file2_abs = os.path.join(self.manager.project_root, file2_rel)
        file2_content = "mod content;"

        def getsize_side_effect(path):
            if path == file1_abs: return len(file1_content)
            if path == file2_abs: return len(file2_content)
            return 0
        mock_getsize_method.side_effect = getsize_side_effect

        def open_side_effect(path, mode='r', encoding=None):
            if path == file1_abs:
                return mock_open(read_data=file1_content).return_value
            elif path == file2_abs:
                return mock_open(read_data=file2_content).return_value
            raise FileNotFoundError(path)
        mock_file_open_method.side_effect = open_side_effect

        self.manager.add_file(file1_rel)
        self.manager.add_file(file2_rel)

        expected_string = "Current context includes the following files:\n\n"
        expected_string += f"--- Context File: {file1_rel} ---\n"
        expected_string += f"{file1_content}\n"
        expected_string += f"--- End of Context File: {file1_rel} ---\n\n"
        expected_string += f"--- Context File: {file2_rel} ---\n"
        expected_string += f"{file2_content}\n"
        expected_string += f"--- End of Context File: {file2_rel} ---\n\n"

        total_size = len(file1_content) + len(file2_content)
        expected_string += (f"Total files in context: 2.\n"
                             f"Total context size: {total_size // 1024}KB "
                             f"of {TEST_MAX_TOTAL_CONTEXT_SIZE_BYTES // 1024}KB limit.\n")

        self.assertEqual(self.manager.get_context_string(), expected_string)

    def test_get_context_summary_empty(self):
        self.assertEqual(self.manager.get_context_summary(), [])

    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data="content")
    def test_get_context_summary_multiple_files(self, mock_file_open_add, mock_getsize_method, mock_isfile_add):
        file1_rel = "src/file1.py"
        file1_abs = os.path.join(self.manager.project_root, file1_rel)
        file1_size_bytes = 500

        file2_rel = "lib/mod.rs"
        file2_abs = os.path.join(self.manager.project_root, file2_rel)
        file2_size_bytes = 300

        def getsize_side_effect_summary(path):
            if path == file1_abs: return file1_size_bytes
            if path == file2_abs: return file2_size_bytes
            return 0
        mock_getsize_method.side_effect = getsize_side_effect_summary

        self.manager.add_file(file1_rel)
        self.manager.add_file(file2_rel)

        summary = self.manager.get_context_summary()
        expected_summary = [
            f"{file1_rel} ({file1_size_bytes // 1024}KB)",
            f"{file2_rel} ({file2_size_bytes // 1024}KB)"
        ]
        self.assertEqual(summary, expected_summary)

    def test_get_latest_error(self):
        self.assertIsNone(self.manager.get_latest_error())

        error_message_to_set = "Test error"
        self.manager.error_messages.append(error_message_to_set)

        self.assertEqual(self.manager.get_latest_error(), error_message_to_set)

        self.manager.clear_errors()
        self.assertIsNone(self.manager.get_latest_error())


if __name__ == '__main__':
    unittest.main()
