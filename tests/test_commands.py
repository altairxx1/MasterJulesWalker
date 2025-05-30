import unittest
import os
import subprocess
from unittest.mock import patch, MagicMock

from src.commands import CommandRunner

class TestCommandRunner(unittest.TestCase):

    def setUp(self):
        self.project_root = os.path.abspath("test_command_runner_project_dir")
        # No need to create the dir if subprocess is always mocked
        self.runner = CommandRunner(project_root=self.project_root)

    def test_initialization(self):
        self.assertEqual(self.runner.project_root, self.project_root)
        self.assertIsInstance(self.runner.allowed_commands, dict)
        self.assertGreater(len(self.runner.allowed_commands), 0) # Should have some default commands

    def test_list_available_commands(self):
        commands = self.runner.list_available_commands()
        self.assertIsInstance(commands, list)
        self.assertGreater(len(commands), 0)
        for name, desc in commands:
            self.assertIsInstance(name, str)
            self.assertIsInstance(desc, str)
            self.assertIn(name, self.runner.allowed_commands)

    @patch('src.commands.subprocess.Popen')
    def test_run_command_success(self, mock_popen):
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
            cwd=self.runner.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        mock_process.communicate.assert_called_once_with(timeout=30)

    @patch('src.commands.subprocess.Popen')
    def test_run_command_with_args_success(self, mock_popen):
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
        # shlex.split is used in the SUT
        import shlex
        expected_cmd_parts = shlex.split(expected_full_command)

        mock_popen.assert_called_once_with(
            expected_cmd_parts,
            cwd=self.runner.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

    @patch('src.commands.subprocess.Popen')
    def test_run_command_failure_return_code(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("stdout on failure", "stderr on failure")
        mock_popen.return_value = mock_process

        command_name = "git_status"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        self.assertIn("Error running command 'git_status'", error)
        self.assertIn("Return code: 1", error)
        self.assertIn("Stderr:\nstderr on failure", error)

    @patch('src.commands.subprocess.Popen')
    def test_run_command_failure_return_code_no_stderr(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("stdout output even on failure", "") # stdout, empty stderr
        mock_popen.return_value = mock_process

        command_name = "git_status"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIn("Stdout (might contain error):\nstdout output even on failure", error)


    def test_run_command_not_found_in_allowed_commands(self):
        command_name = "non_existent_command"
        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIn(f"Error: Command '{command_name}' not found.", output) # Error message is in 'output' field for this case
        self.assertIsNone(error)


    @patch('src.commands.subprocess.Popen')
    def test_run_command_os_command_not_found(self, mock_popen):
        # This mocks the scenario where the command itself (e.g., 'git') is not installed
        command_name = "git_status" # A command that should exist in allowed_commands
        # Ensure the command is in allowed_commands for this test path
        self.assertIn(command_name, self.runner.allowed_commands)

        mock_popen.side_effect = FileNotFoundError("git not found")

        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        # Check against the actual error message from src/commands.py
        expected_cmd_executable = self.runner.allowed_commands[command_name]["command"].split()[0]
        self.assertEqual(error, f"Error: The command '{expected_cmd_executable}' was not found. Is it installed and in PATH?")


    @patch('src.commands.subprocess.Popen')
    def test_run_command_timeout(self, mock_popen):
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
    def test_run_command_unexpected_exception(self, mock_popen):
        command_name = "list_files"
        mock_popen.side_effect = Exception("Unexpected boom")

        success, output, error = self.runner.run_command(command_name)

        self.assertFalse(success)
        self.assertIsNone(output)
        self.assertIsNotNone(error)
        self.assertEqual(error, f"An unexpected error occurred while running '{command_name}': Unexpected boom")


if __name__ == '__main__':
    unittest.main()
