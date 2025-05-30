import unittest
import os
import json
from unittest.mock import patch, mock_open

# Assuming src.config is the module to test
from src.config import load_config, save_setting # Removed get_config_file_path

# Actual defaults from src/config.py
DEFAULT_CONFIG = {
    "openrouter_api_key": None, # os.getenv default
    "mjw_model": "google/gemini-flash-1.5-latest",
    "max_tokens": 4000, # Comes as int after load_config
    "temperature": 0.1 # Comes as float after load_config
}

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Path to the config file for testing
        self.test_config_file = '.mjw_test_config.json'
        # Patch CONFIG_FILE_PATH in src.config module
        self.patch_config_file_path = patch('src.config.CONFIG_FILE_PATH', self.test_config_file)
        self.mock_config_file_path = self.patch_config_file_path.start()

        # Clean up any existing test config file before each test
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)

    def tearDown(self):
        # Stop patching CONFIG_FILE_PATH
        self.patch_config_file_path.stop()
        # Clean up the test config file after each test
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)

    def test_load_config_defaults(self):
        # Test loading config when no file or env vars are set
        # Clear all environment variables to ensure defaults are used.
        with patch.dict(os.environ, {}, clear=True):
            # Simulate config file not existing
            with patch('src.config.os.path.exists') as mock_exists:
                mock_exists.return_value = False # For CONFIG_FILE_PATH check in _load_from_file
                config = load_config()
                self.assertEqual(config['openrouter_api_key'], DEFAULT_CONFIG['openrouter_api_key'])
                self.assertEqual(config['mjw_model'], DEFAULT_CONFIG['mjw_model'])
                self.assertEqual(config['temperature'], DEFAULT_CONFIG['temperature'])
                self.assertEqual(config['max_tokens'], DEFAULT_CONFIG['max_tokens'])


    @patch.dict(os.environ, {'OPENROUTER_API_KEY': 'env_api_key', 'MJW_MODEL': 'env_model_name', 'MJW_TEMPERATURE': '0.5', 'MJW_MAX_TOKENS': '1000'})
    def test_load_config_env_vars_override_defaults(self):
        # Test environment variables overriding defaults
        with patch('src.config.os.path.exists') as mock_exists: # Mock os.path.exists used by _load_from_file
            mock_exists.return_value = False # Config file does not exist
            config = load_config()
            self.assertEqual(config['openrouter_api_key'], 'env_api_key')
            self.assertEqual(config['mjw_model'], 'env_model_name')
            self.assertEqual(config['temperature'], 0.5) # Env override
            self.assertEqual(config['max_tokens'], 1000) # Env override

    def test_load_config_file_overrides_env_vars_and_defaults(self):
        # Test file settings overriding environment variables and defaults
        file_settings = {
            'openrouter_api_key': 'file_api_key',
            'mjw_model': 'file_model_name',
            'temperature': 0.88,
            # Not including max_tokens, so it should fall back to env/default
        }
        # Create the test config file
        with open(self.test_config_file, 'w') as f:
            json.dump(file_settings, f)

        env_vars = {
            'OPENROUTER_API_KEY': 'env_api_key', # Should be overridden by file
            'MJW_MODEL': 'env_model_name',       # Should be overridden by file
            'MJW_TEMPERATURE': '0.77',         # Should be overridden by file
            'MJW_MAX_TOKENS': '2000'             # Should be used (env, as not in file)
        }
        with patch.dict(os.environ, env_vars):
            # os.path.exists for CONFIG_FILE_PATH (self.test_config_file) should be true
            # open for CONFIG_FILE_PATH should return the content of file_settings
            # We don't need to mock open globally here if the file actually exists and CONFIG_FILE_PATH is patched
            # However, _load_from_file uses the global open, so patching it for specific read is safer
            with patch('src.config.os.path.exists') as mock_exists:
                mock_exists.return_value = True # Config file exists
                with patch('builtins.open', mock_open(read_data=json.dumps(file_settings))) as mock_file_open:
                    config = load_config()
                    # Ensure it tried to open the (mocked) test config file
                    mock_file_open.assert_any_call(self.test_config_file, 'r', encoding='utf-8')

                    self.assertEqual(config['openrouter_api_key'], 'file_api_key')
                    self.assertEqual(config['mjw_model'], 'file_model_name')
                    self.assertEqual(config['temperature'], 0.88) # File override
                    self.assertEqual(config['max_tokens'], 2000) # From env, as not in file

    def test_save_setting_creates_and_updates_file(self):
        # 1. Save a new key when file does not exist
        mock_open_func_create = mock_open()
        mock_file_handle_create = mock_open_func_create.return_value

        written_content_accumulator_create = []
        def accumulate_write_create(data_written):
            written_content_accumulator_create.append(data_written)
            return len(data_written)
        mock_file_handle_create.write.side_effect = accumulate_write_create

        with patch('src.config.os.path.exists', return_value=False) as mock_exists_create, \
             patch('builtins.open', mock_open_func_create) as mock_open_patch_create:

            save_setting('openrouter_api_key', 'test_key_1')

            mock_exists_create.assert_called_with(self.test_config_file)
            mock_open_patch_create.assert_called_once_with(self.test_config_file, 'w', encoding='utf-8')

            self.assertTrue(mock_file_handle_create.write.called, "mock_file_handle_create.write was not called")

            full_written_str_create = "".join(written_content_accumulator_create)
            self.assertTrue(full_written_str_create.strip(), "Written content for create is empty or only whitespace")

            written_data_1 = json.loads(full_written_str_create)
            self.assertEqual(written_data_1, {'openrouter_api_key': 'test_key_1'})

        # 2. Save another key (mjw_model), file now "exists" and has the first key.
        existing_data_for_read = {'openrouter_api_key': 'test_key_1'}

        mock_open_func_update = mock_open() # General mock for the open function
        mock_read_handle_update = mock_open(read_data=json.dumps(existing_data_for_read)).return_value
        mock_write_handle_update = mock_open_func_update.return_value # This will be used for the actual write

        written_content_accumulator_update = []
        def accumulate_write_update(data_written):
            written_content_accumulator_update.append(data_written)
            return len(data_written)
        mock_write_handle_update.write.side_effect = accumulate_write_update

        with patch('src.config.os.path.exists', return_value=True) as mock_exists_update, \
             patch('builtins.open', mock_open_func_update) as mock_open_patch_update:

            # Configure mock_open_func_update side effect for read and write
            def open_side_effect(path, mode='r', **kwargs):
                if path == self.test_config_file and mode == 'r':
                    return mock_read_handle_update # Use pre-filled handle for read
                elif path == self.test_config_file and mode == 'w':
                    # This ensures that the write handle (which has the accumulator) is returned
                    return mock_write_handle_update
                raise FileNotFoundError(f"Unexpected open call: {path}, {mode}")
            mock_open_patch_update.side_effect = open_side_effect

            save_setting('mjw_model', 'test_model_save')

            mock_exists_update.assert_called_with(self.test_config_file)
            mock_open_patch_update.assert_any_call(self.test_config_file, 'r', encoding='utf-8')
            mock_open_patch_update.assert_any_call(self.test_config_file, 'w', encoding='utf-8')

            self.assertTrue(mock_write_handle_update.write.called, "mock_write_handle_update.write was not called")
            full_written_str_update = "".join(written_content_accumulator_update)
            self.assertTrue(full_written_str_update.strip(), "Written content for update is empty or only whitespace")

            written_data_2 = json.loads(full_written_str_update)
            self.assertEqual(written_data_2['openrouter_api_key'], 'test_key_1')
            self.assertEqual(written_data_2['mjw_model'], 'test_model_save')

    def test_load_config_missing_file_uses_defaults_and_env(self):
        # Test that if config file is missing, defaults and env vars are used
        env_vars = {
            'OPENROUTER_API_KEY': 'env_api_key_missing_file',
            # MJW_MODEL is not set in env_vars, so it should use its default from config.py's os.getenv
            # MJW_MAX_TOKENS is not set in env_vars, so it should use its default from config.py's os.getenv
            'MJW_TEMPERATURE': '0.25' # This will be used from env
        }
        with patch.dict(os.environ, env_vars, clear=True): # Clear other env vars, then apply these
            with patch('src.config.os.path.exists') as mock_exists:
                mock_exists.return_value = False # Config file does not exist
                config = load_config()
                self.assertEqual(config['openrouter_api_key'], 'env_api_key_missing_file')
                self.assertEqual(config['mjw_model'], DEFAULT_CONFIG['mjw_model']) # Default
                self.assertEqual(config['max_tokens'], DEFAULT_CONFIG['max_tokens']) # Default from os.getenv in load_config
                self.assertEqual(config['temperature'], 0.25) # Env

    def test_specific_keys_loading_priority(self):
        # Default
        # 1. Defaults
        # Clear all environment variables to ensure defaults are used.
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.config.os.path.exists') as mock_exists: # For _load_from_file
                mock_exists.return_value = False
                config = load_config()
                self.assertEqual(config.get('openrouter_api_key'), DEFAULT_CONFIG['openrouter_api_key'])
                self.assertEqual(config.get('mjw_model'), DEFAULT_CONFIG['mjw_model'])

        # 2. Environment variables override defaults
        env_vars_set = {
            'OPENROUTER_API_KEY': 'env_key_specific',
            'MJW_MODEL': 'env_model_specific'
            # Max_tokens and temperature will use their defaults from os.getenv if not set here
        }
        with patch.dict(os.environ, env_vars_set): # Not clearing, so other MJW_ env vars might be present
            with patch('src.config.os.path.exists') as mock_exists: # For _load_from_file
                mock_exists.return_value = False
                config = load_config()
                self.assertEqual(config['openrouter_api_key'], 'env_key_specific')
                self.assertEqual(config['mjw_model'], 'env_model_specific')

        # 3. File settings override environment variables and defaults
        file_settings = {
            'openrouter_api_key': 'file_key_specific',
            'mjw_model': 'file_model_specific',
            # temperature is not in file, should take from env if set, or default
        }
        # Create the physical test config file (CONFIG_FILE_PATH is patched to self.test_config_file)
        with open(self.test_config_file, 'w') as f:
            json.dump(file_settings, f)

        env_vars_for_file_test = {
            'OPENROUTER_API_KEY': 'env_key_should_be_overridden_by_file',
            'MJW_MODEL': 'env_model_should_be_overridden_by_file',
            'MJW_TEMPERATURE': '0.99' # This should be used as 'temperature' is not in file_settings
        }
        # os.path.exists for self.test_config_file should be True
        # open for self.test_config_file should return the content of file_settings
        # No need to mock open if we are writing the file and src.config.CONFIG_FILE_PATH is correctly patched.
        # The _load_from_file will use the real open with the patched path.
        with patch.dict(os.environ, env_vars_for_file_test):
             # Ensure os.path.exists used by _load_from_file returns True for the patched CONFIG_FILE_PATH
            with patch('src.config.os.path.exists') as mock_exists:
                mock_exists.return_value = True # The (test) config file exists
                # We also need to ensure that 'open' call inside _load_from_file reads the actual content
                # of self.test_config_file. Since CONFIG_FILE_PATH is patched, it will try to open self.test_config_file.
                # No need to mock 'builtins.open' if the file is actually created and CONFIG_FILE_PATH is patched.
                config = load_config()
                self.assertEqual(config['openrouter_api_key'], 'file_key_specific')
                self.assertEqual(config['mjw_model'], 'file_model_specific')
                self.assertEqual(config['temperature'], 0.99) # From env
                self.assertEqual(config['max_tokens'], DEFAULT_CONFIG['max_tokens']) # Default, as not in file or env for this specific sub-test run

        # Clean up the created file for this specific test part if needed, though tearDown handles it.
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)


if __name__ == '__main__':
    unittest.main()
