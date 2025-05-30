import os
from . import files # Assuming files.py is in the same directory (src)

MAX_CONTEXT_FILES = 5
MAX_FILE_SIZE_BYTES = 100 * 1024  # 100KB per file
MAX_TOTAL_CONTEXT_SIZE_BYTES = 300 * 1024 # 300KB total

class ContextManager:
    def __init__(self, project_root="."):
        self.project_root = os.path.abspath(project_root)
        self.context_files = [] # List of absolute file paths
        self.context_content = {} # path: content
        self.current_context_size_bytes = 0
        self.error_messages = []

    def _can_add_file(self, filepath):
        self.error_messages.clear()
        if len(self.context_files) >= MAX_CONTEXT_FILES:
            self.error_messages.append(f"Cannot add more than {MAX_CONTEXT_FILES} files to context.")
            return False
        
        try:
            file_size = os.path.getsize(filepath)
        except OSError as e:
            self.error_messages.append(f"Error accessing file {os.path.basename(filepath)}: {e.strerror}")
            return False

        if file_size > MAX_FILE_SIZE_BYTES:
            self.error_messages.append(
                f"File {os.path.basename(filepath)} ({file_size // 1024}KB) "
                f"exceeds max size of {MAX_FILE_SIZE_BYTES // 1024}KB."
            )
            return False
        
        if self.current_context_size_bytes + file_size > MAX_TOTAL_CONTEXT_SIZE_BYTES:
            self.error_messages.append(
                f"Adding {os.path.basename(filepath)} ({file_size // 1024}KB) "
                f"would exceed total context size of {MAX_TOTAL_CONTEXT_SIZE_BYTES // 1024}KB. "
                f"(Current: {self.current_context_size_bytes // 1024}KB)"
            )
            return False
        return True

    def add_file(self, relative_filepath):
        """Adds a file to the context if constraints are met."""
        absolute_filepath = os.path.join(self.project_root, relative_filepath)
        
        if not os.path.isfile(absolute_filepath):
            self.error_messages.append(f"File not found: {relative_filepath}")
            return False

        if absolute_filepath in self.context_files:
            self.error_messages.append(f"{os.path.basename(relative_filepath)} is already in context.")
            return False

        if not self._can_add_file(absolute_filepath):
            return False # error_messages already populated by _can_add_file

        try:
            with open(absolute_filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.context_files.append(absolute_filepath)
            self.context_content[absolute_filepath] = content
            self.current_context_size_bytes += os.path.getsize(absolute_filepath)
            self.error_messages.append(f"Added {os.path.basename(relative_filepath)} to context.")
            return True
        except Exception as e:
            self.error_messages.append(f"Error reading file {os.path.basename(relative_filepath)}: {str(e)}")
            return False

    def remove_file(self, relative_filepath):
        """Removes a file from the context."""
        absolute_filepath = os.path.join(self.project_root, relative_filepath)
        if absolute_filepath in self.context_files:
            try:
                file_size = os.path.getsize(absolute_filepath) # Get size before removing
                self.context_files.remove(absolute_filepath)
                if absolute_filepath in self.context_content:
                    del self.context_content[absolute_filepath]
                self.current_context_size_bytes -= file_size
                self.error_messages.append(f"Removed {os.path.basename(relative_filepath)} from context.")
                return True
            except OSError as e: # Should not happen if it was in context_files, but defensive
                self.error_messages.append(f"Error accessing file during removal: {str(e)}")
                return False
        else:
            self.error_messages.append(f"{os.path.basename(relative_filepath)} not found in context.")
            return False
            
    def get_context_string(self):
        """
        Constructs a string representation of the context, including file contents.
        Prepends each file's content with its relative path.
        """
        if not self.context_files:
            return "No files currently in context."

        full_context_str = "Current context includes the following files:\n\n"
        for abs_path in self.context_files:
            relative_path = os.path.relpath(abs_path, self.project_root)
            content = self.context_content.get(abs_path, "# Error: Content not loaded\n")
            full_context_str += f"--- Context File: {relative_path} ---\n"
            full_context_str += content
            full_context_str += f"\n--- End of Context File: {relative_path} ---\n\n"
        
        # Add info about total size
        full_context_str += (f"Total files in context: {len(self.context_files)}.\n"
                             f"Total context size: {self.current_context_size_bytes // 1024}KB "
                             f"of {MAX_TOTAL_CONTEXT_SIZE_BYTES // 1024}KB limit.\n")
        return full_context_str

    def get_context_summary(self):
        """Returns a list of relative file paths and their sizes."""
        summary = []
        for abs_path in self.context_files:
            relative_path = os.path.relpath(abs_path, self.project_root)
            try:
                size = os.path.getsize(abs_path) // 1024 # KB
                summary.append(f"{relative_path} ({size}KB)")
            except OSError:
                summary.append(f"{relative_path} (Error accessing)")
        return summary

    def get_latest_error(self):
        """Returns the most recent error message, if any."""
        if self.error_messages:
            return self.error_messages[-1]
        return None

    def clear_errors(self):
        self.error_messages.clear()

if __name__ == '__main__':
    print("Testing ContextManager...")
    # Setup dummy project structure for testing
    test_project_root = "test_project_ctx"
    os.makedirs(os.path.join(test_project_root, "src"), exist_ok=True)
    os.makedirs(os.path.join(test_project_root, "data"), exist_ok=True)

    with open(os.path.join(test_project_root, "main.py"), "w") as f:
        f.write("print('Hello from main.py')\n" * 10) # Approx 280 bytes

    with open(os.path.join(test_project_root, "src", "utils.py"), "w") as f:
        f.write("# Utility functions\n" * 500) # Approx 9.5KB

    # Create a large file ( > MAX_FILE_SIZE_BYTES)
    large_file_path = os.path.join(test_project_root, "large.txt")
    with open(large_file_path, "w") as f:
        f.write("This is a large file.\n" * (MAX_FILE_SIZE_BYTES // 20 + 1000)) # Ensure it's > 100KB

    # Create a file that would exceed total context when added with another file
    medium_file_path = os.path.join(test_project_root, "medium.txt")
    # Make it large enough so that utils.py + medium.txt > MAX_TOTAL_CONTEXT_SIZE_BYTES
    # utils.py is ~9.5KB. MAX_TOTAL_CONTEXT_SIZE_BYTES is 300KB.
    # So medium.txt should be > 290.5KB. Let's make it 295KB.
    with open(medium_file_path, "w") as f:
        f.write("This is a medium-large file.\n" * ( (MAX_TOTAL_CONTEXT_SIZE_BYTES - 10*1024) // 28 +100) )


    ctx_manager = ContextManager(project_root=test_project_root)

    # 1. Add a valid file
    print("\n1. Adding main.py...")
    ctx_manager.add_file("main.py")
    print(f"Error: {ctx_manager.get_latest_error()}")
    print(f"Context files: {ctx_manager.get_context_summary()}")
    print(f"Total size: {ctx_manager.current_context_size_bytes} bytes")

    # 2. Add another valid file
    print("\n2. Adding src/utils.py...")
    ctx_manager.add_file(os.path.join("src", "utils.py"))
    print(f"Error: {ctx_manager.get_latest_error()}")
    print(f"Context files: {ctx_manager.get_context_summary()}")
    print(f"Total size: {ctx_manager.current_context_size_bytes} bytes")

    # 3. Try to add an already added file
    print("\n3. Adding main.py again...")
    ctx_manager.add_file("main.py")
    print(f"Error: {ctx_manager.get_latest_error()}")

    # 4. Try to add a non-existent file
    print("\n4. Adding non_existent.py...")
    ctx_manager.add_file("non_existent.py")
    print(f"Error: {ctx_manager.get_latest_error()}")

    # 5. Try to add a file that is too large
    print("\n5. Adding large.txt...")
    ctx_manager.add_file("large.txt")
    print(f"Error: {ctx_manager.get_latest_error()}")

    # 6. Remove a file
    print("\n6. Removing main.py...")
    ctx_manager.remove_file("main.py")
    print(f"Error: {ctx_manager.get_latest_error()}")
    print(f"Context files: {ctx_manager.get_context_summary()}")
    print(f"Total size: {ctx_manager.current_context_size_bytes} bytes")

    # 7. Try to remove a file not in context
    print("\n7. Removing main.py again...")
    ctx_manager.remove_file("main.py")
    print(f"Error: {ctx_manager.get_latest_error()}")
    
    # 8. Add files to hit MAX_CONTEXT_FILES limit (currently 1 file: utils.py)
    print("\n8. Adding more files to hit limit...")
    for i in range(MAX_CONTEXT_FILES - 1): # Already 1 file in context
        fpath = f"file{i}.py"
        with open(os.path.join(test_project_root, fpath), "w") as f: f.write(f"# Content of file{i}.py")
        if not ctx_manager.add_file(fpath):
             print(f"Error adding {fpath}: {ctx_manager.get_latest_error()}")
        else:
            print(f"Added {fpath}. Context files: {len(ctx_manager.context_files)}")
    
    print(f"Context files after additions: {ctx_manager.get_context_summary()}")
    
    # Try adding one more, should fail
    with open(os.path.join(test_project_root, "extra.py"), "w") as f: f.write("# extra")
    print("Adding extra.py (should fail due to count limit)...")
    ctx_manager.add_file("extra.py")
    print(f"Error: {ctx_manager.get_latest_error()}")


    # 9. Clear context and test total size limit
    print("\n9. Clearing context and testing total size limit...")
    # Remove all files first
    # Create a copy of the list of files to iterate over, as we are modifying context_files
    files_to_remove = [os.path.relpath(p, test_project_root) for p in list(ctx_manager.context_files)]
    for rel_path_to_remove in files_to_remove:
        print(f"Removing {rel_path_to_remove} for cleanup...")
        ctx_manager.remove_file(rel_path_to_remove)
    print(f"Context after clear: {ctx_manager.get_context_summary()}, size: {ctx_manager.current_context_size_bytes}")
    ctx_manager.clear_errors()

    print("Adding src/utils.py (approx 9.5KB)...")
    ctx_manager.add_file(os.path.join("src", "utils.py")) # Approx 9.5KB
    print(f"Error: {ctx_manager.get_latest_error()}")
    print(f"Current total size: {ctx_manager.current_context_size_bytes // 1024}KB")

    print("Adding medium.txt (should fail due to total size limit with utils.py)...")
    # This file is designed to be large enough that utils.py + medium.txt > MAX_TOTAL_CONTEXT_BYTES
    ctx_manager.add_file("medium.txt")
    print(f"Error: {ctx_manager.get_latest_error()}")
    print(f"Context files: {ctx_manager.get_context_summary()}")
    print(f"Total size: {ctx_manager.current_context_size_bytes // 1024}KB")

    # 10. Get context string
    print("\n10. Getting context string...")
    # Add main.py back for a smaller context string
    ctx_manager.remove_file(os.path.join("src","utils.py")) # remove utils to make space
    ctx_manager.add_file("main.py")
    context_str = ctx_manager.get_context_string()
    print("--- Generated Context String ---")
    # print only first 500 chars for brevity in test output
    print(context_str[:1000] + "\n[...omitted for brevity...]" if len(context_str) > 1000 else context_str)
    print("--- End of Context String ---")


    # Clean up dummy project
    print("\nCleaning up test directory...")
    try:
        import shutil
        shutil.rmtree(test_project_root)
        print(f"Removed {test_project_root}")
    except Exception as e:
        print(f"Error cleaning up: {e}")

    print("\nContextManager test finished.")
