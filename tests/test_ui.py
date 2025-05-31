import unittest
from unittest.mock import MagicMock, patch
import os

from src.ui import TerminalUI
from src.context import ContextManager # Used for spec

# Minimal config for TerminalUI initialization
MOCK_APP_CONFIG = {
    "openrouter_api_key": "test_key",
    "mjw_model": "test_model",
    # Add other keys if TerminalUI.__init__ directly accesses them and causes errors
}

class TestTerminalUI(unittest.TestCase):

    @patch('src.ui.load_config', return_value=MOCK_APP_CONFIG)
    @patch('src.ui.TabManager')
    @patch('src.ui.CodeAnalyzer')
    @patch('src.ui.CommandRunner')
    @patch('src.ui.ChatManager')
    @patch('src.ui.files')
    @patch('src.ui.tree')
    # Patch the ContextManager class where it's imported in src.ui
    # This ensures that TerminalUI.__init__ uses a mock for self.context_manager
    @patch('src.ui.ContextManager')
    def setUp(self, MockContextManager_class_for_init, mock_tree, mock_files,
              MockChatManager, MockCommandRunner, MockCodeAnalyzer,
              MockTabManager, mock_load_config):

        self.stdscr_mock = MagicMock()

        # Mock methods called during TerminalUI.__init__ that might have side effects
        with patch.object(TerminalUI, '_load_project_files', MagicMock()), \
             patch.object(TerminalUI, '_update_tree_display', MagicMock()):
            # TerminalUI will be initialized with a mock ContextManager instance
            # provided by MockContextManager_class_for_init.return_value
            self.ui = TerminalUI(self.stdscr_mock)

        # For fine-grained control in each test, we replace the context_manager
        # instance that was set during __init__ (which is MockContextManager_class_for_init.return_value)
        # with a new MagicMock specific for our assertions.
        self.mock_context_manager_instance = MagicMock(spec=ContextManager)
        self.ui.context_manager = self.mock_context_manager_instance

    def test_add_file_to_context_success(self):
        filepath = "path/to/somefile.py"
        filename = os.path.basename(filepath)

        self.mock_context_manager_instance.add_file.return_value = True
        self.mock_context_manager_instance.get_latest_error.return_value = None # Or some irrelevant old message

        result = self.ui.add_file_to_context(filepath)

        self.mock_context_manager_instance.add_file.assert_called_once_with(filepath)
        self.mock_context_manager_instance.get_latest_error.assert_called_once() # Ensure it's checked
        self.assertEqual(result, f"Successfully added {filename} to context.")

    def test_add_file_to_context_failure_with_specific_error(self):
        filepath = "path/to/nonexistent.py"
        error_message = "Error: File not found or size limit exceeded."

        self.mock_context_manager_instance.add_file.return_value = False
        self.mock_context_manager_instance.get_latest_error.return_value = error_message

        result = self.ui.add_file_to_context(filepath)

        self.mock_context_manager_instance.add_file.assert_called_once_with(filepath)
        self.mock_context_manager_instance.get_latest_error.assert_called_once()
        self.assertEqual(result, error_message)

    def test_add_file_to_context_failure_no_specific_error(self):
        filepath = "path/to/problemfile.py"
        filename = os.path.basename(filepath)

        self.mock_context_manager_instance.add_file.return_value = False
        self.mock_context_manager_instance.get_latest_error.return_value = None

        result = self.ui.add_file_to_context(filepath)

        self.mock_context_manager_instance.add_file.assert_called_once_with(filepath)
        self.mock_context_manager_instance.get_latest_error.assert_called_once()
        self.assertEqual(result, f"Failed to add {filename} to context.")

    def test_add_file_to_context_no_manager(self):
        filepath = "path/to/anyfile.py"
        filename = os.path.basename(filepath) # For the expected message

        original_cm = self.ui.context_manager # Save the mock
        self.ui.context_manager = None # Set to None for this test

        result = self.ui.add_file_to_context(filepath)

        # Expected message format from src/ui.py's add_file_to_context method
        self.assertEqual(result, f"Error: ContextManager not available for {filename}.")

        self.ui.context_manager = original_cm # Restore

if __name__ == '__main__':
    unittest.main()
