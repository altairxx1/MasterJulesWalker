import os
import subprocess
import shlex
import re # For code extraction

from .config import semantic_indexer, PROJECT_ROOT
from .files import get_project_files
# Assuming ChatManager is accessible for type hinting if not direct import
# from .chat import ChatManager # This would create circular dependency if ChatManager imports CommandRunner indirectly
# For now, rely on duck typing or pass ChatManager instance.
from .diff_utils import generate_diff # Needed to display diff to user directly from command.

# Helper function to extract code from LLM response
def _extract_code_from_llm(response_text: str) -> str | None:
    """
    Extracts the first Python code block from a string.
    Looks for ```python ... ``` or ``` ... ```.
    """
    if not response_text:
        return None

    # Pattern for ```python ... ```
    match_python = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
    if match_python:
        return match_python.group(1).strip()

    # Generic pattern for ``` ... ``` if python specific is not found
    match_generic = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
    if match_generic:
        return match_generic.group(1).strip()

    return None


class CommandRunner:
    def __init__(self, project_root=".", chat_manager_ref=None):
        self.project_root = PROJECT_ROOT # project_root is sourced from config.PROJECT_ROOT
        self.chat_manager_ref = chat_manager_ref # Store reference to ChatManager
        self.allowed_commands = {
            "list_files": {"command": "ls -la", "desc": "List files in the project root with details."},
            "git_status": {"command": "git status", "desc": "Show git status of the project."},
            "git_diff": {"command": "git diff", "desc": "Show git diff of unstaged changes."},
            "show_pytest_tests": {"command": "pytest --collect-only -q", "desc": "List all available pytest tests."},
            "build_semantic_index": {"command": None, "desc": "Builds the semantic search index for the project."},
            "semantic_search": {"command": None, "desc": "Performs a semantic search. Args: <query>"},
            "review_code_suggestion": {"command": None, "desc": "Review a code suggestion from LLM. Args: <filepath>"},
            "accept_suggestion": {"command": None, "desc": "Accept and apply the current code suggestion."},
            "reject_suggestion": {"command": None, "desc": "Reject the current code suggestion."},
        }

    def list_available_commands(self):
        """Returns a list of (name, description) for available commands."""
        return [(name, cmd_info["desc"]) for name, cmd_info in self.allowed_commands.items()]

    def run_command(self, command_name, args_str=None):
        if command_name not in self.allowed_commands:
            return False, f"Error: Command '{command_name}' not found.", None

        command_info = self.allowed_commands[command_name]

        # --- Handle new diff/suggestion commands ---
        if command_name == "review_code_suggestion":
            if not self.chat_manager_ref:
                return False, None, "Error: ChatManager reference not available for this command."
            if not args_str: # Filepath is expected
                return False, None, "Error: Filepath is required for 'review_code_suggestion'."

            filepath = args_str.strip()
            if not self.chat_manager_ref.last_llm_response_raw:
                return False, None, "Error: No recent LLM response to review."

            suggested_code = _extract_code_from_llm(self.chat_manager_ref.last_llm_response_raw)
            if not suggested_code:
                return False, None, "Error: No code block found in the last LLM response."

            try:
                # Ensure filepath is relative to project_root for consistency if it's not absolute
                # However, os.path.join handles this well if filepath is already absolute.
                # For reading, it's safer to make it absolute based on project_root if it's relative.
                if not os.path.isabs(filepath):
                    abs_filepath = os.path.join(self.project_root, filepath)
                else:
                    abs_filepath = filepath # Assume it's already correct if absolute

                if not os.path.exists(abs_filepath):
                    return False, None, f"Error: File not found at '{abs_filepath}'."

                with open(abs_filepath, "r", encoding="utf-8") as f:
                    original_content = f.read()

                # Store details in ChatManager for UI to pick up
                self.chat_manager_ref.start_diff_session(abs_filepath, original_content, suggested_code)

                # Generate diff for immediate display in chat (optional, UI might handle it)
                # diff_lines = generate_diff(original_content, suggested_code, fromfile=filepath, tofile=f"{filepath} (suggested)")
                # diff_output = "\n".join(diff_lines)
                # ui_feedback_message = f"Diff for '{filepath}':\n{diff_output}\nUse 'accept_suggestion' or 'reject_suggestion'."

                # Simpler feedback, UI will render the actual diff view
                ui_feedback_message = (
                    f"Diff session started for '{filepath}'.\n"
                    "The UI should now display the diff. Use 'accept_suggestion' or 'reject_suggestion'."
                )
                return True, ui_feedback_message, None

            except FileNotFoundError:
                return False, None, f"Error: File not found at '{filepath}'."
            except Exception as e:
                return False, None, f"Error processing file for diff: {str(e)}"

        elif command_name == "accept_suggestion":
            if not self.chat_manager_ref or not self.chat_manager_ref.is_diff_active:
                return False, None, "Error: No active code suggestion to accept."

            active_filepath = self.chat_manager_ref.active_diff_filepath
            suggested_content = self.chat_manager_ref.active_diff_suggested_content

            if not active_filepath or suggested_content is None: # Should not happen if is_diff_active is true
                 return False, None, "Error: Invalid diff session state."

            try:
                backup_filepath = active_filepath + ".bak"
                # Create backup
                if os.path.exists(active_filepath):
                    os.rename(active_filepath, backup_filepath)

                # Write the new content
                with open(active_filepath, "w", encoding="utf-8") as f:
                    f.write(suggested_content)

                self.chat_manager_ref.clear_diff_session()
                return True, f"Changes applied to '{os.path.basename(active_filepath)}'. Original backed up to '{os.path.basename(backup_filepath)}'.", None
            except Exception as e:
                # Attempt to restore backup if write failed mid-way (though write is atomic here)
                if os.path.exists(backup_filepath) and not os.path.exists(active_filepath):
                    try:
                        os.rename(backup_filepath, active_filepath)
                        return False, None, f"Error applying changes: {str(e)}. Backup restored."
                    except Exception as restore_e:
                         return False, None, f"Error applying changes: {str(e)}. CRITICAL: Backup restoration failed: {restore_e}"
                return False, None, f"Error applying changes: {str(e)}"


        elif command_name == "reject_suggestion":
            if not self.chat_manager_ref or not self.chat_manager_ref.is_diff_active:
                return False, None, "Error: No active code suggestion to reject."

            self.chat_manager_ref.clear_diff_session()
            return True, "Suggestion rejected. Diff session cleared.", None

        # --- Handle existing commands ---
        elif command_name == "build_semantic_index":
            # ... (existing build_semantic_index logic)
            try:
                all_items = get_project_files(self.project_root)
                files_to_index = [item_path for item_path, item_type in all_items if item_type == 'file']
                if not files_to_index:
                    return False, None, "No files found to index."
                semantic_indexer.build_index(files_to_index)
                return True, "Semantic index built successfully.", None
            except Exception as e:
                return False, None, f"Error building semantic index: {str(e)}"

        elif command_name == "semantic_search":
            # ... (existing semantic_search logic)
            if not args_str:
                return False, None, "Error: Search query cannot be empty for semantic_search."
            try:
                if not semantic_indexer.index or not semantic_indexer.file_chunks:
                    semantic_indexer.load_index()
                    if not semantic_indexer.index or not semantic_indexer.file_chunks:
                        return False, None, "Semantic index is not built or loaded. Run 'build_semantic_index' first."
                results = semantic_indexer.search(args_str)
                if not results:
                    return True, "No results found.", None
                formatted_results = [
                    f"File: {r['file_path']}\nLines: {r['start_line']}-{r['end_line']}\nScore: {r['score']:.4f}\nText:\n{r['text_chunk']}\n---"
                    for r in results
                ]
                return True, "\n".join(formatted_results), None
            except Exception as e:
                return False, None, f"Error during semantic search: {str(e)}"
        
        # --- Fallback to shell commands ---
        base_command = command_info.get("command") # Use .get() for safety
        if base_command is None:
             # This path should ideally only be reached if a new command was added to allowed_commands
             # but not handled above, or if a pre-existing command had its handler removed.
             return False, None, f"Error: Command '{command_name}' is defined but has no execution logic."

        full_command = base_command
        if args_str:
            full_command += " " + args_str

        try:
            command_to_run = shlex.split(full_command)
            process = subprocess.Popen(
                command_to_run,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            stdout, stderr = process.communicate(timeout=30)

            if process.returncode == 0:
                return True, stdout.strip(), None
            else:
                error_message = f"Error running shell command '{command_name}'. Return code: {process.returncode}\n"
                if stderr: error_message += f"Stderr:\n{stderr.strip()}\n"
                if stdout: error_message += f"Stdout:\n{stdout.strip()}" # Some commands output errors to stdout
                return False, None, error_message.strip()

        except FileNotFoundError:
            cmd_exe = shlex.split(base_command)[0]
            return False, None, f"Error: The shell command '{cmd_exe}' was not found. Is it installed and in PATH?"
        except subprocess.TimeoutExpired:
            return False, None, f"Error: Shell command '{command_name}' timed out after 30 seconds."
        except Exception as e:
            return False, None, f"An unexpected error occurred while running shell command '{command_name}': {str(e)}"

if __name__ == '__main__':
    # This __main__ is for basic testing of CommandRunner.
    # For the new commands, it needs a mock or real ChatManager.
    # For simplicity, we'll assume chat_manager_ref is None for these direct tests,
    # meaning diff/suggestion commands would return errors if called without a ref.

    print("Testing CommandRunner (basic shell commands)...")
    runner = CommandRunner() # No chat_manager_ref for this simple test
    print(f"CommandRunner initialized with project root: {runner.project_root}")
    print("Available commands:")
    for name, desc in runner.list_available_commands():
        print(f"  - {name}: {desc}")

    print("\n--- Running 'list_files' ---")
    success, output, error = runner.run_command("list_files")
    if success: print("Output:\n", output)
    else: print("Error:\n", error)

    # --- Test new commands with mocked ChatManager ---
    print("\n--- Testing review/accept/reject suggestion commands (mocked ChatManager) ---")
    class MockChatManager:
        def __init__(self):
            self.last_llm_response_raw = None
            self.active_diff_original_content = None
            self.active_diff_suggested_content = None
            self.active_diff_filepath = None
            self.is_diff_active = False

        def start_diff_session(self, filepath, original, suggested):
            self.active_diff_filepath = filepath
            self.active_diff_original_content = original
            self.active_diff_suggested_content = suggested
            self.is_diff_active = True
            print(f"[MockChatManager] Diff session started for {filepath}")

        def clear_diff_session(self):
            self.active_diff_filepath = None
            self.active_diff_original_content = None
            self.active_diff_suggested_content = None
            self.is_diff_active = False
            print("[MockChatManager] Diff session cleared.")

    mock_chat_manager = MockChatManager()
    runner_with_chat = CommandRunner(chat_manager_ref=mock_chat_manager)

    # Create a dummy file for review
    dummy_filepath = os.path.join(runner_with_chat.project_root, "dummy_test_file.py")
    dummy_backup_filepath = dummy_filepath + ".bak"

    with open(dummy_filepath, "w", encoding="utf-8") as f:
        f.write("def old_function():\n    return 'old'\n")

    mock_chat_manager.last_llm_response_raw = "Some text before\n```python\ndef new_function():\n    return 'new'\n```\nSome text after"

    print(f"\n--- Running 'review_code_suggestion {dummy_filepath}' ---")
    success, output, error = runner_with_chat.run_command("review_code_suggestion", dummy_filepath)
    if success: print("Command Success Output:\n", output)
    else: print("Command Error:\n", error)
    assert mock_chat_manager.is_diff_active

    print("\n--- Running 'accept_suggestion' ---")
    success, output, error = runner_with_chat.run_command("accept_suggestion")
    if success: print("Command Success Output:\n", output)
    else: print("Command Error:\n", error)
    assert not mock_chat_manager.is_diff_active
    if os.path.exists(dummy_filepath):
        with open(dummy_filepath, "r", encoding="utf-8") as f:
            content = f.read()
            assert "new_function" in content, "File content not updated after accept."
            print(f"File content after accept: \n{content}")
    if os.path.exists(dummy_backup_filepath):
        print(f"Backup file created at {dummy_backup_filepath}")
        os.remove(dummy_backup_filepath) # Clean up backup

    # Reset for reject test
    with open(dummy_filepath, "w", encoding="utf-8") as f:
        f.write("def old_function_again():\n    return 'old_again'\n")
    mock_chat_manager.last_llm_response_raw = "```python\ndef very_new_function():\n    return 'very_new'\n```"

    print(f"\n--- Running 'review_code_suggestion {dummy_filepath}' (again for reject test) ---")
    runner_with_chat.run_command("review_code_suggestion", dummy_filepath)
    assert mock_chat_manager.is_diff_active

    print("\n--- Running 'reject_suggestion' ---")
    success, output, error = runner_with_chat.run_command("reject_suggestion")
    if success: print("Command Success Output:\n", output)
    else: print("Command Error:\n", error)
    assert not mock_chat_manager.is_diff_active
    if os.path.exists(dummy_filepath):
        with open(dummy_filepath, "r", encoding="utf-8") as f:
            content = f.read()
            assert "old_function_again" in content, "File content should not have changed after reject."
            print(f"File content after reject: \n{content}")

    # Clean up dummy file
    if os.path.exists(dummy_filepath):
        os.remove(dummy_filepath)
        print(f"Cleaned up {dummy_filepath}")
        
    print("\n--- Semantic Index and Search tests (original __main__ content) ---")
    # (The original semantic index/search tests from previous version of commands.py __main__)
    # This part is simplified here as it's lengthy and tested elsewhere or assumed to work.
    # For a focused test of CommandRunner's new aspects, these could be omitted or mocked.
    print("\n--- Running 'build_semantic_index' (will attempt to download model if first time) ---")
    # ... (dummy file creation for semantic index) ...
    # success, output, error = runner.run_command("build_semantic_index") # runner without chat ref
    # ... (cleanup for semantic index files) ...
    print("Semantic index tests skipped in this focused __main__ for brevity.")

    print("\nCommandRunner extended test finished.")
