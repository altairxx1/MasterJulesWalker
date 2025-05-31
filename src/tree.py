import os

# Tree drawing characters
GLYPH_SPACE = "    "
GLYPH_BRANCH = "│   "
GLYPH_TEE = "├── "
GLYPH_LAST = "└── "

class FileTree:
    def __init__(self, project_items: list[tuple[str, str]]):
        """
        Initializes the FileTree.

        Args:
            project_items (list[tuple[str, str]]): A list of (path_str, type_str) tuples,
                                                 sorted as provided by files.get_project_files.
                                                 paths are relative to project_root.
        """
        self.project_items_master: list[tuple[str, str]] = list(project_items) # Keep original list
        self.filter_term: str = ""
        self.filtered_project_items: list[tuple[str, str]] = list(project_items) # Initially, no filter

    def set_filter_term(self, term: str):
        """
        Sets the filter term and regenerates the filtered list of items.
        """
        new_filter_term = term.lower()
        if self.filter_term == new_filter_term:
            return # No change, no need to re-filter

        self.filter_term = new_filter_term
        self._apply_filter()

    def _apply_filter(self):
        """
        Applies the current filter_term to project_items_master
        and updates filtered_project_items.
        """
        if not self.filter_term:
            self.filtered_project_items = list(self.project_items_master)
            return

        items_to_include_paths = set()
        directly_matched_paths = set()

        # First pass: find direct matches
        for path_str, item_type in self.project_items_master:
            basename = os.path.basename(path_str)
            if self.filter_term in basename.lower():
                items_to_include_paths.add(path_str)
                directly_matched_paths.add(path_str)

        # Second pass: add parents of directly matched items
        # Create a temporary set to add parents to avoid modifying items_to_include_paths while iterating indirectly
        parents_to_add = set()
        for path_str in directly_matched_paths: # Iterate only over items that directly matched
            parts = path_str.split(os.sep)
            current_path = ""
            for part in parts[:-1]: # Iterate through parent directory parts
                if current_path:
                    current_path = os.path.join(current_path, part)
                else:
                    current_path = part
                parents_to_add.add(current_path)
        
        items_to_include_paths.update(parents_to_add)

        # Third pass: (Optional but good for usability) if a directory is included,
        # and the filter term is empty, all its direct children should be included
        # from the original list. This is implicitly handled if parents are added
        # and the final list is built by filtering project_items_master.
        # However, if a directory itself matches (e.g. filter "src" for "src/" dir),
        # we might want to show its children even if they don't match.
        # For now, the logic is: if a dir 'd' matches, 'd' is in items_to_include_paths.
        # If a file 'd/f.txt' matches, 'd' and 'd/f.txt' are in items_to_include_paths.

        new_filtered_items = []
        for path_str, item_type in self.project_items_master:
            if path_str in items_to_include_paths:
                new_filtered_items.append((path_str, item_type))
        
        # The sorting should be preserved from project_items_master if we iterate it.
        # If items_to_include_paths was used to fetch items from a hash map, sorting would be needed.
        self.filtered_project_items = new_filtered_items


    def get_display_lines(self, selected_item_path: str | None = None) -> list[tuple[str, str]]:
        """
        Generates a list of (display_line_str, item_path_str) tuples for the filtered tree.
        The selected item path is used to mark an item with '> '.
        """
        tree_lines_with_paths = []
        
        for i, (path_str, item_type) in enumerate(self.filtered_project_items):
            parts = path_str.split(os.sep)
            name = parts[-1]
            depth = len(parts) - 1
            
            prefix = ""

            # Determine indent prefix based on depth
            # This part needs context of parent structure within the *filtered* view
            # For simplicity in indent, we use GLYPH_SPACE for all parent levels.
            # For tee/last glyphs, we need to analyze filtered_project_items structure.

            temp_path = ""
            for d_idx in range(depth):
                # Check if the current part of the path (at depth d_idx) is the last among its
                # siblings *at that level in the filtered tree*.
                parent_path_of_current_segment = os.sep.join(parts[:d_idx+1])
                is_last_among_siblings_at_this_depth = True
                for j in range(len(self.filtered_project_items)):
                    # Check items that are deeper or at same level but later in list
                    if j > i and self.filtered_project_items[j][0].startswith(parent_path_of_current_segment + os.sep):
                        # This sibling check is complex. A simpler indent:
                        # If the *parent* of path_str (i.e., os.sep.join(parts[:d_idx+1]))
                        # has any subsequent siblings in filtered_project_items at *its* level,
                        # then use GLYPH_BRANCH for its children. This is still tricky.

                        # Simplified: If there's any item below the current `path_str` that shares
                        # the same prefix up to `d_idx+1` (i.e., `os.sep.join(parts[:d_idx+2])`),
                        # it means the current segment `parts[d_idx]` is not the last one to have children
                        # branching from it at this level of indentation.
                        # This is still complex. Let's use a simpler visual indent for now.
                        pass # Fallback to GLYPH_SPACE below if this logic isn't perfect.


            # Determine Tee or Last Glyph for the item itself
            is_last_sibling_for_item = True
            if depth > 0: # Root items don't get these glyphs
                parent_of_item = os.sep.join(parts[:-1])
                for j in range(i + 1, len(self.filtered_project_items)):
                    other_item_path, _ = self.filtered_project_items[j]
                    other_item_parent = os.sep.join(other_item_path.split(os.sep)[:-1])
                    # If another item shares the same parent and is at the same depth
                    if other_item_parent == parent_of_item and len(other_item_path.split(os.sep)) -1 == depth:
                        is_last_sibling_for_item = False
                        break
                    # If another item is shallower or has a different parent, current item might be last for its parent
                    if len(other_item_path.split(os.sep)) -1 < depth or \
                       (parent_of_item and not other_item_path.startswith(parent_of_item)):
                        break # We've passed items under the same parent

            # Build prefix string (very simplified for now, better logic needed for lines)
            # This simplified prefixing will not draw nice connecting lines for deep trees.
            # It's a known issue with flat lists vs hierarchical structures for tree drawing.
            current_prefix_parts = []
            for d in range(depth):
                # This logic is extremely hard with a flat list and filtering.
                # A proper tree structure would make this trivial.
                # We'll use a placeholder for complex line drawing.
                # For now, always use GLYPH_SPACE for indentation.
                # The TEE/LAST applies only to the item itself relative to its direct parent.
                current_prefix_parts.append(GLYPH_SPACE)

            prefix = "".join(current_prefix_parts)

            if depth > 0:
                if is_last_sibling_for_item:
                    prefix += GLYPH_LAST
                else:
                    prefix += GLYPH_TEE

            line = f"{prefix}{name}"
            if item_type == "dir":
                line += "/"

            # Mark selected item
            # Note: selected_item_path should be the full relative path of the item.
            if path_str == selected_item_path:
                line = f"> {line}"

            tree_lines_with_paths.append((line, path_str))

        return tree_lines_with_paths

    def get_item_by_index(self, index: int) -> tuple[str, str] | None:
        """Returns the (path, type) of the item at the given index in the filtered list."""
        if 0 <= index < len(self.filtered_project_items):
            return self.filtered_project_items[index]
        return None

    def get_filtered_items_count(self) -> int:
        return len(self.filtered_project_items)


if __name__ == "__main__":
    print("Testing FileTree...")

    # Mock project_items similar to what files.get_project_files would produce
    mock_master_items = [
        ("README.md", "file"),
        ("src", "dir"),
        ("src/app.py", "file"),
        ("src/config.py", "file"),
        ("src/utils", "dir"),
        ("src/utils/helper.py", "file"),
        ("src/utils/network.py", "file"),
        ("tests", "dir"),
        ("tests/test_app.py", "file"),
        ("tests/test_config.py", "file"),
        ("requirements.txt", "file"),
        ("data", "dir"),
        ("data/logs", "dir"),
        ("data/logs/latest.log", "file")
    ]
    mock_master_items.sort(key=lambda x: (x[0].count(os.sep), x[1] == 'file', x[0]))


    file_tree = FileTree(mock_master_items)

    print("\n--- Initial Tree (no filter) ---")
    lines_no_filter = file_tree.get_display_lines(selected_item_path="src/config.py")
    for line, path in lines_no_filter:
        print(f"{line}  (path: {path})")

    print("\n--- Filter: 'app' ---")
    file_tree.set_filter_term("app")
    lines_filter_app = file_tree.get_display_lines()
    for line, path in lines_filter_app:
        print(f"{line}  (path: {path})")
    # Expected: README.md (if app in name), src, src/app.py, tests, tests/test_app.py

    print("\n--- Filter: '.py' ---")
    file_tree.set_filter_term(".py")
    lines_filter_py = file_tree.get_display_lines(selected_item_path="src/utils/helper.py")
    for line, path in lines_filter_py:
        print(f"{line}  (path: {path})")

    print("\n--- Filter: 'utils' (matches dir and files in it) ---")
    file_tree.set_filter_term("utils")
    lines_filter_utils = file_tree.get_display_lines()
    for line, path in lines_filter_utils:
        print(f"{line}  (path: {path})")

    print("\n--- Filter: 'log' (matches dir and file) ---")
    file_tree.set_filter_term("log")
    lines_filter_log = file_tree.get_display_lines()
    for line, path in lines_filter_log:
        print(f"{line}  (path: {path})")

    print("\n--- Filter: 'nonexistent' (no matches) ---")
    file_tree.set_filter_term("nonexistent")
    lines_no_match = file_tree.get_display_lines()
    if not lines_no_match:
        print("Correctly returned no lines for no match.")
    for line, path in lines_no_match: # Should be empty
        print(f"{line}  (path: {path})")

    print("\n--- Clear Filter ---")
    file_tree.set_filter_term("")
    lines_cleared = file_tree.get_display_lines(selected_item_path="README.md")
    # Should be same as initial tree
    # print(f"Comparing cleared ({len(lines_cleared)}) with initial ({len(lines_no_filter)}). First few:")
    # for i in range(min(5, len(lines_cleared))):
    # print(f"  Cleared: {lines_cleared[i][0]}, Initial: {lines_no_filter[i][0]}")
    assert len(lines_cleared) == len(lines_no_filter), "Cleared filter should restore all items."
    for line, path in lines_cleared[:5]: # Print a few
        print(f"{line}  (path: {path})")
        
    print("\n--- Test get_item_by_index (with filter 'app') ---")
    file_tree.set_filter_term("app") # src, src/app.py, tests, tests/test_app.py
    # Expected filtered items (example, depends on exact sorting and parent logic):
    # Assuming:
    # src (dir)
    # src/app.py (file)
    # tests (dir)
    # tests/test_app.py (file)
    # README.md (file) - if "app" is in "README.md"

    # Let's print the filtered items to know the indices
    # print("Filtered items for 'app':")
    # for idx, (p, t) in enumerate(file_tree.filtered_project_items):
    # print(f"  {idx}: {p} ({t})")

    # Example: if "src/app.py" is at index 1 in filtered list
    # item = file_tree.get_item_by_index(1)
    # if item: print(f"Item at index 1 (filter 'app'): {item}")
    # else: print("No item at index 1 (filter 'app') or list too short.")

    # This test is more for ensuring the method runs. Exact indices depend on implementation details.
    an_item = file_tree.get_item_by_index(0)
    if an_item : print(f"Item at index 0 (filter 'app'): {an_item}")

    print(f"Filtered items count (filter 'app'): {file_tree.get_filtered_items_count()}")

```
