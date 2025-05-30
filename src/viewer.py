import curses # For key constants
import os # For the __main__ test block
import itertools

class FileViewer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.file_handle = None
        self.total_lines = 0
        self.line_cache = {} # Stores line_number: line_content
        self.top_line_num = 0  # The line number (0-indexed) at the top of the view
        self.error_message = None
        self._load_file()

    def _load_file(self):
        try:
            self.file_handle = open(self.filepath, 'r', encoding='utf-8')
            # Count lines
            line_count = 0
            for i, _ in enumerate(self.file_handle):
                line_count = i + 1
            self.total_lines = line_count
            # Reset the file pointer for later reading
            if self.total_lines > 0: # seek(0) is problematic on empty files for some OS/Python versions
                self.file_handle.seek(0)
        except Exception as e:
            self.error_message = f"Error loading file: {str(e)}"
            if self.file_handle:
                self.file_handle.close()
            self.file_handle = None
            self.total_lines = 0

    def get_display_lines(self, num_display_lines):
        """
        Returns a portion of the file content to be displayed.
        num_display_lines: The number of lines the display area can show.
        """
        if self.error_message:
            return [self.error_message]
        
        if not self.file_handle:
            return [self.error_message or "Error: File not loaded."] # Use existing error or a generic one

        if self.total_lines == 0:
            return ["(Empty File)"]

        # Adjust self.top_line_num to ensure it's valid before trying to read.
        self.top_line_num = max(0, self.top_line_num)
        # Ensure top_line_num doesn't go beyond where it can start to display num_display_lines
        # or the last line if total_lines < num_display_lines
        self.top_line_num = min(self.top_line_num, self.total_lines - 1) # Cannot be more than last line index
        if self.total_lines > num_display_lines:
             self.top_line_num = min(self.top_line_num, self.total_lines - num_display_lines)
        else: # If total lines is less than display area, top must be 0
            self.top_line_num = 0


        display_lines = []
        
        # Determine the actual number of lines to retrieve based on current top_line_num and total_lines
        start_line_abs_idx = self.top_line_num
        end_line_abs_idx = min(self.top_line_num + num_display_lines, self.total_lines)
        num_lines_to_render = end_line_abs_idx - start_line_abs_idx

        lines_retrieved_this_pass = {} # Store lines retrieved in this call (abs_idx: content)

        # Pre-fill from cache for lines in the desired range
        for i in range(num_lines_to_render):
            line_num_abs = start_line_abs_idx + i
            if line_num_abs in self.line_cache:
                lines_retrieved_this_pass[line_num_abs] = self.line_cache[line_num_abs]

        # Determine which lines are missing from cache and need to be read from file
        missing_line_indices = []
        for i in range(num_lines_to_render):
            line_num_abs = start_line_abs_idx + i
            if line_num_abs not in lines_retrieved_this_pass:
                missing_line_indices.append(line_num_abs)
        
        if missing_line_indices:
            # Find min and max line numbers to read from file in this pass
            min_read_from_file = min(missing_line_indices)
            max_read_from_file = max(missing_line_indices)

            self.file_handle.seek(0) # Reset iterator for islice
            file_iterator = itertools.islice(self.file_handle, min_read_from_file, max_read_from_file + 1)
            
            for current_offset, line_content_from_file in enumerate(file_iterator):
                actual_line_num_in_file = min_read_from_file + current_offset
                if actual_line_num_in_file in missing_line_indices: # If this line was one we needed
                    processed_line = line_content_from_file.rstrip('\n')
                    self.line_cache[actual_line_num_in_file] = processed_line
                    lines_retrieved_this_pass[actual_line_num_in_file] = processed_line
            
            # Cache eviction logic
            if len(self.line_cache) > 200: # Example limit
                keys_to_delete = [
                    k for k in self.line_cache 
                    if not (start_line_abs_idx - 50 < k < end_line_abs_idx + 50) # Keep lines around current view
                ]
                # More aggressive: if still too many, remove some from the ones selected to delete
                if len(self.line_cache) - len(keys_to_delete) > 150 : # Keep at least 150
                     num_to_evict_additionally = (len(self.line_cache) - len(keys_to_delete)) - 150
                     # This is a simple way, could be smarter (e.g. LRU on the keys_to_delete)
                     keys_to_delete.extend(list(self.line_cache.keys())[:num_to_evict_additionally])


                for k_del in set(keys_to_delete): # Use set to avoid issues if a key is listed twice
                    if k_del in self.line_cache:
                         del self.line_cache[k_del]

        # Construct display_lines using lines_retrieved_this_pass
        for i in range(num_lines_to_render):
            current_line_num_abs = start_line_abs_idx + i
            # Get from populated dict, provide empty string if somehow still missing (should not happen)
            line_content = lines_retrieved_this_pass.get(current_line_num_abs, "") 
            display_lines.append(f"{current_line_num_abs + 1:4d} {line_content}")
        
        return display_lines

    def scroll(self, direction, amount=1, page_amount=10):
        """
        Adjusts the top_line_num to scroll the view.
        direction: 'up', 'down', 'pageup', 'pagedown'
        amount: number of lines for line scroll
        page_amount: number of lines for page scroll (relative to current view height)
        """
        if self.total_lines == 0:
            return

        if direction == 'up':
            self.top_line_num = max(0, self.top_line_num - amount)
        elif direction == 'down':
            # Allow scrolling down such that the last line can become the top_line_num
            self.top_line_num = min(self.top_line_num + amount, self.total_lines - 1)
        elif direction == 'pageup':
            self.top_line_num = max(0, self.top_line_num - page_amount)
        elif direction == 'pagedown':
            self.top_line_num = min(self.top_line_num + page_amount, self.total_lines - 1)
        
        # Ensure top_line_num doesn't go negative
        if self.top_line_num < 0: self.top_line_num = 0
    
    def close(self):
        """Closes the file handle and clears the cache."""
        if self.file_handle is not None:
            try:
                self.file_handle.close()
            except Exception:
                pass # Ignore errors on close
            self.file_handle = None
        self.line_cache.clear()

    def handle_input(self, key, lines_in_view_area):
        """
        Handles input for scrolling.
        Returns True if the input was handled (scrolling occurred), False otherwise.
        lines_in_view_area: how many lines the UI can display, for page scrolling.
        """
        if key == curses.KEY_UP:
            self.scroll('up', amount=1)
            return True
        elif key == curses.KEY_DOWN:
            self.scroll('down', amount=1)
            return True
        elif key == curses.KEY_PPAGE: # Page Up
            self.scroll('pageup', page_amount=lines_in_view_area)
            return True
        elif key == curses.KEY_NPAGE: # Page Down
            self.scroll('pagedown', page_amount=lines_in_view_area)
            return True
        return False

if __name__ == "__main__":
    print("Testing FileViewer with on-demand loading...")
    dummy_filepath = "test_viewer_large_file.txt"
    num_test_lines = 300
    with open(dummy_filepath, "w") as f:
        for i in range(num_test_lines):
            f.write(f"This is line number {i+1} in a large test file.\n")

    viewer = FileViewer(dummy_filepath)
    
    if viewer.error_message:
        print(f"Error during init: {viewer.error_message}")
    else:
        print(f"File: {viewer.filepath}")
        print(f"Total lines counted: {viewer.total_lines}")

        num_display_lines = 15 # Simulate a display area

        print(f"\nInitial view (first {num_display_lines} lines):")
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size: {len(viewer.line_cache)}")


        print(f"\nSimulating scroll down by {num_test_lines // 4} lines:")
        viewer.scroll("down", amount=(num_test_lines // 4))
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size: {len(viewer.line_cache)}")


        print(f"\nSimulating page down by {num_display_lines} lines:")
        viewer.scroll("pagedown", page_amount=num_display_lines)
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size: {len(viewer.line_cache)}")


        print("\nSimulating scroll to near end:")
        viewer.top_line_num = viewer.total_lines - (num_display_lines // 2) # Go near end
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size: {len(viewer.line_cache)}")

        print("\nSimulating scroll to very end (last page):")
        viewer.top_line_num = viewer.total_lines -1 # last line at top
        # viewer.scroll("pagedown", amount=viewer.total_lines) # Scroll way down
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size: {len(viewer.line_cache)}")
        
        print("\nSimulating scroll back to top:")
        viewer.top_line_num = 0
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
        print(f"Cache size after returning to top (should show some cache hits): {len(viewer.line_cache)}")

        # Test cache eviction by scrolling far away
        print("\nScrolling far away to test cache eviction:")
        viewer.top_line_num = num_test_lines - num_display_lines # Go to end
        for _ in viewer.get_display_lines(num_display_lines): pass # Populate cache at end
        viewer.top_line_num = 0 # Go to beginning
        for _ in viewer.get_display_lines(num_display_lines): pass # Populate cache at beginning
        print(f"Cache size after accessing disjoint regions: {len(viewer.line_cache)}")


    viewer.close() # Important to close the file handle

    # Clean up dummy file
    if os.path.exists(dummy_filepath):
        os.remove(dummy_filepath)
    
    print("\nTesting with an empty file:")
    empty_filepath = "test_empty_viewer_file.txt"
    open(empty_filepath, "w").close() # Create empty file
    empty_viewer = FileViewer(empty_filepath)
    if empty_viewer.error_message:
        print(f"Error (empty file): {empty_viewer.error_message}")
    else:
        print(f"Total lines (empty): {empty_viewer.total_lines}")
        for line_content in empty_viewer.get_display_lines(10):
            print(line_content)
    empty_viewer.close()
    if os.path.exists(empty_filepath): os.remove(empty_filepath)

    print("\nTesting with a non-existent file:")
    non_existent_filepath = "test_does_not_exist_viewer.txt"
    ne_viewer = FileViewer(non_existent_filepath)
    if ne_viewer.error_message:
        print(f"Caught error as expected: {ne_viewer.error_message}")
    else:
        print("Error: Non-existent file test failed to report an error.")
    ne_viewer.close() # Should do nothing, but good practice
