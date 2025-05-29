import os
import json

CONFIG_FILE_PATH = ".mjw_config.json" # In project root

def _load_from_file():
    """Loads settings from the JSON config file."""
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file not found (e.g. first run) or corrupt, return empty dict
            return {}
    return {}

def _save_to_file(settings_dict):
    """Saves the given settings dictionary to the JSON config file."""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=4)
    except IOError:
        # Handle error (e.g., log it or raise it)
        # For now, print a warning if save fails. UI should give feedback.
        print(f"Warning: Could not save settings to {CONFIG_FILE_PATH}")


def save_setting(key_name, value):
    """Saves a specific setting to the config file."""
    current_settings = _load_from_file()
    current_settings[key_name] = value
    _save_to_file(current_settings)

def load_config():
    """
    Loads configuration settings.
    Priority:
    1. From .mjw_config.json file
    2. From environment variables
    3. Hardcoded defaults
    """
    file_settings = _load_from_file()
    
    config = {}

    # OpenRouter API Key
    config["openrouter_api_key"] = file_settings.get(
        "openrouter_api_key", 
        os.getenv("OPENROUTER_API_KEY")
    )

    # MJW Model
    config["mjw_model"] = file_settings.get(
        "mjw_model",
        os.getenv("MJW_MODEL", "google/gemini-flash-1.5-latest") 
    )
    
    # Max Tokens (example: still from env or default, but could be added to file)
    config["max_tokens"] = int(os.getenv("MJW_MAX_TOKENS", "4000"))
    
    # Temperature (example: still from env or default)
    config["temperature"] = float(os.getenv("MJW_TEMPERATURE", "0.1"))
    
    return config

if __name__ == "__main__":
    print("Initial config (could be from env vars or defaults):")
    initial_conf = load_config()
    for key, value in initial_conf.items():
        if key == "openrouter_api_key" and value:
            print(f"  {key.replace('_', ' ').title()}: Loaded (not shown)")
        else:
            print(f"  {key.replace('_', ' ').title()}: {value}")

    print(f"\nSaving a test API key ('test_api_key_123') and model ('test/model') to {CONFIG_FILE_PATH}...")
    save_setting("openrouter_api_key", "test_api_key_123")
    save_setting("mjw_model", "test/model")

    print("\nConfig after saving settings to file:")
    reloaded_conf_file = load_config()
    for key, value in reloaded_conf_file.items():
        if key == "openrouter_api_key" and value: # Check key exists and has a value
            # For the test API key, we can show it as it's not a real secret
            print(f"  {key.replace('_', ' ').title()}: {value} (from file)")
        elif key == "openrouter_api_key" and not value: # Explicitly state if key is None/empty from file
             print(f"  {key.replace('_', ' ').title()}: Not set in file (or empty value)")
        else:
            print(f"  {key.replace('_', ' ').title()}: {value}")
            
    # Test fallback to env var if file setting is removed (manual step to test this)
    # To fully test env var fallback after file save:
    # 1. Run once to create file.
    # 2. Manually edit .mjw_config.json to remove 'openrouter_api_key'.
    # 3. Set OPENROUTER_API_KEY env var.
    # 4. Run again. load_config() should pick up the env var.
    
    print(f"\nTo clean up, remove the file: {CONFIG_FILE_PATH}")
    # Example: os.remove(CONFIG_FILE_PATH) # Uncomment to auto-cleanup during test script run
