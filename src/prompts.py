# Default system prompt for MasterJulesWalker
DEFAULT_SYSTEM_PROMPT = "You are MasterJulesWalker, a helpful and concise AI coding assistant. Your goal is to assist users with their coding-related questions and tasks."

def format_chat_messages(user_prompt, system_prompt=None, history=None):
    """
    Formats messages for the OpenRouter API.

    Args:
        user_prompt (str): The user's current message.
        system_prompt (str, optional): The system message. Defaults to DEFAULT_SYSTEM_PROMPT.
        history (list, optional): A list of previous message objects, e.g.,
                                  [{"role": "user", "content": "Previous question"},
                                   {"role": "assistant", "content": "Previous answer"}]

    Returns:
        list: A list of message objects formatted for the API.
    """
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT
    
    messages = [{"role": "system", "content": system_prompt}]
    
    if history:
        # Ensure history items are correctly formatted (role, content)
        # This is a simple pass-through assuming history is already well-formed.
        # More robust validation could be added here.
        for message in history:
            if isinstance(message, dict) and "role" in message and "content" in message:
                messages.append(message)
            # else: log a warning or skip malformed history item

    messages.append({"role": "user", "content": user_prompt})
    
    return messages

if __name__ == "__main__":
    print("Testing prompt formatting...")

    # Test case 1: User prompt only (with default system prompt)
    user_input_1 = "How do I write a for loop in Python?"
    formatted_messages_1 = format_chat_messages(user_input_1)
    print("\nFormatted messages (user prompt only):")
    for msg in formatted_messages_1:
        print(msg)
    # Expected: System prompt, User prompt

    # Test case 2: User prompt with a custom system prompt
    user_input_2 = "Explain recursion."
    custom_system_2 = "You are a computer science professor."
    formatted_messages_2 = format_chat_messages(user_input_2, system_prompt=custom_system_2)
    print("\nFormatted messages (custom system prompt):")
    for msg in formatted_messages_2:
        print(msg)
    # Expected: Custom system prompt, User prompt

    # Test case 3: User prompt with history
    user_input_3 = "What about in JavaScript?"
    history_3 = [
        {"role": "user", "content": "How do I write a for loop in Python?"},
        {"role": "assistant", "content": "You can use `for item in iterable:`."}
    ]
    formatted_messages_3 = format_chat_messages(user_input_3, history=history_3)
    print("\nFormatted messages (with history):")
    for msg in formatted_messages_3:
        print(msg)
    # Expected: System prompt, history[0], history[1], User prompt 3
    
    # Test case 4: User prompt with history and custom system prompt
    user_input_4 = "Any performance considerations?"
    custom_system_4 = "You are a performance optimization expert."
    history_4 = [
        {"role": "user", "content": "Explain bubble sort."},
        {"role": "assistant", "content": "Bubble sort is a simple sorting algorithm..."}
    ]
    formatted_messages_4 = format_chat_messages(user_input_4, system_prompt=custom_system_4, history=history_4)
    print("\nFormatted messages (history and custom system prompt):")
    for msg in formatted_messages_4:
        print(msg)
    # Expected: Custom system 4, history[0], history[1], User prompt 4
