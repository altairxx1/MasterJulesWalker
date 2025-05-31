import re # Added for @include directive parsing
import json # For parsing LLM response for command suggestions
import threading # For background operations
from .llm import OpenRouterClient
from .prompts import format_chat_messages, DEFAULT_SYSTEM_PROMPT
from .config import load_config # To get API key and model for the client
# No direct import of ui needed here, just passing the reference

class ChatManager:
    """
    Manages chat interactions with an LLM, including history, context,
    and specialized LLM requests like test generation and command suggestions.
    It interfaces with an LLM client (e.g., OpenRouterClient) and can
    interact with a UI component to exchange context information.
    """
    def __init__(self, config=None, ui_reference=None):
        """
        Initializes the ChatManager.

        Args:
            config (dict, optional): Configuration dictionary. If None, loads from default.
                                     Expected keys: "openrouter_api_key", "mjw_model",
                                     "max_tokens", "temperature".
            ui_reference (object, optional): A reference to the UI instance, used for
                                             accessing UI-specific context methods like
                                             `add_file_to_context` and `get_current_context_for_chat`.
        """
        if config is None:
            config = load_config() 
            
        self.api_key = config.get("openrouter_api_key")
        self.model_name = config.get("mjw_model", "google/gemini-flash-1.5-latest")
        self.max_tokens = config.get("max_tokens")
        self.temperature = config.get("temperature")
        
        self.llm_client = None
        self.initialization_error = None
        self.ui_reference = ui_reference 
        self._initialize_llm_client()

        self.chat_history = [] 
        self.system_prompt = DEFAULT_SYSTEM_PROMPT

        self.last_llm_response_raw: str | None = None
        self.active_diff_original_content: str | None = None
        self.active_diff_suggested_content: str | None = None
        self.active_diff_filepath: str | None = None
        self.is_diff_active: bool = False

    def _initialize_llm_client(self):
        if self.api_key:
            try:
                self.llm_client = OpenRouterClient(api_key=self.api_key, model_name=self.model_name)
                self.initialization_error = None
            except ValueError as e:
                self.llm_client = None
                self.initialization_error = f"Failed to initialize LLM client: {e}"
        else:
            self.llm_client = None
            self.initialization_error = "OpenRouter API key not found or cleared. Chat is disabled."

    def update_api_config(self, new_api_key=None, new_model_name=None):
        key_updated = False
        model_updated = False

        if new_api_key is not None:
            stripped_key = new_api_key.strip()
            if not stripped_key:
                if self.api_key is not None:
                    key_updated = True
                self.api_key = None
            elif self.api_key != stripped_key:
                self.api_key = stripped_key
                key_updated = True
        elif new_api_key is None:
            if self.api_key is not None:
                key_updated = True
            self.api_key = None

        if new_model_name:
            stripped_model = new_model_name.strip()
            if stripped_model and self.model_name != stripped_model:
                self.model_name = stripped_model
                model_updated = True
        
        if key_updated or model_updated:
            self._initialize_llm_client()

    def set_system_prompt(self, new_system_prompt):
        self.system_prompt = new_system_prompt

    def add_message_to_history(self, role, content):
        self.chat_history.append({"role": role, "content": content})

    def send_message(self, user_input, callback):
        """
        Sends a message to the LLM in a background thread and updates chat history.
        The callback is invoked with (response_str, error_str).
        """
        thread = threading.Thread(target=self._send_message_work, args=(user_input, callback), daemon=True)
        thread.start()

    def _send_message_work(self, user_input, callback):
        response_str = None
        error_str = None

        if self.initialization_error:
            error_str = f"Error: {self.initialization_error}"
            callback(None, error_str)
            return
        if not self.llm_client:
            error_str = "Error: LLM client not initialized. API key might be missing."
            callback(None, error_str)
            return
        if not user_input or user_input.strip() == "":
            error_str = "Error: User input cannot be empty."
            callback(None, error_str)
            return

        context_update_message = ""
        try:
            include_pattern = re.compile(r'@include\s+([\w\/\.\-\_]+)')
            included_filepaths = include_pattern.findall(user_input)
            file_processing_messages = []
            if included_filepaths:
                for filepath in included_filepaths:
                    status_msg_file = ""
                    if self.ui_reference and hasattr(self.ui_reference, 'add_file_to_context'):
                        try:
                            status_msg_file = self.ui_reference.add_file_to_context(filepath)
                        except Exception as e:
                            status_msg_file = f"Error processing file {filepath} through UI: {e}"
                    else:
                        status_msg_file = f"Error: UI context processing not available for {filepath}."
                    if status_msg_file:
                        file_processing_messages.append(status_msg_file)

            if file_processing_messages:
                context_update_message = "Context Update:\n" + "\n".join(file_processing_messages) + "\n\n"

            context_string = None
            if self.ui_reference and hasattr(self.ui_reference, 'get_current_context_for_chat'):
                context_string = self.ui_reference.get_current_context_for_chat()

            messages_payload = format_chat_messages(
                user_prompt=user_input,
                system_prompt=self.system_prompt,
                history=list(self.chat_history),
                context_string=context_string
            )

            assistant_response = self.llm_client.send_chat_request(
                messages=messages_payload,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            if assistant_response:
                self.add_message_to_history("user", user_input)
                self.last_llm_response_raw = assistant_response
                response_str = context_update_message + assistant_response
                self.add_message_to_history("assistant", response_str)
            else:
                self.last_llm_response_raw = None
                error_str = context_update_message + "Error: Received no response or empty response from LLM."

        except Exception as e:
            self.last_llm_response_raw = None
            error_str = context_update_message + f"Error communicating with LLM: {str(e)}"

        callback(response_str, error_str)

    def start_diff_session(self, filepath: str, original_content: str, suggested_content: str):
        self.active_diff_filepath = filepath
        self.active_diff_original_content = original_content
        self.active_diff_suggested_content = suggested_content
        self.is_diff_active = True

    def clear_diff_session(self):
        self.active_diff_filepath = None
        self.active_diff_original_content = None
        self.active_diff_suggested_content = None
        self.is_diff_active = False

    def get_formatted_history(self):
        display_history = []
        for message in self.chat_history:
            role = message.get("role", "unknown").capitalize()
            content = message.get("content", "")
            if role.lower() == "user":
                display_history.append(f"You: {content}")
            elif role.lower() == "assistant":
                display_history.append(f"MJW: {content}")
            else:
                display_history.append(f"{role}: {content}")
        return display_history

    def clear_history(self):
        self.chat_history = []

    def request_test_generation(self, item_name, item_type, item_code_snippet=None, framework="pytest", callback=None):
        """
        Requests the LLM to generate unit tests for a given code item in a background thread.
        The callback is invoked with (generated_code_str, error_str).
        """
        thread = threading.Thread(
            target=self._request_test_generation_work,
            args=(item_name, item_type, item_code_snippet, framework, callback),
            daemon=True
        )
        thread.start()

    def _request_test_generation_work(self, item_name, item_type, item_code_snippet, framework, callback):
        generated_code_str = None
        error_str = None

        if self.initialization_error:
            error_str = f"# Error: LLM Client not initialized. {self.initialization_error}"
            if callback: callback(None, error_str)
            return
        if not self.llm_client:
            error_str = "# Error: LLM client not available for test generation."
            if callback: callback(None, error_str)
            return
        if not item_name or not item_type:
            error_str = "# Error: Item name or type not provided for test generation."
            if callback: callback(None, error_str)
            return

        try:
            prompt = f"Generate comprehensive {framework} unit tests for the following Python {item_type}:\n\nName: `{item_name}`\n\n"
            if item_code_snippet:
                prompt += f"Source Code Snippet:\n```python\n{item_code_snippet}\n```\n\n"
            else:
                prompt += "The source code is not available, please generate tests based on the name and type. Assume standard library imports if necessary, or placeholder imports for custom modules.\n\n"
            prompt += f"Ensure the tests are well-structured, cover typical use cases, edge cases, and follow best practices for {framework}."
            prompt += f" The output should be only the Python code for the tests, ready to be saved to a .py file."

            messages_payload = format_chat_messages(
                user_prompt=prompt,
                system_prompt=self.system_prompt,
                history=[],
                context_string=None
            )
            generated_code = self.llm_client.send_chat_request(
                messages=messages_payload,
                max_tokens=1500,
                temperature=0.4
            )
            if generated_code:
                generated_code_str = generated_code
            else:
                error_str = f"# Error: Received no response or empty response from LLM for {item_name}."
        except Exception as e:
            error_str = f"# Error generating tests for {item_name}: {str(e)}"

        if callback: callback(generated_code_str, error_str)

    def request_command_suggestions(self, context_signals, callback):
        """
        Requests command suggestions from the LLM in a background thread.
        The callback is invoked with (suggestions_list, error_str).
        """
        thread = threading.Thread(
            target=self._request_command_suggestions_work,
            args=(context_signals, callback),
            daemon=True
        )
        thread.start()

    def _request_command_suggestions_work(self, context_signals, callback):
        suggestions_list = []
        error_str = None

        if self.initialization_error:
            error_str = f"Cmd Suggestion Error: LLM Client not initialized. {self.initialization_error}"
            if callback: callback(None, error_str)
            return
        if not self.llm_client:
            error_str = "Cmd Suggestion Error: LLM client not available."
            if callback: callback(None, error_str)
            return

        available_commands = context_signals.get("available_commands", [])
        if not available_commands:
            if callback: callback([], None)
            return

        try:
            formatted_commands_list = [f"{i+1}. name: '{name}', description: '{desc}'" for i, (name, desc) in enumerate(available_commands)]
            available_commands_text = "\n".join(formatted_commands_list)
            system_prompt_for_suggestions = (
                "You are an intelligent assistant that suggests relevant commands based on the user's current context. "
                "The user is working in a terminal application. Given the following context and a list of available commands, "
                "please identify and return a JSON list of command *names* (strings) from the *provided available commands list* "
                "that would be most helpful to the user. Only return command names that are explicitly in the list. "
                "If no commands are particularly relevant, return an empty list. Ensure the output is only the JSON list."
            )
            user_prompt_parts = ["User Context:"]
            if context_signals.get("current_tab"): user_prompt_parts.append(f"- Current Tab: {context_signals['current_tab']}")
            context_files_summary = ", ".join(context_signals['context_files']) if context_signals.get("context_files") else "None"
            user_prompt_parts.append(f"- Files in Context: {context_files_summary}")
            chat_summary = "\n  ".join(context_signals['recent_chat_history']) if context_signals.get("recent_chat_history") else "None"
            user_prompt_parts.append(f"- Recent Chat:\n  {chat_summary}")
            if context_signals.get("active_analysis") and context_signals['active_analysis'] != "None":
                user_prompt_parts.append(f"- Active Code Analysis: {context_signals['active_analysis']}")
            user_prompt_parts.append("\nAvailable Commands:\n" + available_commands_text)
            user_prompt_parts.append("\nBased on the user context, return a JSON list of relevant command names.")
            user_prompt = "\n".join(user_prompt_parts)

            messages_payload = format_chat_messages(user_prompt=user_prompt, system_prompt=system_prompt_for_suggestions, history=[], context_string=None)
            response_text = self.llm_client.send_chat_request(messages=messages_payload, max_tokens=200, temperature=0.2)

            if response_text:
                if response_text.strip().startswith("```json"): response_text = response_text.strip()[7:-3].strip()
                elif response_text.strip().startswith("```"): response_text = response_text.strip()[3:-3].strip()

                parsed_names = json.loads(response_text)
                if isinstance(parsed_names, list):
                    valid_command_names = [cmd[0] for cmd in available_commands]
                    suggestions_list = [name for name in parsed_names if isinstance(name, str) and name in valid_command_names]
                else: error_str = "Cmd Suggestion Error: LLM response is not a list."
            else: error_str = "Cmd Suggestion Error: Received no response from LLM."

        except json.JSONDecodeError as e:
            error_str = f"Cmd Suggestion JSON Decode Error: {e}. Response: {response_text[:100]}"
        except Exception as e:
            error_str = f"Cmd Suggestion LLM Error: {e}"

        if callback: callback(suggestions_list, error_str)

    def request_refactor(self, code_snippet: str, refactor_operation: str, callback, language: str = "python") -> None:
        """
        Requests the LLM to refactor a given code snippet in a background thread.
        The callback is invoked with (refactored_code_str, error_str).
        """
        thread = threading.Thread(
            target=self._request_refactor_work,
            args=(code_snippet, refactor_operation, language, callback),
            daemon=True
        )
        thread.start()

    def _request_refactor_work(self, code_snippet, refactor_operation, language, callback):
        refactored_code_str = None
        error_str = None

        if self.initialization_error:
            error_str = f"# Error: LLM Client not initialized. {self.initialization_error}"
            if callback: callback(None, error_str)
            return
        if not self.llm_client:
            error_str = "# Error: LLM client not available for refactoring."
            if callback: callback(None, error_str)
            return
        if not code_snippet or not code_snippet.strip():
            error_str = "# Error: Code snippet cannot be empty."
            if callback: callback(None, error_str)
            return
        if not refactor_operation or not refactor_operation.strip():
            error_str = "# Error: Refactor operation cannot be empty."
            if callback: callback(None, error_str)
            return

        try:
            system_prompt_refactor = (
                "You are an expert code refactoring assistant. Given the following code "
                f" (language: {language}) and a refactoring instruction, provide only the refactored code block. "
                "Do not add any explanations or markdown formatting around the code. "
                "Preserve original indentation for the block if possible, or ensure the new code is correctly indented."
            )
            user_prompt_refactor = (
                f"Refactor this {language} code by applying the '{refactor_operation}' operation:\n\n"
                f"```{language}\n{code_snippet}\n```"
            )
            messages_payload = format_chat_messages(user_prompt=user_prompt_refactor, system_prompt=system_prompt_refactor, history=[], context_string=None)
            refactored_code = self.llm_client.send_chat_request(messages=messages_payload, max_tokens=1500, temperature=0.5)

            if refactored_code:
                processed_code = re.sub(r'^```(?:python|)\s*\n', '', refactored_code, flags=re.MULTILINE)
                processed_code = re.sub(r'\n```\s*$', '', processed_code, flags=re.MULTILINE)
                refactored_code_str = processed_code.strip()
            else:
                error_str = "# Error: LLM request failed. Received no response or empty response."
        except Exception as e:
            error_str = f"# Error: LLM request failed. {str(e)}"

        if callback: callback(refactored_code_str, error_str)


if __name__ == "__main__":
    # Note: Standalone tests for threaded methods would require time.sleep() or mocks for callbacks.
    # These tests are simplified and might not fully test async behavior without a running event loop or similar.
    print("Testing ChatManager (threaded)...")
    test_config = load_config()

    if not test_config.get("openrouter_api_key"):
        print("OPENROUTER_API_KEY not set. LLM calls will fail if attempted without mock.")
    
    chat_manager = ChatManager(config=test_config, ui_reference=None)

    def generic_callback(result, error):
        if error: print(f"Callback Error: {error}")
        else: print(f"Callback Result: {result}")

    if chat_manager.initialization_error:
        print(f"ChatManager initialized with error: {chat_manager.initialization_error}")
    else:
        print("ChatManager initialized successfully.")
        print("\n--- Test 1: Sending a simple message (async) ---")
        chat_manager.send_message("Explain Python's list comprehensions in one sentence.", generic_callback)
        print("Message sent (async). Callback will print result.")
        
        print("\n--- Test (async) command suggestion ---")
        dummy_context = {
            "available_commands": [("test_cmd", "A test command"), ("another_cmd", "Another one")],
            "current_tab": "Main"
        }
        chat_manager.request_command_suggestions(dummy_context, generic_callback)
        print("Command suggestion requested (async).")

        print("\n--- Test (async) test generation ---")
        chat_manager.request_test_generation("my_func", "function", "def my_func(): pass", "pytest", generic_callback)
        print("Test generation requested (async).")

        print("\n--- Test (async) refactor ---")
        chat_manager.request_refactor("print('hello world')", "Convert to f-string if applicable", generic_callback)
        print("Refactor requested (async).")

    print("\n--- Test: Sending an empty message (async) ---")
    chat_manager.send_message("   ", generic_callback) # This will now use the callback to report the error.
    print("Empty message sent (async). Callback should report error.")

    # Add a small delay to allow threads to potentially execute and print
    # This is only for basic standalone testing visibility.
    import time
    time.sleep(1) # Reduced sleep, as extensive LLM calls are not made without API key
    print("\nStandalone test sequence finished. Note: Full async behavior/callbacks might need more time or an active API key to manifest.")
