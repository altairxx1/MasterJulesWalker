import difflib

def generate_diff(original_text: str, new_text: str, fromfile: str = "original", tofile: str = "new") -> list[str]:
    """
    Generates a unified diff between two strings of text.

    Args:
        original_text (str): The original text content.
        new_text (str): The new text content.
        fromfile (str): Optional name for the original file in the diff header.
        tofile (str): Optional name for the new file in the diff header.

    Returns:
        list[str]: A list of strings, where each string is a line of the
                   unified diff output. Returns an empty list if texts are identical.
    """
    if original_text == new_text:
        return []

    original_lines = original_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm="" # Keepends in splitlines already handles newlines
    )
    return list(diff)

if __name__ == '__main__':
    # Example Usage
    original_content = """line1
line2
line3 common
line4
line5
"""

    new_content_addition = """line1
line2
line2_added
line3 common
line4
line5
"""

    new_content_deletion = """line1
line3 common
line4
line5
"""

    new_content_modification = """line1
line2_modified
line3 common
line4
line5
"""

    new_content_multiline_change = """line1
line2_modified_again
line2_another_new_line
line3 common
line4_also_changed
line5
"""

    print("--- Diff: Addition ---")
    diff_add = generate_diff(original_content, new_content_addition, fromfile="file.txt", tofile="file_new.txt")
    for line in diff_add:
        print(line, end="")

    print("\n--- Diff: Deletion ---")
    diff_del = generate_diff(original_content, new_content_deletion, fromfile="a/file.txt", tofile="b/file.txt")
    for line in diff_del:
        print(line, end="")

    print("\n--- Diff: Modification ---")
    diff_mod = generate_diff(original_content, new_content_modification) # Use default filenames
    for line in diff_mod:
        print(line, end="")

    print("\n--- Diff: Multi-line Change ---")
    diff_multi = generate_diff(original_content, new_content_multiline_change, fromfile="old_version.py", tofile="new_version.py")
    for line in diff_multi:
        print(line, end="")

    print("\n--- Diff: Identical Content ---")
    diff_identical = generate_diff(original_content, original_content)
    if not diff_identical:
        print("No differences found (correct).")
    else:
        for line in diff_identical:
            print(line, end="")

    print("\n--- Diff: Empty Original, Content Added ---")
    diff_empty_orig = generate_diff("", new_content_addition)
    for line in diff_empty_orig:
        print(line, end="")

    print("\n--- Diff: Content Deleted, Empty New ---")
    diff_empty_new = generate_diff(original_content, "")
    for line in diff_empty_new:
        print(line, end="")

    print("\n--- Diff: Both Empty ---")
    diff_both_empty = generate_diff("", "")
    if not diff_both_empty:
        print("No differences found (correct).")
    else:
        for line in diff_both_empty:
            print(line, end="")

    # Edge case: text without trailing newlines
    original_no_newline = "line1\nline2"
    new_no_newline = "line1\nline2_changed"
    print("\n--- Diff: No Trailing Newlines ---")
    diff_no_trail = generate_diff(original_no_newline, new_no_newline)
    for line in diff_no_trail:
        print(line, end="") # lineterm="" in unified_diff handles this

    original_with_newline = "line1\nline2\n"
    new_with_newline_changed = "line1\nline2_changed\n"
    print("\n--- Diff: With Trailing Newlines (no change in newline status) ---")
    diff_with_trail = generate_diff(original_with_newline, new_with_newline_changed)
    for line in diff_with_trail:
        print(line, end="")

    original_nl = "a\nb\n"
    new_nl_removed = "a\nb" # Newline removed from last line
    print("\n--- Diff: Trailing Newline Removed ---")
    # difflib standard behavior will show this as a change on the last line and a \ No newline at end of file marker
    diff_nl_removed = generate_diff(original_nl, new_nl_removed)
    for line in diff_nl_removed:
        print(line, end="")

    original_no_nl = "a\nb"
    new_nl_added = "a\nb\n" # Newline added to last line
    print("\n--- Diff: Trailing Newline Added ---")
    diff_nl_added = generate_diff(original_no_nl, new_nl_added)
    for line in diff_nl_added:
        print(line, end="")

    # Test with lineterm (already using "" in function)
    # The key is that splitlines(keepends=True) + lineterm="" is a good combo.
    # If lineterm was not set, unified_diff would add its own newlines to lines it processes,
    # which would be duplicative if original lines already had them.
    print("\n--- Diff: Example with different line endings (mixed content, but input to func is str) ---")
    original_mixed = "line1\r\nline2\nline3"
    new_mixed = "line1\r\nline2_changed\nline3\n" # \n added to line3
    diff_mixed = generate_diff(original_mixed, new_mixed)
    for line in diff_mixed:
        print(line, end="") # end="" because diff lines already have newlines if they were in original/new


    # Conceptual LLM Interaction:
    # 1. User: "Refactor the `foo` function in `src/my_module.py` to be more efficient."
    # 2. LLM: "Okay, here's the refactored `foo` function for `src/my_module.py`:
    #    ```python
    #    def foo(n):
    #        # ... new efficient code ...
    #        return result
    #    ```"
    # 3. System Backend:
    #    a. `llm_code_block = extract_code_from_llm_response(llm_response)`
    #    b. `current_file_content = read_file_content('src/my_module.py')`
    #    c. The challenge: The LLM provided a *function*. The system needs to decide
    #       whether to replace the whole file, or try to find and replace just that function.
    #       For this subtask, we assume a simpler model: LLM provides full new file content,
    #       or the change is applied by replacing the entire file.
    #       So, if LLM provided *full* new content for `src/my_module.py`:
    #       `llm_full_new_content = llm_response_containing_full_file_code`
    #       `diff_output = generate_diff(current_file_content, llm_full_new_content, fromfile='src/my_module.py (original)', tofile='src/my_module.py (proposed)')`
    #    d. `display_diff_to_user(diff_output)`
    #    e. If user accepts: `write_file_content('src/my_module.py', llm_full_new_content)` (This part is for later)

    #    If the LLM provides only a partial change (e.g., just a function) and the system
    #    is not yet smart enough to surgically replace it, it might:
    #    - Ask the user to manually apply it.
    #    - Show a diff of the function against the existing function (if it can find it).
    #    - For now, `generate_diff` is a general tool. If used for partial changes,
    #      `original_text` would be the existing function's text and `new_text` the LLM's version.
    #      Example:
    #      `existing_func_code = extract_function_from_file(current_file_content, "foo")`
    #      `llm_func_code = llm_code_block`
    #      `func_diff = generate_diff(existing_func_code, llm_func_code, "foo (original)", "foo (proposed)")`
    #      This still requires robust extraction logic.

    # The current `generate_diff` is suitable for showing differences between any two text blocks,
    # whether they are full files or subsections. The "application" is what's simplified for now
    # (i.e., assumed to be full file overwrite based on diff of full contents).
    pass
