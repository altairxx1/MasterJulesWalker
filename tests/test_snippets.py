import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import uuid # To work with the UUIDs used in SnippetManager

from src.snippets import SnippetManager

class TestSnippetManager(unittest.TestCase):

    def setUp(self):
        # Default filepath for tests, can be overridden in specific tests if needed
        self.test_filepath = "test_snippets_file.json"
        # Ensure no actual file from previous runs interferes
        if os.path.exists(self.test_filepath):
            os.remove(self.test_filepath)

    def tearDown(self):
        # Clean up the test file after each test
        if os.path.exists(self.test_filepath):
            os.remove(self.test_filepath)

    @patch('src.snippets.os.path.exists')
    @patch('src.snippets.open', new_callable=mock_open)
    def test_load_snippets_file_not_found(self, mock_file_open, mock_exists):
        mock_exists.return_value = False
        manager = SnippetManager(filepath=self.test_filepath)
        self.assertEqual(manager.snippets, [])
        mock_file_open.assert_not_called() # Should not try to open if not exists (current logic does try)
                                         # Correcting based on SnippetManager's actual behavior:
                                         # it checks exists, then tries to open. If exists is false, open won't be called.
                                         # The provided SnippetManager code, however, does:
                                         # if os.path.exists(self.filepath): with open(...)
                                         # So, if mock_exists is False, open is indeed not called.

    @patch('src.snippets.os.path.exists')
    @patch('src.snippets.open', new_callable=mock_open)
    @patch('src.snippets.json.load')
    def test_load_snippets_success(self, mock_json_load, mock_file_open, mock_exists):
        mock_exists.return_value = True
        sample_data = [{"id": str(uuid.uuid4()), "name": "Test Snippet", "content": "Content"}]
        mock_json_load.return_value = sample_data

        manager = SnippetManager(filepath=self.test_filepath)

        mock_file_open.assert_called_once_with(self.test_filepath, 'r')
        mock_json_load.assert_called_once()
        self.assertEqual(manager.snippets, sample_data)

    @patch('src.snippets.os.path.exists')
    @patch('src.snippets.open', new_callable=mock_open)
    @patch('src.snippets.json.load')
    def test_load_snippets_json_decode_error(self, mock_json_load, mock_file_open, mock_exists):
        mock_exists.return_value = True
        mock_json_load.side_effect = json.JSONDecodeError("Error", "doc", 0)

        # Capture print output to check for error message
        with patch('builtins.print') as mock_print:
            manager = SnippetManager(filepath=self.test_filepath)
            mock_print.assert_any_call(f"Error: Could not decode JSON from {self.test_filepath}. Starting with an empty snippet list.")

        mock_file_open.assert_called_once_with(self.test_filepath, 'r')
        mock_json_load.assert_called_once()
        self.assertEqual(manager.snippets, [])

    @patch('src.snippets.open', new_callable=mock_open)
    @patch('src.snippets.json.dump')
    def test_save_snippets_success(self, mock_json_dump, mock_file_open):
        manager = SnippetManager(filepath=self.test_filepath)
        test_snippet = {"id": str(uuid.uuid4()), "name": "Save Test", "content": "Data to save"}
        manager.snippets = [test_snippet]

        manager._save_snippets()

        mock_file_open.assert_called_once_with(self.test_filepath, 'w')
        mock_json_dump.assert_called_once_with([test_snippet], mock_file_open.return_value, indent=2)

    @patch('src.snippets.open', new_callable=mock_open)
    def test_save_snippets_io_error(self, mock_file_open):
        mock_file_open.side_effect = IOError("Disk full")
        manager = SnippetManager(filepath=self.test_filepath)
        manager.snippets = [{"id": "1", "name": "Test", "content": "Content"}]

        with patch('builtins.print') as mock_print:
            manager._save_snippets() # Call the method that should handle the error
            mock_print.assert_any_call(f"Error: Could not save snippets to {self.test_filepath}: Disk full")


    @patch.object(SnippetManager, '_save_snippets') # Mock _save_snippets to prevent actual file I/O
    def test_add_snippet_success(self, mock_save):
        manager = SnippetManager(filepath=self.test_filepath)
        self.assertEqual(len(manager.snippets), 0)

        added_snippet = manager.add_snippet("New Name", "New Content", "python", "Category", ["tag1"])

        self.assertIsNotNone(added_snippet)
        self.assertEqual(len(manager.snippets), 1)
        self.assertEqual(manager.snippets[0]['name'], "New Name")
        self.assertEqual(manager.snippets[0]['content'], "New Content")
        self.assertEqual(manager.snippets[0]['language'], "python")
        self.assertEqual(manager.snippets[0]['category'], "Category")
        self.assertEqual(manager.snippets[0]['tags'], ["tag1"])
        self.assertTrue(uuid.UUID(manager.snippets[0]['id'])) # Check if ID is a valid UUID
        mock_save.assert_called_once()

    @patch.object(SnippetManager, '_save_snippets')
    def test_add_snippet_validation(self, mock_save):
        manager = SnippetManager(filepath=self.test_filepath)

        with patch('builtins.print') as mock_print:
            snippet1 = manager.add_snippet("", "Content") # Empty name
            mock_print.assert_any_call("Error: Snippet name cannot be empty.")
            self.assertIsNone(snippet1)

            snippet2 = manager.add_snippet("Name", "  ") # Whitespace content
            mock_print.assert_any_call("Error: Snippet content cannot be empty.")
            self.assertIsNone(snippet2)

        self.assertEqual(len(manager.snippets), 0)
        mock_save.assert_not_called()

    def test_list_snippets(self):
        manager = SnippetManager(filepath=self.test_filepath)
        manager.snippets = [{"id": "1", "name": "Test", "content": "Content"}]
        self.assertEqual(manager.list_snippets(), [{"id": "1", "name": "Test", "content": "Content"}])
        # Ensure it returns a copy
        list_copy = manager.list_snippets()
        list_copy.append({"id": "2"})
        self.assertEqual(len(manager.snippets), 1)


    def test_get_snippet_by_id(self):
        manager = SnippetManager(filepath=self.test_filepath)
        snippet_id = str(uuid.uuid4())
        test_snippet = {"id": snippet_id, "name": "Find Me", "content": "Here I am"}
        manager.snippets = [test_snippet]

        self.assertEqual(manager.get_snippet_by_id(snippet_id), test_snippet)
        self.assertIsNone(manager.get_snippet_by_id(str(uuid.uuid4()))) # Non-existent ID

    @patch.object(SnippetManager, '_save_snippets')
    def test_update_snippet_success(self, mock_save):
        manager = SnippetManager(filepath=self.test_filepath)
        snippet_id = str(uuid.uuid4())
        original_snippet = {"id": snippet_id, "name": "Original", "content": "Original Content", "language": "py", "category": "OrigCat", "tags": ["orig"]}
        manager.snippets = [original_snippet.copy()] # Work with a copy

        updated_snippet = manager.update_snippet(snippet_id, name="Updated Name", content="Updated Content", tags=["newtag"])

        self.assertIsNotNone(updated_snippet)
        self.assertEqual(updated_snippet['name'], "Updated Name")
        self.assertEqual(updated_snippet['content'], "Updated Content")
        self.assertEqual(updated_snippet['language'], "py") # Unchanged
        self.assertEqual(updated_snippet['tags'], ["newtag"])
        mock_save.assert_called_once()
        self.assertEqual(manager.snippets[0]['name'], "Updated Name")

    @patch.object(SnippetManager, '_save_snippets')
    def test_update_snippet_no_changes(self, mock_save):
        manager = SnippetManager(filepath=self.test_filepath)
        snippet_id = str(uuid.uuid4())
        original_snippet = {"id": snippet_id, "name": "Original", "content": "Content"}
        manager.snippets = [original_snippet.copy()]

        updated_snippet = manager.update_snippet(snippet_id, name="Original") # No actual change
        self.assertIsNotNone(updated_snippet)
        mock_save.assert_not_called() # Save should not be called if no fields changed

    def test_update_snippet_not_found(self):
        manager = SnippetManager(filepath=self.test_filepath)
        self.assertIsNone(manager.update_snippet(str(uuid.uuid4()), name="New Name"))

    @patch.object(SnippetManager, '_save_snippets')
    def test_delete_snippet_success(self, mock_save):
        manager = SnippetManager(filepath=self.test_filepath)
        snippet_id = str(uuid.uuid4())
        manager.snippets = [{"id": snippet_id, "name": "To Delete", "content": "Content"}]

        self.assertTrue(manager.delete_snippet(snippet_id))
        self.assertEqual(len(manager.snippets), 0)
        mock_save.assert_called_once()

    def test_delete_snippet_not_found(self):
        manager = SnippetManager(filepath=self.test_filepath)
        manager.snippets = [{"id": str(uuid.uuid4()), "name": "Some snippet", "content": "Content"}]
        self.assertFalse(manager.delete_snippet(str(uuid.uuid4()))) # Different, non-existent ID
        self.assertEqual(len(manager.snippets), 1)


if __name__ == '__main__':
    unittest.main()
