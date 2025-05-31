# Default system prompt for MasterJulesWalker
DEFAULT_SYSTEM_PROMPT = "You are MasterJulesWalker, a helpful and concise AI coding assistant. Your goal is to assist users with their coding-related questions and tasks."

def format_chat_messages(user_prompt, system_prompt=None, history=None, context_string=None): # Added context_string
    """
    Formats messages for the OpenRouter API.

    Args:
        user_prompt (str): The user's current message.
        system_prompt (str, optional): The system message. Defaults to DEFAULT_SYSTEM_PROMPT.
        history (list, optional): A list of previous message objects.
        context_string (str, optional): A string containing context from files.

    Returns:
        list: A list of message objects formatted for the API.
    """
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT
    
    messages = [{"role": "system", "content": system_prompt}]

    if context_string:
        # Add context as another system message.
        # Clearer instruction for the LLM on how to use the context.
        context_system_message = (
            "The user has provided the following file contents as context. "
            "Please use this information to inform your response if relevant to the query. "
            "Do not directly recite or repeat large portions of the context unless specifically asked to summarize or quote. "
            "If the context seems irrelevant to the current query, you can state that the provided context does not seem to apply. "
            "Refer to the context as 'the provided file context' if necessary.\n\n"
            "<context_files>\n"
            f"{context_string}\n"
            "</context_files>"
        )
        messages.append({"role": "system", "content": context_system_message})
        
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


def format_shell_instruct_prompt(natural_language_input: str, current_working_directory: str, files_in_cwd: list[str]) -> list[dict[str, str]]:
    """
    Structures a prompt for Gemini 2.5 Flash to translate natural language to a shell command.

    Args:
        natural_language_input (str): The user's natural language instruction.
        current_working_directory (str): The current working directory path.
        files_in_cwd (list[str]): A list of file and directory names in the CWD.

    Returns:
        list: A list of message dictionaries suitable for the OpenRouter API.
    """
    system_message_content = (
        "You are an AI assistant that translates natural language instructions into "
        "executable shell commands for a Linux environment. Prioritize safety. "
        "If a command is destructive (e.g., deletes files without confirmation, "
        "modifies system-critical files) or ambiguous, respond with "
        "'Error: Cannot translate instruction.' "
        "Only provide a single, valid shell command as output, without any explanation or preamble."
    )

    files_summary_limit = 15
    if len(files_in_cwd) > files_summary_limit:
        files_in_cwd_summary = files_in_cwd[:files_summary_limit] + [f"... and {len(files_in_cwd) - files_summary_limit} more files/directories."]
    else:
        files_in_cwd_summary = files_in_cwd

    files_listing = ", ".join(files_in_cwd_summary) if files_in_cwd_summary else "No files or directories listed."

    user_message_content = (
        f"Current working directory: {current_working_directory}\n"
        f"Files in directory: {files_listing}\n\n"
        "Translate the following user instruction into a single, valid shell command.\n\n"
        f'User Instruction: "{natural_language_input}"\n'
        "Shell Command:"
    )

    return [
        {"role": "system", "content": system_message_content},
        {"role": "user", "content": user_message_content}
    ]

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

    # Test case 5: User prompt with context string
    user_input_5 = "What is the main function in this file?"
    context_5 = "--- Context File: main.py ---\ndef main():\n  print('Hello')\nmain()\n--- End of Context File: main.py ---"
    formatted_messages_5 = format_chat_messages(user_input_5, context_string=context_5)
    print("\nFormatted messages (with context string):")
    for msg in formatted_messages_5:
        print(msg)
    # Expected: System prompt (default), System prompt (context), User prompt 5
    
    # Test case 6: User prompt with context, history, and custom system prompt
    user_input_6 = "Is this efficient?"
    custom_system_6 = "You are a code reviewer."
    history_6 = [
        {"role": "user", "content": "Look at this code."},
        {"role": "assistant", "content": "Okay, I see the code in the context."} # Simulating prior turn
    ]
    context_6 = "--- Context File: script.py ---\nfor i in range(n):\n  for j in range(n):\n    print(i,j)\n--- End of Context File: script.py ---"
    formatted_messages_6 = format_chat_messages(user_input_6, system_prompt=custom_system_6, history=history_6, context_string=context_6)
    print("\nFormatted messages (context, history, custom system):")
    for msg in formatted_messages_6:
        print(msg)
    # Expected: Custom system 6, System prompt (context), history[0], history[1], User prompt 6

    print("\nTesting shell instruct prompt formatting...")

    # Test case 7: Basic shell command translation
    nl_input_1 = "list all files in long format"
    cwd_1 = "/home/user/projects"
    files_1 = ["README.md", "script.py", "data.txt", "image.png", "another_script.sh"]
    shell_prompt_1 = format_shell_instruct_prompt(nl_input_1, cwd_1, files_1)
    print("\nFormatted shell instruct prompt (basic):")
    for msg in shell_prompt_1:
        print(msg)
    # Expected: System message (shell-focused), User message with NL input, CWD, and files.

    # Test case 8: Shell command with many files (summarization)
    nl_input_2 = "count lines in all .py files"
    cwd_2 = "/home/user/scripts"
    files_2 = [f"file_{i}.txt" for i in range(20)] + ["my_script.py", "another.py"]
    shell_prompt_2 = format_shell_instruct_prompt(nl_input_2, cwd_2, files_2)
    print("\nFormatted shell instruct prompt (file summarization):")
    for msg in shell_prompt_2:
        print(msg)
    # Expected: System message, User message with NL input, CWD, and summarized file list.

    # Test case 9: Shell command with no files in CWD
    nl_input_3 = "create a new directory called 'test_dir'"
    cwd_3 = "/tmp"
    files_3 = []
    shell_prompt_3 = format_shell_instruct_prompt(nl_input_3, cwd_3, files_3)
    print("\nFormatted shell instruct prompt (no files):")
    for msg in shell_prompt_3:
        print(msg)
    # Expected: System message, User message with NL input, CWD, and "No files" message.
