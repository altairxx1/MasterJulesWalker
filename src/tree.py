import os
from .files import get_project_files # Assuming files.py is in the same directory

# Tree drawing characters
GLYPH_SPACE = "    "
GLYPH_BRANCH = "│   "
GLYPH_TEE = "├── "
GLYPH_LAST = "└── "

def generate_tree_display(file_items, selected_index=-1):
    """
    Generates a list of strings representing the directory tree.
    file_items should be a list of (path_str, type_str) tuples, sorted appropriately.
    type_str can be 'dir' or 'file'.
    selected_index can be used to highlight an item.
    Returns a list of strings, each being a line in the tree.
    """
    tree_lines = []
    
    # Create a lookup for directory contents to determine 'last' items
    # This is a bit complex with a flat list. A hierarchical structure would be easier.
    # For now, we'll infer based on path prefixes.
    
    # We need to know, for each path segment, whether it's the last among its siblings.
    # This simplified version will iterate and decide prefixes based on the next item.
    
    for i, (path_str, item_type) in enumerate(file_items):
        parts = path_str.split(os.sep)
        name = parts[-1]
        depth = len(parts) - 1
        
        prefix = ""
        
        # Determine prefix based on depth and whether it's the last item at its level.
        # This requires looking ahead or knowing sibling counts at each level.
        # This is a simplified approach:
        
        # Basic indentation
        for d in range(depth):
            # A more accurate prefix would check if the parent directory itself was the last
            # among its siblings. This simplified version just indents.
            # To do it properly, we'd need to know the structure of parent directories.
            prefix += GLYPH_SPACE # Simplified: use space. For lines, need more context.


        # Determine if this item is the last among its direct siblings
        # This is tricky with a flat sorted list. We check if the next item has a shallower depth
        # or a different parent prefix.
        is_last_sibling = True # Assume last unless proven otherwise
        if i + 1 < len(file_items):
            next_item_path_str, _ = file_items[i+1]
            next_item_parts = next_item_path_str.split(os.sep)
            # If next item has same depth and same parent path, then current is not last
            if len(next_item_parts) -1 == depth and os.sep.join(parts[:-1]) == os.sep.join(next_item_parts[:-1]):
                is_last_sibling = False
            # If next item is deeper but under the same parent, current is not last (if current is a dir)
            # This logic can get very complex. A proper tree data structure is better.

        if depth > 0: # Only add tee or last if not a root item
             # This simplified logic for is_last_sibling might not be perfect for all cases.
             # A truly robust tree display often builds a graph/tree structure first.
            if is_last_sibling:
                prefix += GLYPH_LAST
            else:
                prefix += GLYPH_TEE
        
        line = f"{prefix}{name}"
        if item_type == "dir":
            line += "/"
        
        if i == selected_index:
            line = f"> {line}" # Simple selection indicator
            
        tree_lines.append(line)
        
    return tree_lines

if __name__ == "__main__":
    print("Testing tree generation...")

    # Create dummy files/dirs for testing get_project_files from files.py
    # This assumes files.py is in the same directory or Python path is set up.
    # For robust testing, use mocks or a dedicated test file structure.
    
    # Example items (normally from get_project_files)
    # Ensure these are sorted as get_project_files would sort them
    # (depth, type, name)
    mock_items = [
        ("README.md", "file"),
        ("src", "dir"),
        ("src/config.py", "file"),
        ("src/files.py", "file"),
        ("src/main.py", "file"),
        ("src/tabs.py", "file"),
        ("src/tree.py", "file"),
        ("src/ui.py", "file"),
        ("tests", "dir"),
        ("tests/test_app.py", "file"),
        ("venv", "dir"), # This would typically be gitignored
    ]

    print("\nUsing mock items:")
    tree_output_mock = generate_tree_display(mock_items)
    for line in tree_output_mock:
        print(line)

    print("\nSimulating selection (item 2 - src/config.py):")
    tree_output_selected = generate_tree_display(mock_items, selected_index=2)
    for line in tree_output_selected:
        print(line)

    # Test with actual get_project_files if possible (might need to be in project root)
    # This part might fail if not run from the project root or if .gitignore is aggressive
    try:
        print("\nUsing get_project_files from current directory (if files.py is accessible):")
        # Create a dummy .gitignore for testing if it doesn't exist
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w") as f:
                f.write("venv/\n") # ignore venv for this test
                f.write("*.pyc\n")
                f.write("__pycache__/\n")
        
        # Ensure some files exist for `get_project_files`
        os.makedirs("src", exist_ok=True)
        if not os.path.exists("src/main.py"): open("src/main.py", "w").close()
        if not os.path.exists("README.md"): open("README.md", "w").close()

        actual_items = get_project_files(".") # Assumes files.py is in python path
        tree_output_actual = generate_tree_display(actual_items)
        if tree_output_actual:
            for line in tree_output_actual:
                print(line)
        else:
            print("get_project_files returned no items or an error occurred.")

    except ImportError:
        print("\nCould not import get_project_files. Skipping test with actual files.")
    except Exception as e:
        print(f"\nError during test with actual files: {e}")
