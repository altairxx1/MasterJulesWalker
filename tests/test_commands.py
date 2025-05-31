import unittest
import os
import subprocess
from unittest.mock import patch, MagicMock

# Ensure src directory is in path for imports if running tests from root
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.commands import CommandRunner
# Assuming PROJECT_ROOT is correctly picked up by CommandRunner from src.config
# We might need to mock src.config.PROJECT_ROOT if it's dynamic during tests
# For now, CommandRunner uses its own project_root or the one from config.

@patch('src.commands.PROJECT_ROOT', '/mock/project_root') # Mock project root for all tests in this class
class TestCommandRunner(unittest.TestCase):

    def setUp(self, mock_project_root_const): # mock_project_root_const is injected by class-level patch
        # The project_root passed to CommandRunner constructor is now less critical
        # as the one from src.config (mocked to /mock/project_root) will be used internally by CommandRunner methods.
        # However, CommandRunner's __init__ still takes project_root, which it assigns to self.project_root.
        # This self.project_root is used for Popen's cwd.
        # The semantic commands use semantic_indexer which gets PROJECT_ROOT from config.
        # For consistency, let's ensure the CommandRunner instance also uses the mocked root.
        self.runner = CommandRunner(project_root=mock_project_root_const)
        # If CommandRunner's __init__ was changed to always use config.PROJECT_ROOT, this would be simpler.
        # Current CommandRunner.__init__ sets self.project_root = PROJECT_ROOT (from config)
        # So, the constructor arg is effectively ignored if PROJECT_ROOT is available in config.
        # Let's verify this assumption or adjust CommandRunner. For now, assume it uses the mocked config.PROJECT_ROOT.
        self.assertEqual(self.runner.project_root, '/mock/project_root')


    def test_initialization(self, mock_project_root_const): # Keep signature for class-level patch
        # self.assertEqual(self.runner.project_root, self.project_root) # self.project_root is now the mocked path
        self.assertEqual(self.runner.project_root, '/mock/project_root')
        self.assertIsInstance(self.runner.allowed_commands, dict)
        self.assertTrue(len(self.runner.allowed_commands) > 0) # Should have some default commands

    def test_list_available_commands(self, mock_project_root_const):
        commands = self.runner.list_available_commands()
        self.assertIsInstance(commands, list)
        self.assertTrue(len(commands) > 0)
        for name, desc in commands:
            self.assertIsInstance(name, str)
            self.assertIsInstance(desc, str)
            self.assertIn(name, self.runner.allowed_commands)

    @patch('src.commands.subprocess.Popen')
    def test_run_command_success(self, mock_popen, mock_project_root_const):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("stdout success output", "") # stdout, stderr
        mock_popen.return_value = mock_process

        command_name = "list_files" # Assumes this is a valid command key
        success, output, error = self.runner.run_command(command_name)

        self.assertTrue(success)
        self.assertEqual(output, "stdout success output")
        self.assertIsNone(error)

        expected_cmd_parts = self.runner.allowed_commands[command_name]["command"].split()
        mock_popen.assert_called_once_with(
            expected_cmd_parts,
            cwd=self.runner.project_root, # This should be '/mock/project_root'
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        mock_process.communicate.assert_called_once_with(timeout=30)
        self.assertEqual(mock_popen.call_args[1]['cwd'], '/mock/project_root')


    @patch('src.commands.subprocess.Popen')
    def test_run_command_with_args_success(self, mock_popen, mock_project_root_const):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("diff output", "")
        mock_popen.return_value = mock_process

        command_name = "git_diff"
        args_str = "HEAD~1"
        success, output, error = self.runner.run_command(command_name, args_str=args_str)

        self.assertTrue(success)
        self.assertEqual(output, "diff output")
        self.assertIsNone(error)

        base_cmd = self.runner.allowed_commands[command_name]["command"]
        expected_full_command = base_cmd + " " + args_str
        import shlex
        expected_cmd_parts = shlex.split(expected_full_command)

        mock_popen.assert_called_once_with(
            expected_cmd_parts,
            cwd=self.runner.project_root, # This should be '/mock/project_root'
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        self.assertEqual(mock_popen.call_args[1]['cwd'], '/mock/project_root')


    @patch('src.commands.subprocess.Popen')
    def test_run_command_failure_return_code(self, mock_popen, mock_project_root_const):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("stdout on failure", "stderr on failure")
        mock_popen.return_value = mock_process

        command_name = "git_status"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        self.assertIn(f"Error running command '{command_name}'", error)
        self.assertIn("Return code: 1", error)
        self.assertIn("Stderr:\nstderr on failure", error)

    @patch('src.commands.subprocess.Popen')
    def test_run_command_failure_return_code_no_stderr(self, mock_popen, mock_project_root_const):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("stdout output even on failure", "") # stdout, empty stderr
        mock_popen.return_value = mock_process

        command_name = "git_status"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIn("Stdout (might contain error):\nstdout output even on failure", error)


    def test_run_command_not_found_in_allowed_commands(self, mock_project_root_const):
        command_name = "non_existent_command"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIn(f"Error: Command '{command_name}' not found.", output)
        self.assertIsNone(error)


    @patch('src.commands.subprocess.Popen')
    def test_run_command_os_command_not_found(self, mock_popen, mock_project_root_const):
        command_name = "git_status"
        self.assertIn(command_name, self.runner.allowed_commands)
        mock_popen.side_effect = FileNotFoundError("git not found")
        success, output, error = self.runner.run_command(command_name)
        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        expected_cmd_executable = self.runner.allowed_commands[command_name]["command"].split()[0]
        self.assertEqual(error, f"Error: The command '{expected_cmd_executable}' was not found. Is it installed and in PATH?")


    @patch('src.commands.subprocess.Popen')
    def test_run_command_timeout(self, mock_popen, mock_project_root_const):
        command_name = "list_files"
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="ls -la", timeout=30)
        mock_popen.return_value = mock_process
        success, output, error = self.runner.run_command(command_name)
        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error: Command '{command_name}' timed out after 30 seconds.")

    @patch('src.commands.subprocess.Popen')
    def test_run_command_unexpected_exception(self, mock_popen, mock_project_root_const):
        command_name = "list_files"
        mock_popen.side_effect = Exception("Unexpected boom")
        success, output, error = self.runner.run_command(command_name)
        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        self.assertEqual(error, f"An unexpected error occurred while running '{command_name}': Unexpected boom")

    # Tests for new semantic commands
    @patch('src.commands.get_project_files')
    @patch('src.commands.semantic_indexer')
    def test_run_command_build_semantic_index_success(self, mock_semantic_indexer, mock_get_project_files, mock_project_root_const):
        mock_get_project_files.return_value = [("file1.py", "file"), ("file2.txt", "file")]
        mock_semantic_indexer.build_index.return_value = None # build_index doesn't return anything

        success, output, error = self.runner.run_command("build_semantic_index")

        self.assertTrue(success)
        self.assertEqual(output, "Semantic index built successfully.")
        self.assertIsNone(error)
        mock_get_project_files.assert_called_once_with(self.runner.project_root)
        mock_semantic_indexer.build_index.assert_called_once_with(["file1.py", "file2.txt"])

    @patch('src.commands.get_project_files')
    @patch('src.commands.semantic_indexer')
    def test_run_command_build_semantic_index_no_files(self, mock_semantic_indexer, mock_get_project_files, mock_project_root_const):
        mock_get_project_files.return_value = [] # No files found

        success, output, error = self.runner.run_command("build_semantic_index")

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertEqual(error, "No files found to index.")
        mock_get_project_files.assert_called_once_with(self.runner.project_root)
        mock_semantic_indexer.build_index.assert_not_called()

    @patch('src.commands.get_project_files')
    @patch('src.commands.semantic_indexer')
    def test_run_command_build_semantic_index_exception(self, mock_semantic_indexer, mock_get_project_files, mock_project_root_const):
        mock_get_project_files.return_value = [("file1.py", "file")]
        mock_semantic_indexer.build_index.side_effect = Exception("Build failed")

        success, output, error = self.runner.run_command("build_semantic_index")

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertEqual(error, "Error building semantic index: Build failed")

    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_success(self, mock_semantic_indexer, mock_project_root_const):
        mock_semantic_indexer.index = True # Simulate index is loaded
        mock_semantic_indexer.file_chunks = True # Simulate file_chunks are loaded
        search_results = [
            {'file_path': 'file1.py', 'start_line': 1, 'end_line': 5, 'score': 0.9, 'text_chunk': 'chunk1 text'},
            {'file_path': 'file2.txt', 'start_line': 10, 'end_line': 12, 'score': 0.85, 'text_chunk': 'chunk2 text'}
        ]
        mock_semantic_indexer.search.return_value = search_results

        query = "test query"
        success, output, error = self.runner.run_command("semantic_search", args_str=query)

        self.assertTrue(success)
        self.assertIsNotNone(output)
        self.assertIsNone(error)
        mock_semantic_indexer.load_index.assert_not_called() # Index and chunks already "loaded"
        mock_semantic_indexer.search.assert_called_once_with(query)

        expected_output = (
            "File: file1.py\nLines: 1-5\nScore: 0.9000\nText:\nchunk1 text\n---\n"
            "File: file2.txt\nLines: 10-12\nScore: 0.8500\nText:\nchunk2 text\n---"
        )
        self.assertEqual(output, expected_output.strip())


    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_calls_load_index(self, mock_semantic_indexer, mock_project_root_const):
        # Simulate index not loaded initially
        mock_semantic_indexer.index = None
        mock_semantic_indexer.file_chunks = None

        # After load_index() is called, simulate it loads them
        def load_index_effect():
            mock_semantic_indexer.index = True
            mock_semantic_indexer.file_chunks = True
        mock_semantic_indexer.load_index.side_effect = load_index_effect
        mock_semantic_indexer.search.return_value = [] # No results needed for this test focus

        query = "test query"
        self.runner.run_command("semantic_search", args_str=query)

        mock_semantic_indexer.load_index.assert_called_once()
        mock_semantic_indexer.search.assert_called_once_with(query)


    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_no_results(self, mock_semantic_indexer, mock_project_root_const):
        mock_semantic_indexer.index = True
        mock_semantic_indexer.file_chunks = True
        mock_semantic_indexer.search.return_value = [] # No results

        success, output, error = self.runner.run_command("semantic_search", args_str="query")

        self.assertTrue(success)
        self.assertEqual(output, "No results found.")
        self.assertIsNone(error)

    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_no_query(self, mock_semantic_indexer, mock_project_root_const):
        success, output, error = self.runner.run_command("semantic_search", args_str=None) # No query

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertEqual(error, "Error: Search query cannot be empty for semantic_search.")
        mock_semantic_indexer.search.assert_not_called()

    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_index_not_built_or_loaded(self, mock_semantic_indexer, mock_project_root_const):
        mock_semantic_indexer.index = None
        mock_semantic_indexer.file_chunks = None
        # Simulate load_index also doesn't find anything
        mock_semantic_indexer.load_index.side_effect = lambda: None

        success, output, error = self.runner.run_command("semantic_search", args_str="query")

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertEqual(error, "Semantic index is not built or loaded. Run 'build_semantic_index' first.")
        mock_semantic_indexer.load_index.assert_called_once() # Attempted to load

    @patch('src.commands.semantic_indexer')
    def test_run_command_semantic_search_exception(self, mock_semantic_indexer, mock_project_root_const):
        mock_semantic_indexer.index = True
        mock_semantic_indexer.file_chunks = True
        mock_semantic_indexer.search.side_effect = Exception("Search failed")

        success, output, error = self.runner.run_command("semantic_search", args_str="query")

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertEqual(error, "Error during semantic search: Search failed")

    # --- Tests for diff and suggestion commands ---

    def setUp_chat_manager_mock(self):
        # Helper to set up a mock ChatManager on the runner
        self.mock_chat_manager_ref = MagicMock()
        self.runner.chat_manager_ref = self.mock_chat_manager_ref

    @patch('src.commands._extract_code_from_llm')
    @patch('src.commands.os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="original file content")
    def test_review_code_suggestion_success(self, mock_open_file, mock_path_exists, mock_extract_code, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.last_llm_response_raw = "```python\nnew code\n```"
        mock_extract_code.return_value = "new code"
        mock_path_exists.return_value = True
        filepath_arg = "test_file.py"
        abs_filepath_expected = os.path.join(self.runner.project_root, filepath_arg)


        success, output, error = self.runner.run_command("review_code_suggestion", args_str=filepath_arg)

        self.assertTrue(success)
        self.assertIn(f"Diff session started for '{filepath_arg}'", output)
        self.assertIsNone(error)
        mock_extract_code.assert_called_once_with("```python\nnew code\n```")
        mock_path_exists.assert_called_once_with(abs_filepath_expected)
        mock_open_file.assert_called_once_with(abs_filepath_expected, "r", encoding="utf-8")
        self.mock_chat_manager_ref.start_diff_session.assert_called_once_with(abs_filepath_expected, "original file content", "new code")

    def test_review_code_suggestion_no_chat_manager(self, mock_project_root_const):
        self.runner.chat_manager_ref = None # Ensure no chat manager
        success, output, error = self.runner.run_command("review_code_suggestion", args_str="file.py")
        self.assertFalse(success)
        self.assertEqual(error, "Error: ChatManager reference not available for this command.")

    def test_review_code_suggestion_no_filepath(self, mock_project_root_const):
        self.setUp_chat_manager_mock()
        success, output, error = self.runner.run_command("review_code_suggestion", args_str=None)
        self.assertFalse(success)
        self.assertEqual(error, "Error: Filepath is required for 'review_code_suggestion'.")

    def test_review_code_suggestion_no_llm_response(self, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.last_llm_response_raw = None
        success, output, error = self.runner.run_command("review_code_suggestion", args_str="file.py")
        self.assertFalse(success)
        self.assertEqual(error, "Error: No recent LLM response to review.")

    @patch('src.commands._extract_code_from_llm', return_value=None)
    def test_review_code_suggestion_no_code_found(self, mock_extract_code, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.last_llm_response_raw = "some response without code"
        success, output, error = self.runner.run_command("review_code_suggestion", args_str="file.py")
        self.assertFalse(success)
        self.assertEqual(error, "Error: No code block found in the last LLM response.")
        mock_extract_code.assert_called_once_with("some response without code")

    @patch('src.commands.os.path.exists', return_value=False)
    def test_review_code_suggestion_file_not_found(self, mock_path_exists, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.last_llm_response_raw = "```python\ncode\n```"
        # _extract_code_from_llm is not mocked here, will run, but that's fine.

        filepath_arg = "non_existent_file.py"
        abs_filepath_expected = os.path.join(self.runner.project_root, filepath_arg)

        success, output, error = self.runner.run_command("review_code_suggestion", args_str=filepath_arg)

        self.assertFalse(success)
        self.assertEqual(error, f"Error: File not found at '{abs_filepath_expected}'.")
        mock_path_exists.assert_called_once_with(abs_filepath_expected)


    @patch('src.commands.os.rename')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('src.commands.os.path.exists', return_value=True) # Assume target file exists for backup
    def test_accept_suggestion_success(self, mock_path_exists, mock_open_file, mock_os_rename, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = True
        self.mock_chat_manager_ref.active_diff_filepath = os.path.join(self.runner.project_root, "test_file.py")
        self.mock_chat_manager_ref.active_diff_suggested_content = "new accepted code"

        success, output, error = self.runner.run_command("accept_suggestion")

        self.assertTrue(success)
        self.assertIn("Changes applied to 'test_file.py'", output)
        self.assertIn("Original backed up to 'test_file.py.bak'", output)
        self.assertIsNone(error)

        mock_os_rename.assert_called_once_with(
            os.path.join(self.runner.project_root, "test_file.py"),
            os.path.join(self.runner.project_root, "test_file.py.bak")
        )
        mock_open_file.assert_called_once_with(os.path.join(self.runner.project_root, "test_file.py"), "w", encoding="utf-8")
        mock_open_file().write.assert_called_once_with("new accepted code")
        self.mock_chat_manager_ref.clear_diff_session.assert_called_once()

    def test_accept_suggestion_no_active_diff(self, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = False
        success, output, error = self.runner.run_command("accept_suggestion")
        self.assertFalse(success)
        self.assertEqual(error, "Error: No active code suggestion to accept.")

    @patch('src.commands.os.path.exists', return_value=True)
    @patch('src.commands.os.rename', side_effect=OSError("Backup failed"))
    def test_accept_suggestion_backup_fails(self, mock_os_rename, mock_path_exists, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = True
        self.mock_chat_manager_ref.active_diff_filepath = os.path.join(self.runner.project_root, "test_file.py")
        self.mock_chat_manager_ref.active_diff_suggested_content = "new code"

        success, output, error = self.runner.run_command("accept_suggestion")
        self.assertFalse(success)
        self.assertIn("Error applying changes: Backup failed", error)
        self.mock_chat_manager_ref.clear_diff_session.assert_not_called() # Should not clear if failed

    @patch('src.commands.os.path.exists') # Control exists for various calls
    @patch('src.commands.os.rename')
    @patch('builtins.open', side_effect=OSError("Write failed"))
    def test_accept_suggestion_write_fails_backup_restored(self, mock_open_file, mock_os_rename, mock_path_exists, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = True
        filepath = os.path.join(self.runner.project_root, "test_file.py")
        backup_filepath = filepath + ".bak"
        self.mock_chat_manager_ref.active_diff_filepath = filepath
        self.mock_chat_manager_ref.active_diff_suggested_content = "new code"

        # os.path.exists should return True for the original file, then True for backup, then False for original (after failed write)
        mock_path_exists.side_effect = [True, True, False] # 1st for active_filepath (backup), 2nd for backup_filepath (restore check), 3rd for active_filepath (restore check)

        success, output, error = self.runner.run_command("accept_suggestion")

        self.assertFalse(success)
        self.assertIn("Error applying changes: Write failed. Backup restored.", error)
        mock_os_rename.assert_any_call(filepath, backup_filepath) # Backup attempt
        mock_os_rename.assert_any_call(backup_filepath, filepath) # Restore attempt
        self.mock_chat_manager_ref.clear_diff_session.assert_not_called()


    def test_reject_suggestion_success(self, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = True
        success, output, error = self.runner.run_command("reject_suggestion")
        self.assertTrue(success)
        self.assertEqual(output, "Suggestion rejected. Diff session cleared.")
        self.assertIsNone(error)
        self.mock_chat_manager_ref.clear_diff_session.assert_called_once()

    def test_reject_suggestion_no_active_diff(self, mock_project_root_const):
        self.setUp_chat_manager_mock()
        self.mock_chat_manager_ref.is_diff_active = False
        success, output, error = self.runner.run_command("reject_suggestion")
        self.assertFalse(success)
        self.assertEqual(error, "Error: No active code suggestion to reject.")

    # Tests for _extract_code_from_llm (can be part of TestCommandRunner or separate if it grows)
    def test_extract_code_from_llm_python_block(self, mock_project_root_const):
        from src.commands import _extract_code_from_llm # Import here due to class-level patch
        text = "Some text before\n```python\ndef hello():\n    print('Hello')\n```\nSome text after"
        self.assertEqual(_extract_code_from_llm(text), "def hello():\n    print('Hello')")

    def test_extract_code_from_llm_generic_block(self, mock_project_root_const):
        from src.commands import _extract_code_from_llm
        text = "Explanation...\n```\n// Java code\nSystem.out.println(\"Hi\");\n```"
        self.assertEqual(_extract_code_from_llm(text), "// Java code\nSystem.out.println(\"Hi\");")

    def test_extract_code_from_llm_no_block(self, mock_project_root_const):
        from src.commands import _extract_code_from_llm
        text = "Just plain text, no code block."
        self.assertIsNone(_extract_code_from_llm(text))

    def test_extract_code_from_llm_empty_input(self, mock_project_root_const):
        from src.commands import _extract_code_from_llm
        self.assertIsNone(_extract_code_from_llm(""))
        self.assertIsNone(_extract_code_from_llm(None))


if __name__ == '__main__':
    unittest.main()
