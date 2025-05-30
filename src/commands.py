import os
import subprocess
import shlex

# Security Note: Running arbitrary shell commands can be dangerous.
# This implementation assumes commands are predefined or carefully constructed.
# For a real-world application, consider sandboxing or more robust validation.

class CommandRunner:
    def __init__(self, project_root="."):
        self.project_root = os.path.abspath(project_root)
        self.allowed_commands = {
            "list_files": {"command": "ls -la", "desc": "List files in the project root with details."},
            "git_status": {"command": "git status", "desc": "Show git status of the project."},
            "git_diff": {"command": "git diff", "desc": "Show git diff of unstaged changes."},
            "show_pytest_tests": {"command": "pytest --collect-only -q", "desc": "List all available pytest tests."},
            # Example of a command that might take arguments (though current run() doesn't support templating well)
            # "run_pytest_test": {"command": "pytest {}", "desc": "Run a specific pytest test. Arg: test_name"}
        }
        # TODO: Add more commands, potentially load from a config file.
        # TODO: Implement argument passing to commands.

    def list_available_commands(self):
        """Returns a list of (name, description) for available commands."""
        return [(name, cmd_info["desc"]) for name, cmd_info in self.allowed_commands.items()]

    def run_command(self, command_name, args_str=None):
        """
        Runs a predefined command.
        Args:
            command_name (str): The key of the command in self.allowed_commands.
            args_str (str, optional): A string of arguments to append to the command.
                                      Note: This is a simple append, be wary of injection if args are user-supplied.

        Returns:
            tuple: (success (bool), output (str), error (str or None))
        """
        if command_name not in self.allowed_commands:
            return False, f"Error: Command '{command_name}' not found.", None

        command_info = self.allowed_commands[command_name]
        base_command = command_info["command"]
        
        full_command = base_command
        if args_str:
            # Simple concatenation. For commands that take specific args,
            # a more robust templating or argument parsing system would be needed.
            # shlex.split() might be useful if the base_command is complex and args need to be integrated carefully.
            # For now, just append. This is relatively safe if base_command doesn't end with operators.
            full_command += " " + args_str

        try:
            # Using `shlex.split()` for safer command construction.
            # Ensure `base_command` and `args_str` are handled carefully,
            # especially if they can include user-influenced input,
            # though predefined commands here limit that risk.
            
            command_to_run = shlex.split(full_command)

            process = subprocess.Popen(
                command_to_run,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            stdout, stderr = process.communicate(timeout=30) # Timeout to prevent hanging

            if process.returncode == 0:
                return True, stdout.strip(), None
            else:
                error_message = f"Error running command '{command_name}'. Return code: {process.returncode}\n"
                if stderr:
                    error_message += f"Stderr:\n{stderr.strip()}"
                elif stdout: # Some commands output errors to stdout
                    error_message += f"Stdout (might contain error):\n{stdout.strip()}"
                return False, None, error_message

        except FileNotFoundError:
            return False, None, f"Error: The command '{shlex.split(base_command)[0]}' was not found. Is it installed and in PATH?"
        except subprocess.TimeoutExpired:
            return False, None, f"Error: Command '{command_name}' timed out after 30 seconds."
        except Exception as e:
            return False, None, f"An unexpected error occurred while running '{command_name}': {str(e)}"

if __name__ == '__main__':
    print("Testing CommandRunner...")
    runner = CommandRunner(project_root=".") # Assumes script is run from project root

    print("\nAvailable commands:")
    for name, desc in runner.list_available_commands():
        print(f"  - {name}: {desc}")

    print("\n--- Running 'list_files' ---")
    success, output, error = runner.run_command("list_files")
    if success:
        print("Output:\n", output)
    else:
        print("Error:\n", error)

    print("\n--- Running 'git_status' ---")
    # This command will only succeed if in a git repository.
    # The test environment for the agent might not be a git repo.
    success, output, error = runner.run_command("git_status")
    if success:
        print("Output:\n", output)
    else:
        print("Error (may be expected if not in a git repo):\n", error)
        
    print("\n--- Running 'show_pytest_tests' ---")
    # This requires pytest to be installed and some tests to be discoverable.
    # Create a dummy test file for basic pytest discovery.
    dummy_test_content = "def test_example():\n    assert True\n"
    dummy_test_dir = os.path.join(runner.project_root, "tests_for_cmd_runner")
    os.makedirs(dummy_test_dir, exist_ok=True)
    with open(os.path.join(dummy_test_dir, "test_dummy_cmd.py"), "w") as f:
        f.write(dummy_test_content)
        
    success, output, error = runner.run_command("show_pytest_tests")
    if success:
        print("Output:\n", output)
    else:
        print("Error (pytest not installed or no tests found?):\n", error)

    print("\n--- Running a command with simple arguments (git diff HEAD) ---")
    # For this to work, 'git_diff' would need to be defined to accept args,
    # or we add a new command. Let's simulate adding 'HEAD' to 'git diff'.
    # Current run_command just appends.
    success, output, error = runner.run_command("git_diff", "HEAD") # Example: git diff HEAD
    if success:
        print("Output:\n", output)
    else:
        print("Error (may be expected if not in a git repo or no changes):\n", error)


    print("\n--- Running a non-existent command ---")
    success, output, error = runner.run_command("non_existent_cmd")
    if not success and "not found" in error:
        print(f"Correctly handled non-existent command: {error}")
    else:
        print(f"Unexpected result for non-existent command: Success={success}, Output={output}, Error={error}")

    # Clean up dummy test directory
    try:
        import shutil
        if os.path.exists(dummy_test_dir):
            shutil.rmtree(dummy_test_dir)
            print(f"\nCleaned up {dummy_test_dir}")
    except Exception as e:
        print(f"Error cleaning up dummy test dir: {e}")
        
    print("\nCommandRunner test finished.")
