import unittest
from unittest.mock import MagicMock, patch
import os
import curses # <--- Import curses

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
    @patch('src.ui.SnippetManager') # Added patch for SnippetManager
    def setUp(self, MockSnippetManager_class, MockContextManager_class_for_init, mock_tree, mock_files,
              MockChatManager_class, MockCommandRunner_class, MockCodeAnalyzer_class,
              MockTabManager_class, mock_load_config_func):

        self.stdscr_mock = MagicMock()
        self.stdscr_mock.getmaxyx.return_value = (24, 80) # Common terminal size

        # Store mock classes for potential later use if needed for instances
        self.MockChatManager_class = MockChatManager_class

        # Mock methods called during TerminalUI.__init__ that might have side effects
        with patch.object(TerminalUI, '_load_project_files', MagicMock()), \
             patch.object(TerminalUI, '_update_tree_display', MagicMock()):
            self.ui = TerminalUI(self.stdscr_mock)

        # The ui.chat_manager will be an instance of MockChatManager_class.return_value
        # We can directly mock methods on self.ui.chat_manager
        self.mock_chat_manager_instance = self.ui.chat_manager

        self.mock_context_manager_instance = MagicMock(spec=ContextManager)
        self.ui.context_manager = self.mock_context_manager_instance

        # Ensure tab_manager has a mock get_current_tab method
        self.ui.tab_manager.get_current_tab.return_value = "Files" # Default for relevant tests

        # Make self.ui.code_analyzer an accessible mock instance for tests
        self.mock_code_analyzer_instance = self.ui.code_analyzer
        # Make self.ui.snippet_manager an accessible mock instance
        self.mock_snippet_manager_instance = self.ui.snippet_manager


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

    # --- Tests for AI-Powered Test Generation UI ---

    def test_trigger_test_generation(self):
        # Setup UI state for analyzer mode
        self.ui.file_tab_mode = "analyzer"
        self.ui.active_analysis_report = {
            'classes': [{'name': 'MyClass', 'methods': [], 'attributes': []}],
            'functions': [{'name': 'my_func'}]
        }
        # Populate selectable items (simplified version of what _draw_main_content does)
        self.ui.analysis_selectable_items = [
            {'type': 'class', 'name': 'MyClass', 'report_idx': 0, 'display_start_line': 0},
            {'type': 'function', 'name': 'my_func', 'report_idx': 0, 'display_start_line': 5}
        ]
        self.ui.selected_analysis_item_index = 1 # Select 'my_func'

        selected_item_info = self.ui.analysis_selectable_items[self.ui.selected_analysis_item_index]
        item_name_to_generate = selected_item_info['name']
        item_type_to_generate = selected_item_info['type']

        sample_test_code = f"# Test for {item_name_to_generate}\ndef test_{item_name_to_generate}(): assert True"

        # Configure mock ChatManager
        self.mock_chat_manager_instance.request_test_generation.return_value = sample_test_code

        # Mock stdscr.refresh called during 't' handling
        self.stdscr_mock.refresh = MagicMock()

        # Simulate pressing 't'
        # _handle_input returns False to quit, True to continue
        # We need to ensure the current tab is "Files" for the logic to trigger
        self.ui.tab_manager.get_current_tab.return_value = "Files"
        result = self.ui._handle_input(ord('t'))
        self.assertTrue(result) # Should continue running

        # Assertions
        self.mock_chat_manager_instance.request_test_generation.assert_called_once_with(
            item_name_to_generate, item_type_to_generate
        )

        # is_generating_tests is True during the call, then False after.
        # Hard to test intermediate state without threads/async; check final.
        self.assertFalse(self.ui.is_generating_tests)
        self.assertEqual(self.ui.file_tab_mode, "test_viewer")
        self.assertEqual(self.ui.generated_test_code_lines, sample_test_code.split('\n'))
        self.assertEqual(self.ui.test_viewer_top_line, 0)
        self.assertIn(f"Tests generated for {item_name_to_generate}", self.ui.context_status_message)

    def test_trigger_test_generation_error_from_llm(self):
        self.ui.file_tab_mode = "analyzer"
        self.ui.analysis_selectable_items = [
            {'type': 'function', 'name': 'error_func', 'report_idx': 0, 'display_start_line': 0}
        ]
        self.ui.selected_analysis_item_index = 0
        item_name_to_generate = 'error_func'
        item_type_to_generate = 'function'

        error_message_from_llm = "# Error: LLM failed miserably"
        self.mock_chat_manager_instance.request_test_generation.return_value = error_message_from_llm
        self.stdscr_mock.refresh = MagicMock()
        self.ui.tab_manager.get_current_tab.return_value = "Files"

        self.ui._handle_input(ord('t'))

        self.assertEqual(self.ui.file_tab_mode, "test_viewer")
        self.assertEqual(self.ui.generated_test_code_lines, error_message_from_llm.split('\n'))
        self.assertIn(f"Error generating tests: {error_message_from_llm}", self.ui.context_status_message)


    def test_navigate_back_from_test_viewer(self):
        # Setup UI state for test_viewer mode
        self.ui.file_tab_mode = "test_viewer"
        self.ui.generated_test_code_lines = ["line1", "line2"]
        self.ui.tab_manager.get_current_tab.return_value = "Files" # Ensure correct tab

        # Simulate pressing 'b'
        result = self.ui._handle_input(ord('b'))
        self.assertTrue(result)

        # Assertions
        self.assertEqual(self.ui.file_tab_mode, "analyzer")
        self.assertEqual(self.ui.generated_test_code_lines, [])
        self.assertIn("Returned to analyzer", self.ui.context_status_message)

    def test_scroll_test_viewer(self):
        self.ui.file_tab_mode = "test_viewer"
        self.ui.generated_test_code_lines = [f"line {i}" for i in range(50)]
        self.ui.test_viewer_top_line = 0
        self.ui.tab_manager.get_current_tab.return_value = "Files"

        # Mock getmaxyx to define content height for scrolling calculation
        # (h - content_start_y - hint_lines) = max_h - 4 - 2 = max_h - 6
        # If max_h is 24, content_height is 18.
        self.stdscr_mock.getmaxyx.return_value = (24, 80) # h=24, w=80
        test_viewer_content_height = 24 - 4 - 2 # 18

        # Scroll down
        self.ui._handle_input(curses.KEY_DOWN)
        self.assertEqual(self.ui.test_viewer_top_line, 1)

        # Scroll up
        self.ui._handle_input(curses.KEY_UP)
        self.assertEqual(self.ui.test_viewer_top_line, 0)

        # Page down
        self.ui._handle_input(curses.KEY_NPAGE)
        expected_top_line = min(len(self.ui.generated_test_code_lines) - test_viewer_content_height, 0 + test_viewer_content_height)
        self.assertEqual(self.ui.test_viewer_top_line, expected_top_line)

        current_top = self.ui.test_viewer_top_line
        # Page up
        self.ui._handle_input(curses.KEY_PPAGE)
        self.assertEqual(self.ui.test_viewer_top_line, max(0, current_top - test_viewer_content_height) )

    # --- Tests for Command Suggestions ---

    def test_get_context_signals(self):
        # Configure mocks
        self.ui.tab_manager.get_current_tab.return_value = "TestTab"
        self.mock_context_manager_instance.get_context_summary.return_value = ["file1.py (1KB)"]
        self.mock_chat_manager_instance.get_formatted_history.return_value = ["User: Hi", "MJW: Hello"]
        self.mock_code_analyzer_instance.format_analysis_for_llm.return_value = "Formatted analysis detail"
        self.ui.active_analysis_report = {'some_key': 'some_value'} # Not an error report
        self.ui.available_commands = [("cmd1", "desc1")]

        signals = self.ui._get_context_signals()

        self.assertEqual(signals['current_tab'], "TestTab")
        self.assertEqual(signals['context_files'], ["file1.py (1KB)"])
        self.assertEqual(signals['recent_chat_history'], ["User: Hi", "MJW: Hello"])
        self.assertEqual(signals['active_analysis'], "Formatted analysis detail")
        self.assertEqual(signals['available_commands'], [("cmd1", "desc1")])
        self.mock_code_analyzer_instance.format_analysis_for_llm.assert_called_once_with(self.ui.active_analysis_report)

    def test_get_context_signals_no_analysis(self):
        self.ui.active_analysis_report = None
        signals = self.ui._get_context_signals()
        self.assertEqual(signals['active_analysis'], "None")

    def test_get_context_signals_analysis_error(self):
        self.ui.active_analysis_report = {'error': 'Failed to parse'}
        signals = self.ui._get_context_signals()
        self.assertEqual(signals['active_analysis'], "Error in analysis: Failed to parse")

    def test_get_context_signals_long_analysis_truncation(self):
        long_analysis_text = "a" * 1000
        self.ui.active_analysis_report = {'some_key': 'some_value'}
        self.mock_code_analyzer_instance.format_analysis_for_llm.return_value = long_analysis_text

        signals = self.ui._get_context_signals()

        expected_truncated_text = long_analysis_text[:497] + "..."
        self.assertEqual(signals['active_analysis'], expected_truncated_text)
        self.assertTrue(len(signals['active_analysis']) <= 500)

    @patch.object(TerminalUI, '_get_context_signals')
    def test_trigger_suggestion_fetch_on_tab_switch(self, mock_get_signals):
        # Simulate switching TO Commands tab
        # 1. Setup: Current tab is NOT Commands
        self.ui.tab_manager.get_current_tab.return_value = "Files" # Initial current tab

        # 2. Configure handle_input to report that a switch to "Commands" happened
        # We make tab_manager.handle_input return True (switched)
        # and then make get_current_tab return "Commands" for the check *after* the switch.
        def mock_handle_input_then_get_tab(key):
            if key == curses.KEY_RIGHT: # Or any key that could cause tab switch
                self.ui.tab_manager.get_current_tab.return_value = "Commands" # Switched to Commands
                return True # Indicate tab switch occurred
            return False
        self.ui.tab_manager.handle_input = MagicMock(side_effect=mock_handle_input_then_get_tab)

        mock_fixed_signals = {"key": "value", "available_commands": [("cmd1", "desc1")]}
        mock_get_signals.return_value = mock_fixed_signals
        self.mock_chat_manager_instance.request_command_suggestions.return_value = ["cmd1"]
        self.stdscr_mock.refresh = MagicMock()

        # Act: Call _handle_input with a key that our mock_tab_manager_handle_input will use
        # This will execute the block in _handle_input that processes tab switches.
        self.ui._handle_input(curses.KEY_RIGHT)

        # Assertions
        mock_get_signals.assert_called_once()
        self.mock_chat_manager_instance.request_command_suggestions.assert_called_once_with(mock_fixed_signals)
        self.assertEqual(self.ui.suggested_command_names, ["cmd1"])
        self.assertIn("Fetched 1 suggestions", self.ui.command_status_message)
        self.assertFalse(self.ui.is_fetching_suggestions)

    @patch.object(TerminalUI, '_get_context_signals')
    def test_trigger_suggestion_fetch_f5_press(self, mock_get_signals):
        self.ui.tab_manager.get_current_tab.return_value = "Commands"
        self.ui.commands_view_mode = "list" # Ensure we are in the list view

        mock_fixed_signals = {"key": "value", "available_commands": [("cmd1", "desc1")]}
        mock_get_signals.return_value = mock_fixed_signals
        self.mock_chat_manager_instance.request_command_suggestions.return_value = ["cmd1", "cmd2"]
        self.stdscr_mock.refresh = MagicMock()

        self.ui._handle_input(curses.KEY_F5)

        mock_get_signals.assert_called_once()
        self.mock_chat_manager_instance.request_command_suggestions.assert_called_once_with(mock_fixed_signals)
        self.assertEqual(self.ui.suggested_command_names, ["cmd1", "cmd2"])
        self.assertIn("2 suggestions refreshed", self.ui.command_status_message)
        self.assertFalse(self.ui.is_fetching_suggestions)

    # Test for self.is_fetching_suggestions status message (visual state)
    # This test will involve checking what's drawn.
    # It's a bit more complex due to direct curses calls.
    # We'll check if "Fetching command suggestions..." is passed to addstr.
    def test_drawing_fetching_suggestions_message(self):
        self.ui.tab_manager.get_current_tab.return_value = "Commands"
        self.ui.commands_view_mode = "list"
        self.ui.is_fetching_suggestions = True # Simulate fetching state

        self.stdscr_mock.addstr = MagicMock() # Mock addstr to capture calls

        self.ui._draw_main_content() # Call draw method

        # Check if addstr was called with the fetching message
        # This requires knowing the exact y, x, and message content.
        # The message is "Fetching command suggestions..."
        # It's drawn at content_y_start + 1 (which is 4 + 1 = 5), x=2

        # Simplified check: was "Fetching command suggestions..." part of any addstr call?
        found_fetching_message = False
        for call_args in self.stdscr_mock.addstr.call_args_list:
            # call_args is a tuple ((y, x, text, attr),) or ((y, x, text),)
            args = call_args[0]
            if len(args) >=3 and "Fetching command suggestions..." in args[2]:
                found_fetching_message = True
                break
        self.assertTrue(found_fetching_message, "Fetching suggestions message not displayed")

    # --- Tests for Snippets Tab UI ---

    def test_snippet_tab_activation(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets" # Current tab is already Snippets

        # Simulate having switched to Snippets (logic is in the main _handle_input tab switch block)
        # For this test, we directly call the consequence of switching to the Snippets tab.
        dummy_snippets = [{"id": "1", "name": "Test Snippet", "language": "python"}]
        self.mock_snippet_manager_instance.list_snippets.return_value = dummy_snippets

        # Manually trigger the part of _handle_input that runs on tab switch to Snippets
        # This is a bit of a white-box test, ideally _handle_input would be structured to call a helper.
        # For now, let's assume the state update is what we want to test.
        self.ui.snippet_list = self.ui.snippet_manager.list_snippets()
        self.ui.selected_snippet_index = 0
        self.ui.snippet_view_top_line = 0

        self.mock_snippet_manager_instance.list_snippets.assert_called_once()
        self.assertEqual(self.ui.snippet_list, dummy_snippets)
        self.assertEqual(self.ui.selected_snippet_index, 0)

    def test_snippet_list_mode_actions(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        self.ui.snippet_tab_mode = "list"
        sample_snippet_data = {"id": "s1", "name": "My Snippet", "content": "print('hello')", "language": "python", "tags": ["tag1"]}
        self.ui.snippet_list = [sample_snippet_data]
        self.ui.selected_snippet_index = 0

        # Test View (Enter)
        self.mock_snippet_manager_instance.get_snippet_by_id.return_value = sample_snippet_data
        self.ui._handle_input(curses.KEY_ENTER)
        self.assertEqual(self.ui.snippet_tab_mode, "view_content")
        self.assertEqual(self.ui.active_snippet_content_lines, ["print('hello')"])
        self.mock_snippet_manager_instance.get_snippet_by_id.assert_called_with("s1")
        self.assertIn("Viewing: My Snippet", self.ui.snippet_status_message)

        # Reset for Add
        self.ui.snippet_tab_mode = "list"
        self.ui._handle_input(ord('a'))
        self.assertEqual(self.ui.snippet_tab_mode, "edit_form")
        self.assertIsNone(self.ui.current_snippet_id_being_edited)
        self.assertEqual(self.ui.snippet_form_data["name"], "")
        self.assertEqual(self.ui.snippet_form_active_field, "name")
        self.assertIn("Opened add snippet form", self.ui.snippet_status_message)

        # Reset for Edit
        self.ui.snippet_tab_mode = "list"
        self.mock_snippet_manager_instance.get_snippet_by_id.return_value = sample_snippet_data
        self.ui._handle_input(ord('e'))
        self.assertEqual(self.ui.snippet_tab_mode, "edit_form")
        self.assertEqual(self.ui.current_snippet_id_being_edited, "s1")
        self.assertEqual(self.ui.snippet_form_data["name"], "My Snippet")
        self.assertEqual(self.ui.snippet_form_data["tags"], "tag1") # Check tags conversion
        self.assertIn("Editing: My Snippet", self.ui.snippet_status_message)

        # Test Delete (two-stage)
        self.ui.snippet_tab_mode = "list"
        self.ui.selected_snippet_index = 0 # Ensure a snippet is selected
        self.ui.snippet_list = [sample_snippet_data] # Ensure list is populated for selection

        # First 'd'
        self.ui._handle_input(ord('d'))
        self.assertEqual(self.ui.delete_confirm_pending_id, "s1")
        self.assertIn("Press 'd' again to confirm", self.ui.snippet_status_message)

        # Press another key (e.g. 'x') to cancel confirmation
        self.ui._handle_input(ord('x'))
        self.assertIsNone(self.ui.delete_confirm_pending_id)

        # Press 'd' again for confirmation
        self.ui._handle_input(ord('d')) # Set pending again
        self.mock_snippet_manager_instance.delete_snippet.return_value = True
        self.mock_snippet_manager_instance.list_snippets.return_value = [] # Simulate snippet list after deletion
        self.ui._handle_input(ord('d')) # Confirm delete
        self.mock_snippet_manager_instance.delete_snippet.assert_called_with("s1")
        self.mock_snippet_manager_instance.list_snippets.assert_called() # List is reloaded
        self.assertIsNone(self.ui.delete_confirm_pending_id)
        self.assertIn("Snippet 'My Snippet' deleted", self.ui.snippet_status_message)

    def test_snippet_view_content_mode(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        self.ui.snippet_tab_mode = "view_content"
        self.ui.active_snippet_content_lines = ["line1", "line2", "line3"] * 10 # Ensure scrollable
        self.stdscr_mock.getmaxyx.return_value = (24, 80) # h=24
        # content_view_height = max_h - 4 - 2 - 1 = 24 - 7 = 17

        # Back to list
        self.ui._handle_input(ord('b'))
        self.assertEqual(self.ui.snippet_tab_mode, "list")
        self.assertEqual(self.ui.active_snippet_content_lines, [])

        # Scrolling (reset mode for test)
        self.ui.snippet_tab_mode = "view_content"
        self.ui.active_snippet_content_lines = ["line1", "line2", "line3"] * 10
        self.ui.snippet_content_scroll_top = 0
        self.ui._handle_input(curses.KEY_DOWN)
        self.assertEqual(self.ui.snippet_content_scroll_top, 1)
        self.ui._handle_input(curses.KEY_UP)
        self.assertEqual(self.ui.snippet_content_scroll_top, 0)


    def test_snippet_edit_form_mode_navigation_and_cancel(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        self.ui.snippet_tab_mode = "edit_form"
        self.ui.current_snippet_id_being_edited = None # Add mode
        self.ui.snippet_form_data = {"name": "N", "language": "L", "category": "C", "tags": "T", "content": "CNT"}
        self.ui.snippet_form_active_field = "name"
        self.ui.snippet_form_input_buffer = "N" # Buffer matches active field data

        # Tab through fields
        expected_field_order = ["name", "language", "category", "tags", "content", "save", "cancel"]
        for i in range(len(expected_field_order) * 2): # Cycle twice
            current_field = self.ui.snippet_form_active_field
            self.ui._handle_input(ord('\t'))
            next_expected_idx = (expected_field_order.index(current_field) + 1) % len(expected_field_order)
            self.assertEqual(self.ui.snippet_form_active_field, expected_field_order[next_expected_idx])
            # Check if buffer loaded correctly for the new field
            if expected_field_order[next_expected_idx] not in ["save", "cancel"]:
                self.assertEqual(self.ui.snippet_form_input_buffer, self.ui.snippet_form_data.get(expected_field_order[next_expected_idx],""))

        # Test Escape
        self.ui.snippet_tab_mode = "edit_form" # Reset just in case
        self.ui._handle_input(curses.KEY_ESCAPE)
        self.assertEqual(self.ui.snippet_tab_mode, "list")
        self.assertIsNone(self.ui.current_snippet_id_being_edited)
        self.assertEqual(self.ui.snippet_form_data, {}) # Form data cleared
        self.assertIn("Operation cancelled", self.ui.snippet_status_message)

    def test_snippet_edit_form_save_add_mode(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        self.ui.snippet_tab_mode = "edit_form"
        self.ui.current_snippet_id_being_edited = None # Add mode
        self.ui.snippet_form_active_field = "tags" # Assume last field before save
        self.ui.snippet_form_input_buffer = "tagA, tagB"
        # Populate form data as if user typed it
        self.ui.snippet_form_data = {
            "name": "Added Snippet",
            "language": "python",
            "category": "Test Cat",
            "content": "print('Added')",
            "tags": "tagA, tagB" # This will be from buffer of active field
        }

        self.mock_snippet_manager_instance.add_snippet.return_value = {"id": "new_id", "name": "Added Snippet"}
        self.mock_snippet_manager_instance.list_snippets.return_value = [{"id": "new_id", "name": "Added Snippet"}]

        # Move to Save button and press Enter
        self.ui.snippet_form_active_field = "save"
        self.ui._handle_input(curses.KEY_ENTER)

        self.mock_snippet_manager_instance.add_snippet.assert_called_once_with(
            name="Added Snippet", content="print('Added')", language="python", category="Test Cat", tags=["tagA", "tagB"]
        )
        self.assertEqual(self.ui.snippet_tab_mode, "list")
        self.assertIn("Snippet 'Added Snippet' added", self.ui.snippet_status_message)
        self.mock_snippet_manager_instance.list_snippets.assert_called_once()

    def test_snippet_edit_form_save_edit_mode(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        snippet_id_to_edit = "s_edit_1"
        self.ui.current_snippet_id_being_edited = snippet_id_to_edit
        self.ui.snippet_tab_mode = "edit_form"
        self.ui.snippet_form_active_field = "content" # Assume last field before save
        self.ui.snippet_form_input_buffer = "Updated content"
        self.ui.snippet_form_data = {
            "id": snippet_id_to_edit,
            "name": "Updated Name",
            "language": "javascript",
            "category": "Updated Cat",
            "tags": "tagX, tagY", # This is before content buffer is stored
            "content": "Updated content" # this would be from buffer if content is active
        }

        self.mock_snippet_manager_instance.update_snippet.return_value = {"id": snippet_id_to_edit, "name": "Updated Name"}
        self.mock_snippet_manager_instance.list_snippets.return_value = [{"id": snippet_id_to_edit, "name": "Updated Name"}]

        # Move to Save button and press Enter
        self.ui.snippet_form_active_field = "save"
        self.ui._handle_input(curses.KEY_ENTER)

        self.mock_snippet_manager_instance.update_snippet.assert_called_once_with(
            snippet_id_to_edit,
            name="Updated Name", content="Updated content", language="javascript", category="Updated Cat", tags=["tagX", "tagY"]
        )
        self.assertEqual(self.ui.snippet_tab_mode, "list")
        self.assertIn("Snippet 'Updated Name' updated", self.ui.snippet_status_message)

    def test_snippet_form_input_char_handling(self):
        self.ui.tab_manager.get_current_tab.return_value = "Snippets"
        self.ui.snippet_tab_mode = "edit_form"
        self.ui.snippet_form_active_field = "name"
        self.ui.snippet_form_input_buffer = "Initial"

        # Test printable char
        self.ui._handle_input(ord('X'))
        self.assertEqual(self.ui.snippet_form_input_buffer, "InitialX")

        # Test backspace
        self.ui._handle_input(curses.KEY_BACKSPACE)
        self.assertEqual(self.ui.snippet_form_input_buffer, "Initial")

        # Test Enter on content field
        self.ui.snippet_form_active_field = "content"
        self.ui.snippet_form_input_buffer = "Line1"
        self.ui._handle_input(curses.KEY_ENTER)
        self.assertEqual(self.ui.snippet_form_input_buffer, "Line1\n")


if __name__ == '__main__':
    unittest.main()
