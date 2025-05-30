import unittest
import json
from unittest.mock import patch, MagicMock

# Assuming src.llm is the module to test
from src.llm import OpenRouterClient
import requests # For requests.exceptions.RequestException

# Mock default config values that might be used by the client if not overridden
MOCK_DEFAULT_CONFIG = {
    "openrouter_api_key": "default_mock_api_key",
    "mjw_model": "default_mock_model/name",
    "max_tokens": 1000,
    "temperature": 0.5
}

class TestOpenRouterClient(unittest.TestCase):

    # Removed @patch('src.llm.load_config') from all tests below

    def test_init_success_with_api_key_arg(self):
        client = OpenRouterClient(api_key="test_key_123", model_name="test_model/actual")
        self.assertEqual(client.api_key, "test_key_123")
        self.assertEqual(client.model_name, "test_model/actual")
        self.assertIn("Authorization", client.headers)
        self.assertEqual(client.headers["Authorization"], "Bearer test_key_123")
        # Check default headers from src.llm.COMMON_HEADERS and class defaults
        # These defaults are in the OpenRouterClient class itself or COMMON_HEADERS constant.
        # From COMMON_HEADERS:
        # "HTTP-Referer": "https://github.com/user/masterjuleswalker"
        # "X-Title": "MasterJulesWalker"
        self.assertEqual(client.headers["HTTP-Referer"], "https://github.com/user/masterjuleswalker")
        self.assertEqual(client.headers["X-Title"], "MasterJulesWalker")

    def test_init_uses_provided_api_key_and_model(self):
        # This test replaces former 'test_init_success_with_config_api_key'
        # It verifies that the constructor arguments are used.
        client = OpenRouterClient(api_key="specific_test_key", model_name="specific_model/name")
        self.assertEqual(client.api_key, "specific_test_key")
        self.assertEqual(client.model_name, "specific_model/name")
        self.assertEqual(client.headers["Authorization"], "Bearer specific_test_key")

    def test_init_model_name_uses_signature_default_if_none(self):
        # The OpenRouterClient has a default for model_name in its signature
        client = OpenRouterClient(api_key="test_key_123", model_name=None)
        self.assertEqual(client.model_name, "google/gemini-flash-1.5-latest") # Default from __init__ signature

    def test_init_raises_value_error_if_no_api_key(self):
        with self.assertRaisesRegex(ValueError, "OpenRouter API key is required."):
            OpenRouterClient(api_key=None) # Pass None directly

    def test_init_raises_value_error_if_empty_api_key(self):
        with self.assertRaisesRegex(ValueError, "OpenRouter API key is required."):
            OpenRouterClient(api_key="") # Pass empty string

    def test_init_custom_headers(self):
        custom_site_url = "https_my_app_com"
        custom_app_name = "My Custom AI"
        client = OpenRouterClient(
            api_key="test_key_custom",
            site_url=custom_site_url,
            app_name=custom_app_name
        )
        self.assertEqual(client.headers["HTTP-Referer"], custom_site_url)
        self.assertEqual(client.headers["X-Title"], custom_app_name)

    @patch('src.llm.requests.post')
    def test_send_chat_request_success(self, mock_post):
        # Instantiate client with necessary params; MOCK_DEFAULT_CONFIG can provide these
        client = OpenRouterClient(
            api_key=MOCK_DEFAULT_CONFIG["openrouter_api_key"],
            model_name=MOCK_DEFAULT_CONFIG["mjw_model"]
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, AI!"}}]
        }
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        # Use values from MOCK_DEFAULT_CONFIG for max_tokens and temperature for consistency in test
        response_content = client.send_chat_request(
            messages,
            max_tokens=MOCK_DEFAULT_CONFIG["max_tokens"],
            temperature=MOCK_DEFAULT_CONFIG["temperature"]
        )

        self.assertEqual(response_content, "Hello, AI!")
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(called_args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(called_kwargs['headers'], client.headers)

        sent_payload = called_kwargs['json']
        self.assertEqual(sent_payload['model'], MOCK_DEFAULT_CONFIG["mjw_model"])
        self.assertEqual(sent_payload['messages'], messages)
        self.assertEqual(sent_payload['max_tokens'], MOCK_DEFAULT_CONFIG["max_tokens"])
        self.assertEqual(sent_payload['temperature'], MOCK_DEFAULT_CONFIG["temperature"])

    @patch('src.llm.requests.post')
    def test_send_chat_request_api_error_400(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 400
        # For OpenRouter, error details are often in response.json()['error']['message']
        # but raise_for_status() will use response.text if .reason is not good.
        # The actual llm.py uses response.text for the error message from raise_for_status.
        # Let's simulate that the text attribute contains the error message.
        mock_response.text = "Bad Request Details From Text"
        mock_post.return_value = mock_response # Set mock_post's return_value to mock_response

        # Now configure mock_response's methods, including raise_for_status
        mock_http_error = requests.exceptions.HTTPError(f"400 Client Error: Bad Request for url. Response Text: {mock_response.text}", response=mock_response)
        mock_response.raise_for_status.side_effect = mock_http_error

        with self.assertRaisesRegex(requests.exceptions.RequestException, "Network or API request error: 400 Client Error: Bad Request for url. Response Text: Bad Request Details From Text"):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_api_error_401(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_post.return_value = mock_response # Set before configuring mock_response

        mock_response.status_code = 401
        mock_response.text = "Unauthorized Access"
        mock_http_error = requests.exceptions.HTTPError(f"401 Client Error: Unauthorized for url. Response Text: {mock_response.text}", response=mock_response)
        mock_response.raise_for_status.side_effect = mock_http_error

        with self.assertRaisesRegex(requests.exceptions.RequestException, "Network or API request error: 401 Client Error: Unauthorized for url. Response Text: Unauthorized Access"):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_api_error_500(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_post.return_value = mock_response # Set before configuring mock_response

        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_http_error = requests.exceptions.HTTPError(f"500 Server Error: Internal Server Error for url. Response Text: {mock_response.text}", response=mock_response)
        mock_response.raise_for_status.side_effect = mock_http_error

        with self.assertRaisesRegex(requests.exceptions.RequestException, "Network or API request error: 500 Server Error: Internal Server Error for url. Response Text: Internal Server Error"):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_network_error(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        # The llm.py code has a specific catch for Timeout, then a general RequestException.
        # This test will simulate a general RequestException that is not a Timeout.
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        with self.assertRaisesRegex(requests.exceptions.RequestException, "Network or API request error: Failed to connect"):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_timeout_error(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        # The llm.py code specifically catches Timeout and re-raises it with a custom message.
        with self.assertRaisesRegex(requests.exceptions.RequestException, "API request timed out."):
             client.send_chat_request([{"role": "user", "content": "Hi"}])


    @patch('src.llm.requests.post')
    def test_send_chat_request_malformed_json_response(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 200

        # The str(e) for a JSONDecodeError("Expecting value", "doc", 0) is "Expecting value: line 1 column 1 (char 0)"
        expected_json_error_str = "Expecting value: line 1 column 1 (char 0)"
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "<html></html>", 0)
        mock_post.return_value = mock_response

        # Need to escape parentheses for regex
        expected_regex = f"Error processing API response: {expected_json_error_str}".replace("(", r"\(").replace(")", r"\)")
        with self.assertRaisesRegex(ValueError, expected_regex):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_missing_choices(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        # The llm.py code will raise "API Error: No choices returned and no specific error message."
        # if choices is missing and no error field is present.
        # If error field is present, it uses that.
        mock_response.json.return_value = {"model": "test_model"} # Missing 'choices'
        mock_post.return_value = mock_response

        # The actual error message from llm.py is more detailed if 'error' is in response_data
        # Here, 'error' is not in response_data, so it defaults.
        with self.assertRaisesRegex(ValueError, "API Error: No choices returned and no specific error message."):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_empty_choices(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []} # Empty 'choices'
        mock_post.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "API Error: No choices returned and no specific error message."):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_missing_message_in_choice(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        # llm.py's error: "Invalid response format: 'message' or 'content' missing in choice."
        mock_response.json.return_value = {"choices": [{"index": 0}]}
        mock_post.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "Invalid response format: 'message' or 'content' missing in choice."):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    @patch('src.llm.requests.post')
    def test_send_chat_request_missing_content_in_message(self, mock_post):
        client = OpenRouterClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant"}}]}
        mock_post.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "Invalid response format: 'message' or 'content' missing in choice."):
            client.send_chat_request([{"role": "user", "content": "Hi"}])

    def test_send_chat_request_empty_messages_list(self):
        client = OpenRouterClient(api_key="test_key")
        with self.assertRaisesRegex(ValueError, "Messages list cannot be empty."):
            client.send_chat_request([])

if __name__ == '__main__':
    unittest.main()
