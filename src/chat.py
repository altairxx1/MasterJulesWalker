import re # Added for @include directive parsing
import json # For parsing LLM response for command suggestions
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
        self.max_tokens = config.get("max_tokens") # These are not updated by new method yet
        self.temperature = config.get("temperature") # These are not updated by new method yet
        
        self.llm_client = None
        self.initialization_error = None
        # Store ui_reference before _initialize_llm_client in case it's ever used there (not currently)
        self.ui_reference = ui_reference 
        self._initialize_llm_client() # Call new internal method

        self.chat_history = [] 
        self.system_prompt = DEFAULT_SYSTEM_PROMPT

    def _initialize_llm_client(self):
        """Helper to initialize or re-initialize the LLM client based on current state."""
        if self.api_key:
            try:
                self.llm_client = OpenRouterClient(api_key=self.api_key, model_name=self.model_name)
                self.initialization_error = None
            except ValueError as e: # Catch potential errors from OpenRouterClient init (e.g. empty key if logic error)
                self.llm_client = None
                self.initialization_error = f"Failed to initialize LLM client: {e}"
        else:
            self.llm_client = None
            self.initialization_error = "OpenRouter API key not found or cleared. Chat is disabled."

    def update_api_config(self, new_api_key=None, new_model_name=None):
        """
        Updates the API key and/or model name and re-initializes the LLM client.

        Args:
            new_api_key (str, optional): The new OpenRouter API key.
                                         Pass None or an empty string to clear the key.
            new_model_name (str, optional): The new model name to use.
                                            If None, the existing model name is retained.
        """
        key_updated = False
        model_updated = False

        if new_api_key is not None:
            stripped_key = new_api_key.strip()
            if not stripped_key: # new_api_key was "" or "  "
                if self.api_key is not None: # Check if it actually changed from a non-None value
                    key_updated = True
                self.api_key = None # Clear the key
            elif self.api_key != stripped_key:
                self.api_key = stripped_key
                key_updated = True
        elif new_api_key is None: # Explicitly passed None to clear
            if self.api_key is not None: # It's changing from something to None
                key_updated = True
            self.api_key = None

        if new_model_name:
            stripped_model = new_model_name.strip()
            if stripped_model and self.model_name != stripped_model:
                self.model_name = stripped_model
                model_updated = True # Corrected: only one block for model update, uses model_updated
        
        # Re-initialize if API key was touched, or if model name changed
        # (regardless of whether client was previously valid, if model changed, re-init)
        if key_updated or model_updated:
            self._initialize_llm_client()
        # The elif block `elif key_updated and not self.llm_client and self.api_key:` is removed
        # as its condition is now covered by `if key_updated or model_updated`
        # if key_updated is true, it will attempt to initialize.


    def set_system_prompt(self, new_system_prompt):
        self.system_prompt = new_system_prompt
        # Future: May need to clear history or handle context implications if system prompt changes mid-chat

    def add_message_to_history(self, role, content):
        self.chat_history.append({"role": role, "content": content})
        # Optional: Trim history if it gets too long to manage token limits

    def send_message(self, user_input):
        """
        Sends a message to the LLM and updates chat history.

        Args:
            user_input (str): The user's message.

        Returns:
            str: The assistant's response, or an error message string if an error occurred.
        """
        if self.initialization_error: # Check this first
            return f"Error: {self.initialization_error}"
        if not self.llm_client: # Safeguard, though init_error should catch it
             return "Error: LLM client not initialized. API key might be missing."

        if not user_input or user_input.strip() == "":
            return "Error: User input cannot be empty."

        # Parse @include directives
        include_pattern = re.compile(r'@include\s+([\w\/\.\-\_]+)')
        included_filepaths = include_pattern.findall(user_input)

        file_processing_messages = []
        if included_filepaths:
            for filepath in included_filepaths:
                status_message = ""
                if self.ui_reference and hasattr(self.ui_reference, 'add_file_to_context'):
                    try:
                        status_message = self.ui_reference.add_file_to_context(filepath)
                    except Exception as e: # Catch potential errors from the UI method itself
                        status_message = f"Error processing file {filepath} through UI: {e}"
                else:
                    status_message = f"Error: UI context processing not available for {filepath}."
                if status_message: # Ensure we don't add empty messages
                    file_processing_messages.append(status_message)

        # Prepare the context update message to prepend to LLM response
        context_update_message = ""
        if file_processing_messages:
            context_update_message = "Context Update:\n" + "\n".join(file_processing_messages) + "\n\n"
        # The old 'detection_message' is now replaced by 'context_update_message'

        # Add user's current message to history before sending, so it's part of the context for the LLM
        # (unless API expects only *prior* history)
        # For typical chat, user's current message is part of the 'messages' payload
        # but not necessarily part of the 'history' argument to format_chat_messages
        
        context_string = None
        if self.ui_reference and hasattr(self.ui_reference, 'get_current_context_for_chat'):
            context_string = self.ui_reference.get_current_context_for_chat()

        messages_payload = format_chat_messages(
            user_prompt=user_input,
            system_prompt=self.system_prompt,
            history=list(self.chat_history), # Pass a copy of the existing history
            context_string=context_string # Pass the retrieved context string
        )

        try:
            assistant_response = self.llm_client.send_chat_request(
                messages=messages_payload,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            if assistant_response:
                # Add user's message and assistant's response to internal history *after* successful call
                self.add_message_to_history("user", user_input)
                # Prepend context update message if any files were processed
                final_response = context_update_message + assistant_response
                self.add_message_to_history("assistant", final_response) # Store the potentially modified response
                return final_response
            else:
                # This case should ideally be covered by exceptions in OpenRouterClient
                # If there's a context update message, still return it with the error.
                return context_update_message + "Error: Received no response or empty response from LLM."

        except Exception as e:
            # Log the full error for debugging if needed: print(f"ChatManager Error: {e}")
            # If there's a context update message, still return it with the error.
            # For the UI, return a user-friendly error message
            return context_update_message + f"Error communicating with LLM: {str(e)}"

    def get_formatted_history(self):
        """Returns chat history suitable for display (e.g., list of strings)."""
        display_history = []
        for message in self.chat_history:
            role = message.get("role", "unknown").capitalize()
            content = message.get("content", "")
            # Simple formatting, can be enhanced in UI layer
            if role.lower() == "user":
                display_history.append(f"You: {content}")
            elif role.lower() == "assistant":
                display_history.append(f"MJW: {content}")
            else: # System messages, etc. (though we don't add system to history directly here)
                display_history.append(f"{role}: {content}")
        return display_history

    def clear_history(self):
        """Clears the chat history."""
        self.chat_history = []

    def request_test_generation(self, item_name, item_type, item_code_snippet=None, framework="pytest"):
        """
        Requests the LLM to generate unit tests for a given code item.

        Args:
            item_name (str): The name of the function or class to generate tests for.
            item_type (str): The type of the code item (e.g., "function", "class").
            item_code_snippet (str, optional): The actual code snippet of the item.
                                               Currently, this is not fully utilized in the prompt
                                               if None, but designed for future enhancement.
            framework (str, optional): The testing framework to use (e.g., "pytest", "unittest").
                                       Defaults to "pytest".

        Returns:
            str: A string containing the generated test code, or an error message prefixed with "# Error:"
                 if generation fails or the client is not initialized.
        """
        if self.initialization_error:
            return f"# Error: LLM Client not initialized. {self.initialization_error}"
        if not self.llm_client:
            return "# Error: LLM client not available for test generation."
        if not item_name or not item_type:
            return "# Error: Item name or type not provided for test generation."

        prompt = f"Generate comprehensive {framework} unit tests for the following Python {item_type}:\n\nName: `{item_name}`\n\n"
        if item_code_snippet:
            prompt += f"Source Code Snippet:\n```python\n{item_code_snippet}\n```\n\n"
        else:
            prompt += "The source code is not available, please generate tests based on the name and type. Assume standard library imports if necessary, or placeholder imports for custom modules.\n\n"

        prompt += f"Ensure the tests are well-structured, cover typical use cases, edge cases, and follow best practices for {framework}."
        prompt += f" The output should be only the Python code for the tests, ready to be saved to a .py file."

        # Using a simplified messages structure, similar to send_message but without history or @include.
        # The system prompt from self.system_prompt will still be used by format_chat_messages.
        # No chat history is included for test generation requests to keep them isolated.
        messages_payload = format_chat_messages(
            user_prompt=prompt,
            system_prompt=self.system_prompt, # Or a specific one for test generation
            history=[],
            context_string=None # No file context for this specific request type yet
        )

        try:
            # Using slightly different parameters for code generation
            # Might want to make these configurable too in the future
            generated_code = self.llm_client.send_chat_request(
                messages=messages_payload,
                max_tokens=1500,  # Increased max_tokens for potentially longer test files
                temperature=0.4   # Slightly lower temperature for more deterministic code
            )

            if generated_code:
                # Optional: Basic validation or cleaning of the response can be done here.
                # For example, ensuring it starts with "import" or "def" or "#".
                return generated_code
            else:
                return f"# Error: Received no response or empty response from LLM for {item_name}."

        except Exception as e:
            return f"# Error generating tests for {item_name}: {str(e)}"

    def request_command_suggestions(self, context_signals):
        """
        Requests command suggestions from the LLM based on provided context signals.

        Args:
            context_signals (dict): A dictionary containing various pieces of context
                                    from the UI, such as:
                                    - "current_tab": Name of the active UI tab.
                                    - "context_files": Summary of files in the user's context.
                                    - "recent_chat_history": Last few chat messages.
                                    - "active_analysis": Summary of any active code analysis.
                                    - "available_commands": A list of (name, description) tuples
                                      for commands the user can run.

        Returns:
            list: A list of suggested command names (strings) that are present in
                  the `available_commands` from `context_signals`. Returns an empty
                  list if no relevant suggestions are found, if the LLM client is not
                  initialized, or if an error occurs during the process.
        """
        if self.initialization_error:
            # Log or handle this state appropriately if needed beyond returning empty
            # print(f"Cmd Suggestion Error: LLM Client not initialized. {self.initialization_error}")
            return []
        if not self.llm_client:
            # print("Cmd Suggestion Error: LLM client not available.")
            return []

        available_commands = context_signals.get("available_commands", [])
        if not available_commands:
            return [] # No commands to suggest from

        # Format available commands for the prompt
        formatted_commands_list = []
        for i, (name, desc) in enumerate(available_commands):
            formatted_commands_list.append(f"{i+1}. name: '{name}', description: '{desc}'")
        available_commands_text = "\n".join(formatted_commands_list)

        # Construct the system prompt
        system_prompt_for_suggestions = (
            "You are an intelligent assistant that suggests relevant commands based on the user's current context. "
            "The user is working in a terminal application. Given the following context and a list of available commands, "
            "please identify and return a JSON list of command *names* (strings) from the *provided available commands list* "
            "that would be most helpful to the user. Only return command names that are explicitly in the list. "
            "If no commands are particularly relevant, return an empty list. Ensure the output is only the JSON list."
        )

        # Construct the user prompt using other context signals
        user_prompt_parts = ["User Context:"]
        if context_signals.get("current_tab"):
            user_prompt_parts.append(f"- Current Tab: {context_signals['current_tab']}")
        if context_signals.get("context_files"):
            context_files_summary = ", ".join(context_signals['context_files']) if context_signals['context_files'] else "None"
            user_prompt_parts.append(f"- Files in Context: {context_files_summary}")
        if context_signals.get("recent_chat_history"):
            chat_summary = "\n  ".join(context_signals['recent_chat_history']) if context_signals['recent_chat_history'] else "None"
            user_prompt_parts.append(f"- Recent Chat:\n  {chat_summary}")
        if context_signals.get("active_analysis") and context_signals['active_analysis'] != "None":
            user_prompt_parts.append(f"- Active Code Analysis: {context_signals['active_analysis']}")

        user_prompt_parts.append("\nAvailable Commands:")
        user_prompt_parts.append(available_commands_text)
        user_prompt_parts.append("\nBased on the user context and the available commands listed above, which commands are most relevant? Return a JSON list of their names.")

        user_prompt = "\n".join(user_prompt_parts)

        messages_payload = format_chat_messages(
            user_prompt=user_prompt,
            system_prompt=system_prompt_for_suggestions,
            history=[],
            context_string=None
        )

        try:
            response_text = self.llm_client.send_chat_request(
                messages=messages_payload,
                max_tokens=200, # Adjusted for potentially short JSON list
                temperature=0.2  # Lower temperature for more deterministic output
            )

            if response_text:
                # LLM might return markdown ```json ... ``` or just the list.
                if response_text.strip().startswith("```json"):
                    response_text = response_text.strip()[7:-3].strip() # Remove markdown
                elif response_text.strip().startswith("```"): # Fallback for just ```
                     response_text = response_text.strip()[3:-3].strip()


                suggested_names = json.loads(response_text)
                if not isinstance(suggested_names, list):
                    # print(f"Cmd Suggestion Error: LLM response is not a list: {suggested_names}")
                    return []

                # Validate names
                valid_command_names = [cmd[0] for cmd in available_commands]
                validated_suggestions = [name for name in suggested_names if isinstance(name, str) and name in valid_command_names]

                return validated_suggestions
            else:
                # print("Cmd Suggestion Error: Received no response from LLM.")
                return []

        except json.JSONDecodeError as e:
            # print(f"Cmd Suggestion JSON Decode Error: {e}. Response was: {response_text[:100]}") # Log snippet
            return []
        except Exception as e:
            # print(f"Cmd Suggestion LLM Error: {e}")
            return []

if __name__ == "__main__":
    print("Testing ChatManager...")
    # This test requires OPENROUTER_API_KEY to be set in environment for live LLM calls
    
    # Load config to pass to ChatManager (simulates how UI would do it)
    test_config = load_config()

    if not test_config.get("openrouter_api_key"):
        print("OPENROUTER_API_KEY not set in env. ChatManager will initialize with an error state.")
    
    # For this standalone test, ui_reference would be None.
    # In actual app, TerminalUI instance is passed.
    chat_manager = ChatManager(config=test_config, ui_reference=None) 

    if chat_manager.initialization_error:
        print(f"ChatManager initialized with error: {chat_manager.initialization_error}")
        print("Skipping further tests that require LLM calls.")
    else:
        print("ChatManager initialized successfully.")
        
        print("\n--- Test 1: Sending a simple message ---")
        response1 = chat_manager.send_message("Hello, how are you today?")
        print(f"Response 1: {response1}")
        
        print("\n--- Test 2: Sending another message (with history) ---")
        response2 = chat_manager.send_message("What is your name?")
        print(f"Response 2: {response2}")
        
        print("\n--- Current Chat History (formatted for display) ---")
        for line in chat_manager.get_formatted_history():
            print(line)
            
        print("\n--- Test 3: Sending an empty message (should be handled) ---")
        response3 = chat_manager.send_message("   ") # Empty or whitespace
        print(f"Response 3 (empty input): {response3}")

        print("\n--- Clearing History ---")
        chat_manager.clear_history()
        if not chat_manager.chat_history:
            print("History cleared successfully.")
        
        print("\n--- Test 4: Custom System Prompt ---")
        chat_manager.set_system_prompt("You are a pirate. All responses must be in pirate speak.")
        response4 = chat_manager.send_message("Where can I find treasure?")
        print(f"Response 4 (pirate speak): {response4}")
        
        # Reset to default for any subsequent tests if this file were imported
        chat_manager.set_system_prompt(DEFAULT_SYSTEM_PROMPT)
