import unittest
from unittest.mock import patch, MagicMock, call
from src.chat import ChatManager

# Default config for mocking
MOCK_CONFIG = {
    "openrouter_api_key": "test_api_key_from_config",
    "mjw_model": "test_model_from_config",
    "temperature": 0.5,
    "max_tokens": 1024
}

# DEFAULT_SYSTEM_PROMPT from src.prompts (to avoid direct import if it's complex)
# We'll assume ChatManager sets its self.system_prompt to this.
TEST_DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class TestChatManager(unittest.TestCase):

    @patch('src.chat.load_config', return_value=MOCK_CONFIG) # Outer decorator
    @patch('src.chat.OpenRouterClient')                     # Inner decorator
    # Corrected argument order: inner mock first, then outer mock
    def setUp(self, MockOpenRouterClient_arg, mock_load_config_arg):
        self.mock_load_config = mock_load_config_arg
        self.MockOpenRouterClient = MockOpenRouterClient_arg # This is now the actual OpenRouterClient mock
        self.mock_llm_client_instance = MockOpenRouterClient_arg.return_value # This is now an instance mock

        self.ui_reference_mock = MagicMock()
        self.ui_reference_mock.get_current_context_for_chat.return_value = ""
        # Add mock for add_file_to_context for @include tests
        self.ui_reference_mock.add_file_to_context = MagicMock()

        self.patcher_format_chat = patch('src.chat.format_chat_messages')
        self.mock_format_chat_messages = self.patcher_format_chat.start()
        self.mock_format_chat_messages.side_effect = lambda user_prompt, system_prompt, history, context_string: \
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        # ChatManager will now use the actual DEFAULT_SYSTEM_PROMPT from src.prompts
        self.chat_manager = ChatManager(ui_reference=self.ui_reference_mock)
        # We need to know the actual default system prompt to assert against it if necessary
        # For now, we assume it's TEST_DEFAULT_SYSTEM_PROMPT for consistency if tests rely on its specific content.
        # A better way would be to import it in the test file for comparison.
        # Let's assume self.chat_manager.system_prompt is set correctly by __init__.
        # If tests need a *specific known* system prompt, they should use self.chat_manager.set_system_prompt()
        # or patch DEFAULT_SYSTEM_PROMPT at the test method level.

    def tearDown(self):
        self.patcher_format_chat.stop()

    def test_init_with_ui_reference(self):
        self.assertIsNotNone(self.chat_manager.llm_client)
        self.MockOpenRouterClient.assert_called_once_with(
            api_key=MOCK_CONFIG["openrouter_api_key"],
            model_name=MOCK_CONFIG["mjw_model"]
        )
        self.assertEqual(self.chat_manager.chat_history, [])
        self.assertEqual(self.chat_manager.ui_reference, self.ui_reference_mock)
        # self.assertEqual(self.chat_manager.system_prompt, TEST_DEFAULT_SYSTEM_PROMPT) # This can be asserted if TEST_DEFAULT_SYSTEM_PROMPT is imported from actual src.prompts

    # Removed all specific patches for this method. It will use setUp mocks and actual DEFAULT_SYSTEM_PROMPT.
    def test_init_without_ui_reference(self):
        # The self.patcher_format_chat from setUp is not relevant to __init__ testing.
        # No need to stop/start it here.

        # ChatManager will use:
        # - Actual DEFAULT_SYSTEM_PROMPT (from src.prompts)
        # - self.MockOpenRouterClient (from setUp)
        # - self.mock_load_config (from setUp)
        chat_manager_no_ui = ChatManager(ui_reference=None)

        self.assertIsNotNone(chat_manager_no_ui.llm_client)
        # assert_called_with checks the *last* call. If setUp already called it,
        # this will check the call made by ChatManager(ui_reference=None)
        self.MockOpenRouterClient.assert_called_with(
            api_key=MOCK_CONFIG["openrouter_api_key"],
            model_name=MOCK_CONFIG["mjw_model"]
        )
        self.assertIsNone(chat_manager_no_ui.ui_reference)
        # To assert the actual default system prompt, you would import it:
        # from src.prompts import DEFAULT_SYSTEM_PROMPT as ACTUAL_DEFAULT
        # self.assertEqual(chat_manager_no_ui.system_prompt, ACTUAL_DEFAULT)


    def test_add_message_to_history(self):
        self.chat_manager.add_message_to_history("user", "Hello there!")
        self.assertEqual(len(self.chat_manager.chat_history), 1)
        self.assertEqual(self.chat_manager.chat_history[0], {"role": "user", "content": "Hello there!"})

        self.chat_manager.add_message_to_history("assistant", "General Kenobi!")
        self.assertEqual(len(self.chat_manager.chat_history), 2)
        self.assertEqual(self.chat_manager.chat_history[1], {"role": "assistant", "content": "General Kenobi!"})

    def test_chat_history_grows_with_add_message(self):
        for i in range(15):
            self.chat_manager.add_message_to_history("user", f"Message {i}")
            self.chat_manager.add_message_to_history("assistant", f"Reply {i}")
        self.assertEqual(len(self.chat_manager.chat_history), 30)
        # Actual slicing for API call is responsibility of format_chat_messages, not tested here.

    def test_send_message_success(self):
        self.mock_format_chat_messages.reset_mock()
        self.assertEqual(self.chat_manager.chat_history, []) # Ensure history is empty at start

        user_message = "Tell me a joke."
        mock_response = "Why did the scarecrow win an award? Because he was outstanding in his field!"
        self.mock_llm_client_instance.send_chat_request.return_value = mock_response

        # Configure mock_format_chat_messages for this specific call
        # Clear side_effect from setUp, then set return_value
        self.mock_format_chat_messages.side_effect = None
        # Renamed variable to avoid NameError from previous attempt
        llm_payload_for_test = [
            {"role": "system", "content": self.chat_manager.system_prompt},
            {"role": "user", "content": user_message}
        ]
        self.mock_format_chat_messages.return_value = llm_payload_for_test

        actual_response = self.chat_manager.send_message(user_message)
        self.assertEqual(actual_response, mock_response)

        # Check history: user message and assistant response are added
        self.assertEqual(len(self.chat_manager.chat_history), 2)
        self.assertEqual(self.chat_manager.chat_history[0], {"role": "user", "content": user_message})
        self.assertEqual(self.chat_manager.chat_history[1], {"role": "assistant", "content": mock_response})

        # Check UI update (if UI reference exists)
        # ChatManager itself doesn't call ui_reference.update_chat_display. The main app loop does.
        # So, this assertion should be removed or adapted if ChatManager gets that responsibility.
        # self.ui_reference_mock.update_chat_display.assert_called()

        # Check that format_chat_messages was called correctly
        self.mock_format_chat_messages.assert_called_once_with(
            user_prompt=user_message,
            system_prompt=self.chat_manager.system_prompt,
            history=[],
            context_string=""
        )

        # Check that send_chat_request was called correctly
        self.mock_llm_client_instance.send_chat_request.assert_called_once_with(
            messages=llm_payload_for_test, # Use the defined payload
            max_tokens=MOCK_CONFIG["max_tokens"],
            temperature=MOCK_CONFIG["temperature"]
        )

    def test_send_message_with_context(self):
        user_message = "What about this context?"
        context_text = "This is some important context from the UI."
        self.ui_reference_mock.get_current_context_for_chat.return_value = context_text
        mock_response = "Context considered."
        self.mock_llm_client_instance.send_chat_request.return_value = mock_response

        # Expected payload from format_chat_messages for this test
        expected_payload_for_llm = [
            {"role": "system", "content": self.chat_manager.system_prompt}, # Actual system prompt
            {"role": "system", "content": f"Relevant context:\n{context_text}"},
            {"role": "user", "content": user_message}
        ]
        # Clear side_effect from setUp, then set return_value for this test's specific payload
        self.mock_format_chat_messages.side_effect = None
        self.mock_format_chat_messages.return_value = expected_payload_for_llm

        self.chat_manager.send_message(user_message)

        self.mock_format_chat_messages.assert_called_once_with(
            user_prompt=user_message,
            system_prompt=self.chat_manager.system_prompt, # Actual system prompt
            history=[],
            context_string=context_text
        )
        self.mock_llm_client_instance.send_chat_request.assert_called_once_with(
            messages=expected_payload_for_llm, # Use the same expected_payload here
            max_tokens=MOCK_CONFIG["max_tokens"],
            temperature=MOCK_CONFIG["temperature"]
        )
        # Check history (user msg, assistant response)
        self.assertEqual(self.chat_manager.chat_history[0]["content"], user_message)
        self.assertEqual(self.chat_manager.chat_history[1]["content"], mock_response)


    def test_send_message_api_error(self):
        self.mock_format_chat_messages.reset_mock()
        self.assertEqual(self.chat_manager.chat_history, [])

        user_message = "This will fail."
        error_message = "API Error: Something went wrong"
        self.mock_llm_client_instance.send_chat_request.side_effect = ValueError(error_message)

        response = self.chat_manager.send_message(user_message)

        self.assertEqual(response, f"Error communicating with LLM: {error_message}")
        self.assertEqual(len(self.chat_manager.chat_history), 0)

    def test_send_message_network_error(self):
        self.mock_format_chat_messages.reset_mock()
        self.assertEqual(self.chat_manager.chat_history, [])
        user_message = "This will also fail."
        error_message = "Network problem"
        from requests.exceptions import RequestException
        self.mock_llm_client_instance.send_chat_request.side_effect = RequestException(error_message)

        response = self.chat_manager.send_message(user_message)
        self.assertEqual(response, f"Error communicating with LLM: {error_message}")
        self.assertEqual(len(self.chat_manager.chat_history), 0)

    def test_get_formatted_history(self):
        self.chat_manager.add_message_to_history("user", "User1")
        self.chat_manager.add_message_to_history("assistant", "Assistant1")
        self.chat_manager.add_message_to_history("user", "User2")

        formatted = self.chat_manager.get_formatted_history()
        # Based on src/chat.py: get_formatted_history returns a list of strings
        expected = ["You: User1", "MJW: Assistant1", "You: User2"]
        self.assertEqual(formatted, expected)

    def test_get_formatted_history_empty(self):
        formatted = self.chat_manager.get_formatted_history()
        self.assertEqual(formatted, []) # Expect empty list

    @patch('src.chat.OpenRouterClient')
    def test_update_api_config_success(self, mock_new_open_router_client_class):
        # This test needs to ensure that the ChatManager's OpenRouterClient mock
        # is the one from *this test*, not from setUp, if we want to check calls on it.
        # The setUp one is self.MockOpenRouterClient (class) and self.mock_llm_client_instance (instance)

        # Create a new ChatManager instance for this test to avoid mock confusion from setUp
        # We need to mock load_config and DEFAULT_SYSTEM_PROMPT for its __init__
        with patch('src.chat.load_config', return_value=MOCK_CONFIG), \
             patch('src.chat.DEFAULT_SYSTEM_PROMPT', TEST_DEFAULT_SYSTEM_PROMPT):
            chat_manager_local = ChatManager(ui_reference=None)

        # Ensure the local ChatManager uses the mock provided by this test method's decorator
        chat_manager_local.llm_client = mock_new_open_router_client_class.return_value
        # Or, more directly, patch the client on the instance after it's created with an initial client
        # chat_manager_local.llm_client = MagicMock() # Initial client
        # MockOpenRouterClient_for_update = chat_manager_local.llm_client # This is not the class

        new_api_key = "new_key_123"
        new_model_name = "new_model/updated"

        # We need to ensure that when chat_manager_local._initialize_llm_client() is called,
        # it uses the mock_new_open_router_client_class.
        # The most straightforward way is to patch 'src.chat.OpenRouterClient' for the scope of this call.
        # The decorator @patch('src.chat.OpenRouterClient') for the test method does this.

        mock_new_instance = mock_new_open_router_client_class.return_value

        chat_manager_local.update_api_config(new_api_key=new_api_key, new_model_name=new_model_name)

        self.assertEqual(chat_manager_local.api_key, new_api_key)
        self.assertEqual(chat_manager_local.model_name, new_model_name)
        mock_new_open_router_client_class.assert_called_with(api_key=new_api_key, model_name=new_model_name)
        self.assertEqual(chat_manager_local.llm_client, mock_new_instance)


    @patch('src.chat.OpenRouterClient')
    def test_update_api_config_no_reinit_if_key_missing_or_same(self, mock_open_router_client_class_update):
        # Using the self.chat_manager from setUp.
        # self.MockOpenRouterClient is the class mock from setUp.
        # self.mock_llm_client_instance is the instance mock from setUp.

        original_api_key = self.chat_manager.api_key
        original_model_name = self.chat_manager.model_name

        # Reset the class mock from setUp to check for new calls
        self.MockOpenRouterClient.reset_mock()

        # Test with None key (should clear key and client)
        self.chat_manager.update_api_config(new_api_key=None, new_model_name="some_model")
        self.assertIsNone(self.chat_manager.api_key)
        self.assertIsNone(self.chat_manager.llm_client)
        self.assertEqual(self.chat_manager.model_name, "some_model")
        self.MockOpenRouterClient.assert_not_called() # OpenRouterClient() should not be called if api_key is None

        # Reset to a valid state for next part of test
        self.chat_manager.api_key = original_api_key # Restore
        self.chat_manager.model_name = original_model_name # Restore
        self.chat_manager._initialize_llm_client() # This will call self.MockOpenRouterClient() again
        self.MockOpenRouterClient.reset_mock() # Reset after re-initialization

        # Test with empty string key (should clear key and client)
        self.chat_manager.update_api_config(new_api_key="", new_model_name="another_model")
        self.assertIsNone(self.chat_manager.api_key)
        self.assertIsNone(self.chat_manager.llm_client)
        self.assertEqual(self.chat_manager.model_name, "another_model")
        self.MockOpenRouterClient.assert_not_called()

        # Reset to a valid state
        self.chat_manager.api_key = original_api_key
        self.chat_manager.model_name = original_model_name
        self.chat_manager._initialize_llm_client()
        current_client_instance_before_no_change = self.chat_manager.llm_client # Should be self.mock_llm_client_instance
        self.MockOpenRouterClient.reset_mock()

        # Test with same API key and model (should not re-initialize client)
        self.chat_manager.update_api_config(new_api_key=original_api_key, new_model_name=original_model_name)
        self.assertEqual(self.chat_manager.api_key, original_api_key)
        self.assertEqual(self.chat_manager.model_name, original_model_name)
        # _initialize_llm_client is NOT called if api_key and model are unchanged AND client exists
        # However, the logic in update_api_config is:
        # if key_updated or (model_updated and self.llm_client): self._initialize_llm_client()
        # If nothing changed, key_updated=False, model_updated=False, so no call. This is correct.
        self.MockOpenRouterClient.assert_not_called()
        self.assertEqual(self.chat_manager.llm_client, current_client_instance_before_no_change)

    def test_send_message_system_prompt_handling(self):
        # is_first_message flag is not used. System prompt is always passed to format_chat_messages.

        self.mock_format_chat_messages.reset_mock() # Reset for the first call
        self.assertEqual(self.chat_manager.chat_history, []) # Start with empty history for this test sequence

        self.mock_llm_client_instance.send_chat_request.return_value = "Response 1"
        self.chat_manager.send_message("First message")

        self.assertEqual(len(self.chat_manager.chat_history), 2)
        self.assertEqual(self.chat_manager.chat_history[0]["content"], "First message")

        self.mock_format_chat_messages.assert_called_once_with( # Check first call
            user_prompt="First message",
            system_prompt=self.chat_manager.system_prompt,
            history=[],
            context_string=""
        )

        self.mock_llm_client_instance.reset_mock() # Reset LLM client mock for the second call
        self.mock_format_chat_messages.reset_mock() # Reset format_chat_messages mock for the second call

        self.mock_llm_client_instance.send_chat_request.return_value = "Response 2"
        # History before this call: User1, Assist1
        history_before_second_call = list(self.chat_manager.chat_history) # Copy current history

        self.chat_manager.send_message("Second message")

        self.assertEqual(len(self.chat_manager.chat_history), 4)
        self.assertEqual(self.chat_manager.chat_history[2]["content"], "Second message")

        self.mock_format_chat_messages.assert_called_once_with( # Check second call
            user_prompt="Second message",
            system_prompt=self.chat_manager.system_prompt,
            history=history_before_second_call, # Pass the history as it was before this call
            context_string=""
        )

    # --- Tests for @include functionality ---

    def test_parse_include_directives(self):
        """
        Tests that add_file_to_context is called with correctly parsed filepaths.
        """
        self.mock_llm_client_instance.send_chat_request.return_value = "LLM base response."
        # Reset mock for each scenario
        self.ui_reference_mock.add_file_to_context.reset_mock()

        # Scenario 1: No @include directives
        self.chat_manager.send_message("Hello world")
        self.ui_reference_mock.add_file_to_context.assert_not_called()
        self.ui_reference_mock.add_file_to_context.reset_mock()

        # Scenario 2: One @include directive
        self.chat_manager.send_message("Please check @include path/to/file1.py")
        self.ui_reference_mock.add_file_to_context.assert_called_once_with("path/to/file1.py")
        self.ui_reference_mock.add_file_to_context.reset_mock()

        # Scenario 3: Multiple @include directives
        user_input_multiple = "Analyze @include path/file.txt and @include another/doc.md thanks"
        self.chat_manager.send_message(user_input_multiple)
        expected_calls = [call("path/file.txt"), call("another/doc.md")]
        self.ui_reference_mock.add_file_to_context.assert_has_calls(expected_calls, any_order=True) # Order can vary based on regex.findall
        self.assertEqual(self.ui_reference_mock.add_file_to_context.call_count, 2)
        self.ui_reference_mock.add_file_to_context.reset_mock()

        # Scenario 4: @include with various valid path characters
        self.chat_manager.send_message("Include @include project_A/src-v2/file_name.py and @include docs/API-reference.v1.md")
        expected_calls_complex = [
            call("project_A/src-v2/file_name.py"),
            call("docs/API-reference.v1.md")
        ]
        self.ui_reference_mock.add_file_to_context.assert_has_calls(expected_calls_complex, any_order=True)
        self.assertEqual(self.ui_reference_mock.add_file_to_context.call_count, 2)
        self.ui_reference_mock.add_file_to_context.reset_mock()

        # Scenario 5: @include at start, middle, and end
        self.chat_manager.send_message("@include first.txt then text @include mid/file.py and finally @include end_doc.c")
        expected_calls_positions = [
            call("first.txt"),
            call("mid/file.py"),
            call("end_doc.c")
        ]
        self.ui_reference_mock.add_file_to_context.assert_has_calls(expected_calls_positions, any_order=True)
        self.assertEqual(self.ui_reference_mock.add_file_to_context.call_count, 3)
        self.ui_reference_mock.add_file_to_context.reset_mock()

    def test_send_message_with_include_processing(self):
        """
        Tests that messages from add_file_to_context are prepended to the LLM response.
        """
        user_input = "Analyze @include file1.py and @include file2.txt"
        llm_response = "LLM analysis complete."
        self.mock_llm_client_instance.send_chat_request.return_value = llm_response

        # Configure mock add_file_to_context responses
        def side_effect_func(filepath):
            if filepath == "file1.py":
                return "Successfully added file1.py"
            elif filepath == "file2.txt":
                return "Error: file2.txt not found"
            return "Unknown file"
        self.ui_reference_mock.add_file_to_context.side_effect = side_effect_func

        response = self.chat_manager.send_message(user_input)

        expected_prefix = "Context Update:\nSuccessfully added file1.py\nError: file2.txt not found\n\n"
        self.assertTrue(response.startswith(expected_prefix))
        self.assertTrue(response.endswith(llm_response))

        # Ensure add_file_to_context was called for both files
        self.ui_reference_mock.add_file_to_context.assert_any_call("file1.py")
        self.ui_reference_mock.add_file_to_context.assert_any_call("file2.txt")
        self.assertEqual(self.ui_reference_mock.add_file_to_context.call_count, 2)

        # Test with an API error to ensure prefix is still added
        self.ui_reference_mock.add_file_to_context.reset_mock()
        self.ui_reference_mock.add_file_to_context.side_effect = side_effect_func # re-assign
        api_error_msg = "LLM API is down"
        self.mock_llm_client_instance.send_chat_request.side_effect = Exception(api_error_msg)

        error_response = self.chat_manager.send_message(user_input)
        expected_error_prefix = "Context Update:\nSuccessfully added file1.py\nError: file2.txt not found\n\n"
        self.assertTrue(error_response.startswith(expected_error_prefix))
        self.assertTrue(error_response.endswith(f"Error communicating with LLM: {api_error_msg}"))


    def test_send_message_with_include_no_ui_handler(self):
        """
        Tests behavior when ui_reference is None or lacks add_file_to_context.
        """
        user_input = "Check @include some/file.py"
        llm_response = "LLM processed."
        self.mock_llm_client_instance.send_chat_request.return_value = llm_response
        self.mock_llm_client_instance.send_chat_request.side_effect = None # Clear previous side_effect

        # Scenario 1: ui_reference is None
        original_ui_ref = self.chat_manager.ui_reference
        self.chat_manager.ui_reference = None

        response_no_ui = self.chat_manager.send_message(user_input)
        expected_msg_no_ui = "Context Update:\nError: UI context processing not available for some/file.py\n\n"
        self.assertTrue(response_no_ui.startswith(expected_msg_no_ui))
        self.assertTrue(response_no_ui.endswith(llm_response))

        self.chat_manager.ui_reference = original_ui_ref # Restore

        # Scenario 2: ui_reference lacks add_file_to_context method
        original_add_file_method = self.ui_reference_mock.add_file_to_context
        del self.ui_reference_mock.add_file_to_context
        # or self.ui_reference_mock.add_file_to_context = None # this works if hasattr checks for callable
        # or use a new mock that doesn't have it:
        # temp_mock_ui = MagicMock(spec=[]) # spec ensures it only has attrs explicitly defined
        # self.chat_manager.ui_reference = temp_mock_ui

        response_no_method = self.chat_manager.send_message(user_input)
        expected_msg_no_method = "Context Update:\nError: UI context processing not available for some/file.py\n\n"
        self.assertTrue(response_no_method.startswith(expected_msg_no_method))
        self.assertTrue(response_no_method.endswith(llm_response))

        self.ui_reference_mock.add_file_to_context = original_add_file_method # Restore

    # --- Tests for request_test_generation ---

    def test_request_test_generation_success(self):
        item_name = "my_cool_function"
        item_type = "function"
        framework = "pytest"
        expected_generated_tests = f"# Tests for {item_name}\nimport pytest\ndef test_{item_name}():\n    assert True"

        self.mock_llm_client_instance.send_chat_request.return_value = expected_generated_tests

        # We want the actual format_chat_messages to run to check the prompt.
        # So, we don't mock it here, or ensure the setUp mock is very generic if it affects this.
        # The setUp mock_format_chat_messages is:
        # lambda user_prompt, system_prompt, history, context_string: [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        # This is fine as request_test_generation constructs a user_prompt and passes it.

        response = self.chat_manager.request_test_generation(item_name, item_type, framework=framework)

        self.assertEqual(response, expected_generated_tests)

        self.mock_llm_client_instance.send_chat_request.assert_called_once()
        args, kwargs = self.mock_llm_client_instance.send_chat_request.call_args

        self.assertIn("messages", kwargs)
        messages_payload = kwargs["messages"]

        # Check the user prompt part of the payload (assuming format_chat_messages structure from setUp)
        user_prompt_payload = next((msg for msg in messages_payload if msg["role"] == "user"), None)
        self.assertIsNotNone(user_prompt_payload)

        self.assertIn(f"Generate comprehensive {framework} unit tests", user_prompt_payload["content"])
        self.assertIn(f"Python {item_type}", user_prompt_payload["content"])
        self.assertIn(f"Name: `{item_name}`", user_prompt_payload["content"])
        self.assertIn("source code is not available", user_prompt_payload["content"]) # Since item_code_snippet is None
        self.assertIn(f"best practices for {framework}", user_prompt_payload["content"])
        self.assertIn("only the Python code for the tests", user_prompt_payload["content"])

        self.assertEqual(kwargs.get("max_tokens"), 1500)
        self.assertEqual(kwargs.get("temperature"), 0.4)

    def test_request_test_generation_with_snippet(self):
        item_name = "MyClass"
        item_type = "class"
        framework = "unittest"
        snippet = "class MyClass:\n  pass"
        expected_generated_tests = f"# Tests for {item_name}\nclass TestMyClass(unittest.TestCase):\n    pass"

        self.mock_llm_client_instance.send_chat_request.return_value = expected_generated_tests

        response = self.chat_manager.request_test_generation(item_name, item_type, item_code_snippet=snippet, framework=framework)
        self.assertEqual(response, expected_generated_tests)

        self.mock_llm_client_instance.send_chat_request.assert_called_once()
        args, kwargs = self.mock_llm_client_instance.send_chat_request.call_args
        messages_payload = kwargs["messages"]
        user_prompt_payload = next((msg for msg in messages_payload if msg["role"] == "user"), None)
        self.assertIsNotNone(user_prompt_payload)

        self.assertIn(f"Source Code Snippet:\n```python\n{snippet}\n```", user_prompt_payload["content"])

    def test_request_test_generation_llm_exception(self):
        item_name = "bad_function"
        item_type = "function"
        error_message = "LLM API is down"
        self.mock_llm_client_instance.send_chat_request.side_effect = Exception(error_message)

        response = self.chat_manager.request_test_generation(item_name, item_type)

        expected_error_response = f"# Error generating tests for {item_name}: {error_message}"
        self.assertEqual(response, expected_error_response)

    def test_request_test_generation_missing_params(self):
        response = self.chat_manager.request_test_generation(item_name=None, item_type="function")
        self.assertEqual(response, "# Error: Item name or type not provided for test generation.")

        response = self.chat_manager.request_test_generation(item_name="some_func", item_type=None)
        self.assertEqual(response, "# Error: Item name or type not provided for test generation.")

    def test_request_test_generation_no_llm_client(self):
        # Simulate LLM client not being initialized
        original_client = self.chat_manager.llm_client
        original_init_error = self.chat_manager.initialization_error

        self.chat_manager.llm_client = None
        self.chat_manager.initialization_error = "Test init error"

        response = self.chat_manager.request_test_generation("any_func", "function")
        self.assertEqual(response, f"# Error: LLM Client not initialized. {self.chat_manager.initialization_error}")

        # Restore
        self.chat_manager.llm_client = original_client
        self.chat_manager.initialization_error = original_init_error

    # --- Tests for request_command_suggestions ---

    @patch('src.chat.json.loads') # To inspect what's passed to json.loads if needed
    def test_request_command_suggestions_success(self, mock_json_loads):
        context_signals = {
            "current_tab": "Files",
            "context_files": ["file1.py (10KB)"],
            "recent_chat_history": ["User: Hello"],
            "active_analysis": "Analysis of file1.py",
            "available_commands": [("cmd1", "desc1"), ("cmd2", "desc2"), ("cmd3", "desc3")]
        }
        expected_suggestions = ["cmd1", "cmd2"]
        # Mock what json.loads will return after successful LLM call & markdown stripping
        mock_json_loads.return_value = expected_suggestions

        # Mock the raw LLM response that json.loads will process
        # This raw response needs to be a string that when passed to json.loads (after markdown stripping)
        # results in mock_json_loads.return_value.
        # The actual content of this string doesn't matter as much as json.loads is mocked.
        # However, if we weren't mocking json.loads, this would be important.
        # For this test, we'll assume the LLM returns a string that becomes expected_suggestions.
        self.mock_llm_client_instance.send_chat_request.return_value = '["cmd1", "cmd2"]'


        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, expected_suggestions)

        self.mock_llm_client_instance.send_chat_request.assert_called_once()
        args, kwargs = self.mock_llm_client_instance.send_chat_request.call_args
        self.assertIn("messages", kwargs)
        messages_payload = kwargs["messages"]

        system_prompt_payload = next((msg for msg in messages_payload if msg["role"] == "system"), None)
        user_prompt_payload = next((msg for msg in messages_payload if msg["role"] == "user"), None)
        self.assertIsNotNone(system_prompt_payload)
        self.assertIn("You are an intelligent assistant that suggests relevant commands", system_prompt_payload["content"])

        self.assertIsNotNone(user_prompt_payload)
        self.assertIn("User Context:", user_prompt_payload["content"])
        self.assertIn("- Current Tab: Files", user_prompt_payload["content"])
        self.assertIn("Available Commands:", user_prompt_payload["content"])
        self.assertIn("1. name: 'cmd1', description: 'desc1'", user_prompt_payload["content"])
        self.assertIn("Return a JSON list of their names.", user_prompt_payload["content"])

        self.assertEqual(kwargs.get("max_tokens"), 200)
        self.assertEqual(kwargs.get("temperature"), 0.2)

        # Ensure json.loads was called with the (potentially stripped) response from LLM
        # This mock_llm_client_instance.send_chat_request.return_value is what json.loads should get
        mock_json_loads.assert_called_once_with('["cmd1", "cmd2"]')


    def test_request_command_suggestions_handles_markdown_json(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        # No need to mock json.loads here, testing the stripping logic
        self.mock_llm_client_instance.send_chat_request.return_value = '```json\n["cmd1"]\n```'

        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, ["cmd1"])

    def test_request_command_suggestions_malformed_json(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        self.mock_llm_client_instance.send_chat_request.return_value = '{"cmd1": "cmd2"' # Malformed
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])

    def test_request_command_suggestions_non_list_json(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        self.mock_llm_client_instance.send_chat_request.return_value = '{"command": "cmd1"}' # Valid JSON, but not a list
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])

    def test_request_command_suggestions_llm_exception(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        self.mock_llm_client_instance.send_chat_request.side_effect = Exception("LLM is sleeping")
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])

    def test_request_command_suggestions_filters_invalid_names(self):
        context_signals = {
            "available_commands": [("cmd1", "desc1"), ("cmd2", "desc2")]
        }
        # LLM suggests "cmd3" which is not in available_commands
        self.mock_llm_client_instance.send_chat_request.return_value = '["cmd1", "cmd3"]'
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, ["cmd1"])

    def test_request_command_suggestions_no_llm_client(self):
        original_client = self.chat_manager.llm_client
        original_init_error = self.chat_manager.initialization_error
        self.chat_manager.llm_client = None
        self.chat_manager.initialization_error = "LLM client test error"

        response = self.chat_manager.request_command_suggestions({})
        self.assertEqual(response, [])

        self.chat_manager.llm_client = original_client
        self.chat_manager.initialization_error = original_init_error

    def test_request_command_suggestions_no_available_commands(self):
        context_signals = {"available_commands": []}
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])
        self.mock_llm_client_instance.send_chat_request.assert_not_called()

    def test_request_command_suggestions_empty_llm_response(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        self.mock_llm_client_instance.send_chat_request.return_value = "" # Empty string
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])

    def test_request_command_suggestions_llm_returns_empty_list(self):
        context_signals = {"available_commands": [("cmd1", "desc1")]}
        self.mock_llm_client_instance.send_chat_request.return_value = "[]" # Empty list as JSON
        response = self.chat_manager.request_command_suggestions(context_signals)
        self.assertEqual(response, [])


if __name__ == '__main__':
    unittest.main()
