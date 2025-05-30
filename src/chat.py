from .llm import OpenRouterClient
from .prompts import format_chat_messages, DEFAULT_SYSTEM_PROMPT
from .config import load_config # To get API key and model for the client
# No direct import of ui needed here, just passing the reference

class ChatManager:
    def __init__(self, config=None, ui_reference=None): # Added ui_reference
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
        Pass None or empty string for new_api_key to clear it.
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
                self.add_message_to_history("assistant", assistant_response)
                return assistant_response
            else:
                # This case should ideally be covered by exceptions in OpenRouterClient
                return "Error: Received no response or empty response from LLM."

        except Exception as e:
            # Log the full error for debugging if needed: print(f"ChatManager Error: {e}")
            # For the UI, return a user-friendly error message
            return f"Error communicating with LLM: {str(e)}"

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
        self.chat_history = []


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
