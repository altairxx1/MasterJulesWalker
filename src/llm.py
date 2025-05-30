import os
import json
import requests # External dependency

# Standard Headers for OpenRouter API
OPENROUTER_API_BASE_URL = "https://openrouter.ai/api/v1"
COMMON_HEADERS = {
    "Content-Type": "application/json",
    # HTTP Referer and X-Title are optional but recommended by OpenRouter
    "HTTP-Referer": "https://github.com/user/masterjuleswalker", # Replace with your actual repo URL
    "X-Title": "MasterJulesWalker", # Replace with your actual app name
}

class OpenRouterClient:
    def __init__(self, api_key, model_name="google/gemini-flash-1.5-latest", site_url=None, app_name=None):
        if not api_key:
            raise ValueError("OpenRouter API key is required.")
        
        self.api_key = api_key
        if model_name is None:
            self.model_name = "google/gemini-flash-1.5-latest" # Default model
        else:
            self.model_name = model_name
        self.headers = {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {self.api_key}",
        }
        if site_url:
            self.headers["HTTP-Referer"] = site_url
        if app_name:
            self.headers["X-Title"] = app_name

    def send_chat_request(self, messages, max_tokens=None, temperature=None):
        """
        Sends a chat request to the OpenRouter API.

        Args:
            messages (list): A list of message objects, e.g.,
                             [{"role": "system", "content": "You are a helpful assistant."},
                              {"role": "user", "content": "Hello!"}]
            max_tokens (int, optional): Maximum number of tokens to generate.
            temperature (float, optional): Sampling temperature.

        Returns:
            str: The content of the assistant's reply, or None if an error occurs.
        
        Raises:
            requests.exceptions.RequestException: For network issues.
            ValueError: For API errors or invalid responses.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty.")

        payload = {
            "model": self.model_name,
            "messages": messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        # Other parameters like 'stream': True could be added here

        try:
            response = requests.post(
                f"{OPENROUTER_API_BASE_URL}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30  # Set a reasonable timeout (e.g., 30 seconds)
            )
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            response_data = response.json()

            if response_data.get("choices") and len(response_data["choices"]) > 0:
                first_choice = response_data["choices"][0]
                if first_choice.get("message") and first_choice["message"].get("content"):
                    return first_choice["message"]["content"].strip()
                else:
                    raise ValueError("Invalid response format: 'message' or 'content' missing in choice.")
            else:
                # Log the full response if it's unexpected.
                # print(f"Unexpected API response: {response_data}") 
                error_info = response_data.get("error", {})
                error_msg = error_info.get("message", "No choices returned and no specific error message.")
                # Include more details if available
                code = error_info.get("code")
                param = error_info.get("param")
                err_type = error_info.get("type")
                full_err_msg = f"API Error: {error_msg}"
                if code: full_err_msg += f" (Code: {code})"
                if param: full_err_msg += f" (Param: {param})"
                if err_type: full_err_msg += f" (Type: {err_type})"

                raise ValueError(full_err_msg)

        except requests.exceptions.Timeout:
            raise requests.exceptions.RequestException("API request timed out.")
        except requests.exceptions.RequestException as e:
            # This catches connection errors, HTTP errors (if raise_for_status was not enough), etc.
            raise requests.exceptions.RequestException(f"Network or API request error: {str(e)}")
        except (json.JSONDecodeError, ValueError) as e: # Catch JSON parsing errors or our own ValueErrors
            raise ValueError(f"Error processing API response: {str(e)}")


if __name__ == "__main__":
    print("Testing OpenRouterClient...")
    # Attempt to load API key from environment for testing
    # In a real app, this would come from config.py -> main.py -> ChatManager -> OpenRouterClient
    api_key_from_env = os.getenv("OPENROUTER_API_KEY")
    model_from_env = os.getenv("MJW_MODEL", "google/gemini-flash-1.5-latest") # Default for testing

    if not api_key_from_env:
        print("OPENROUTER_API_KEY environment variable not set. Cannot perform live test.")
    else:
        print(f"Using API Key (last 4 chars): ...{api_key_from_env[-4:]}")
        print(f"Using Model: {model_from_env}")
        
        client = OpenRouterClient(api_key=api_key_from_env, model_name=model_from_env)
        
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant. Respond in one sentence."},
            {"role": "user", "content": "What is the capital of France?"}
        ]
        
        print(f"\nSending test message: {test_messages[1]['content']}")
        
        try:
            response_content = client.send_chat_request(test_messages, max_tokens=50, temperature=0.7)
            if response_content:
                print(f"Assistant's response: {response_content}")
            else:
                print("Received no content in response, but no error raised.")
        except requests.exceptions.RequestException as e:
            print(f"Network or API Request Error during test: {e}")
        except ValueError as e:
            print(f"Value Error or API Error during test: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during test: {e}")

        # Test for expected failure (e.g. invalid model)
        print("\nTesting with a deliberately invalid model name (expecting an error):")
        invalid_model_client = OpenRouterClient(api_key=api_key_from_env, model_name="invalid/nonexistent-model-testing123")
        try:
            response_content = invalid_model_client.send_chat_request(test_messages)
            print(f"Assistant's response (should not happen): {response_content}")
        except ValueError as e:
            print(f"Caught expected error for invalid model: {e}")
        except Exception as e:
            print(f"Caught unexpected error for invalid model test: {e}")
