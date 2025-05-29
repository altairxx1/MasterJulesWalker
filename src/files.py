import os
import fnmatch

def parse_gitignore(gitignore_path):
    """
    Parses a .gitignore file and returns a list of patterns.
    For simplicity, this handles basic glob patterns and comments.
    """
    patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    # Add common virtual environment patterns by default if not overly complex
    # Ensure these are relative to the path being checked.
    # For a robust solution, .gitignore rules can be complex (e.g. unignore with !)
    # This implementation is simplified.
    default_ignores = ["venv/", ".venv/", "__pycache__/", "*.pyc", ".git/"]
    for p in default_ignores:
        if p not in patterns:
            patterns.append(p)
    return patterns

def is_ignored(path, gitignore_patterns, root_path):
    """
    Checks if a given path matches any of the .gitignore patterns.
    path should be relative to the root_path where .gitignore is typically located.
    """
    # Ensure path is relative for matching
    relative_path = os.path.relpath(path, root_path)
    
    # Normalize path separators for matching, especially for directory patterns
    # A pattern like 'node_modules/' should match 'node_modules' directory
    normalized_path_parts = relative_path.split(os.sep)

    for pattern in gitignore_patterns:
        # Check against the full relative path
        if fnmatch.fnmatch(relative_path, pattern):
            return True
        # Check against each part of the path for directory patterns
        # e.g. pattern 'build/' should match 'project/build/file.txt'
        current_check_path = ""
        for part in normalized_path_parts:
            current_check_path = os.path.join(current_check_path, part)
            if fnmatch.fnmatch(current_check_path, pattern.rstrip('/')): # Match 'dir' or 'dir/'
                 return True
            if pattern.endswith('/') and fnmatch.fnmatch(current_check_path + '/', pattern): # Match 'dir/' explicitly
                 return True
        # Also check just the basename (e.g. *.log)
        if fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
            
    return False

def get_project_files(start_path=".", custom_gitignore_path=None):
    """
    Walks through the directory structure from start_path.
    Filters files and directories based on .gitignore rules.
    Returns a list of (path, type) tuples where type is 'dir' or 'file'.
    The paths returned are relative to the start_path.
    """
    project_root = os.path.abspath(start_path)
    gitignore_file_path = custom_gitignore_path if custom_gitignore_path else os.path.join(project_root, ".gitignore")
    
    ignore_patterns = parse_gitignore(gitignore_file_path)
    
    file_system_items = []

    for root, dirs, files in os.walk(project_root, topdown=True):
        # Filter directories
        # A copy of dirs[:] is used because modifying list during iteration is tricky
        original_dirs = list(dirs) # Keep original for full path construction
        dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d), ignore_patterns, project_root)]
        
        # Add filtered directories to items
        for d_name in dirs:
            full_path = os.path.join(root, d_name)
            relative_path = os.path.relpath(full_path, start_path)
            file_system_items.append((relative_path, "dir"))

        # Add filtered files to items
        for f_name in files:
            full_path = os.path.join(root, f_name)
            if not is_ignored(full_path, ignore_patterns, project_root):
                relative_path = os.path.relpath(full_path, start_path)
                file_system_items.append((relative_path, "file"))
                
    # Sort for consistent order: directories first, then files, then alphabetically
    file_system_items.sort(key=lambda x: (x[0].count(os.sep), x[1] == 'file', x[0]))
    
    return file_system_items

if __name__ == "__main__":
    print("Listing files in current directory (.), respecting .gitignore (if any):")
    
    # Create a dummy .gitignore for testing
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w") as f:
            f.write("*.log\n")
            f.write("temp_dir/\n")
            f.write("dist/\n")
            f.write("*.tmp\n")

    # Create some dummy files and dirs for testing
    os.makedirs("temp_dir/subdir", exist_ok=True)
    os.makedirs("dist", exist_ok=True)
    os.makedirs("src", exist_ok=True) # Assuming this test runs from project root
    open("main.py", "a").close()
    open("src/app.py", "a").close()
    open("test.log", "a").close()
    open("temp_dir/file.txt", "a").close()
    open("temp_dir/another.tmp", "a").close()
    open("dist/output.exe", "a").close()

    project_items = get_project_files(".")
    for item_path, item_type in project_items:
        print(f"[{item_type}] {item_path}")

    # Clean up dummy .gitignore and files
    # Note: This cleanup is basic. Be careful if you have important files with these names.
    # In a real test suite, use a temporary directory.
    # os.remove(".gitignore")
    # os.remove("test.log")
    # os.remove("temp_dir/file.txt")
    # os.remove("temp_dir/another.tmp")
    # os.rmdir("temp_dir/subdir")
    # os.rmdir("temp_dir")
    # os.remove("dist/output.exe")
    # os.rmdir("dist")
    # if os.path.exists("main.py"): os.remove("main.py") # if created by this test
    # if os.path.exists("src/app.py"): os.remove("src/app.py") # if created
    # if os.path.exists("src") and not os.listdir("src"): os.rmdir("src")
