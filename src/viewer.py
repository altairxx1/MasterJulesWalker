import curses # For key constants
import os # For the __main__ test block

class FileViewer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.lines = []
        self.top_line_num = 0  # The line number at the top of the view
        self.error_message = None
        self._load_file()

    def _load_file(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.lines = f.readlines()
            # Strip newline characters for cleaner display management
            self.lines = [line.rstrip('\n') for line in self.lines]
        except Exception as e:
            self.lines = []
            self.error_message = f"Error loading file: {str(e)}"

    def get_display_lines(self, num_display_lines):
        """
        Returns a portion of the file content to be displayed.
        num_display_lines: The number of lines the display area can show.
        """
        if self.error_message:
            return [self.error_message]
            
        if not self.lines:
            return ["(Empty File)"]

        # Ensure top_line_num is within valid bounds
        if self.top_line_num < 0:
            self.top_line_num = 0
        if self.top_line_num >= len(self.lines):
            # If top_line_num is too far, adjust to show the last page
            self.top_line_num = max(0, len(self.lines) - num_display_lines)

        end_line = min(self.top_line_num + num_display_lines, len(self.lines))
        
        display_lines = []
        for i in range(self.top_line_num, end_line):
            # Add line numbers for context, similar to a simple editor
            display_lines.append(f"{i+1:4d} {self.lines[i]}")
        
        return display_lines

    def scroll(self, direction, amount=1, page_amount=10):
        """
        Adjusts the top_line_num to scroll the view.
        direction: 'up', 'down', 'pageup', 'pagedown'
        amount: number of lines for line scroll
        page_amount: number of lines for page scroll
        """
        if not self.lines:
            return

        if direction == 'up':
            self.top_line_num = max(0, self.top_line_num - amount)
        elif direction == 'down':
            # Prevent scrolling too far down if content is less than a full page
            # Max scroll is len(self.lines) - num_display_lines (handled in get_display_lines)
             self.top_line_num = min(self.top_line_num + amount, len(self.lines) -1) # -1 so last line can be top
        elif direction == 'pageup':
            self.top_line_num = max(0, self.top_line_num - page_amount)
        elif direction == 'pagedown':
            self.top_line_num = min(self.top_line_num + page_amount, len(self.lines) -1)
        
        # Ensure top_line_num doesn't go negative if file is very short
        if self.top_line_num < 0: self.top_line_num = 0


    def handle_input(self, key, lines_in_view_area):
        """
        Handles input for scrolling.
        Returns True if the input was handled (scrolling occurred), False otherwise.
        lines_in_view_area: how many lines the UI can display, for page scrolling.
        """
        if key == curses.KEY_UP:
            self.scroll('up')
            return True
        elif key == curses.KEY_DOWN:
            self.scroll('down')
            return True
        elif key == curses.KEY_PPAGE: # Page Up
            self.scroll('pageup', page_amount=lines_in_view_area)
            return True
        elif key == curses.KEY_NPAGE: # Page Down
            self.scroll('pagedown', page_amount=lines_in_view_area)
            return True
        return False

if __name__ == "__main__":
    # This test requires a terminal that can interpret curses key constants
    # and manual input or a more sophisticated test harness.
    
    print("Testing FileViewer...")
    # Create a dummy file for testing
    dummy_filepath = "test_viewer_file.txt"
    with open(dummy_filepath, "w") as f:
        for i in range(100):
            f.write(f"This is line number {i+1}.\n")

    viewer = FileViewer(dummy_filepath)
    
    if viewer.error_message:
        print(viewer.error_message)
    else:
        print(f"File: {viewer.filepath}")
        print(f"Total lines: {len(viewer.lines)}")

        num_display_lines = 10 # Simulate a display area of 10 lines
        
        print("\nInitial view (first 10 lines):")
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)

        print("\nSimulating scroll down by 5 lines:")
        viewer.scroll("down", amount=5)
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)

        print("\nSimulating page down (10 lines):")
        viewer.scroll("pagedown", page_amount=num_display_lines)
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)

        print("\nSimulating scroll up by 3 lines:")
        viewer.scroll("up", amount=3)
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)
            
        # Test edge case: scrolling near end
        print("\nScrolling near end to show last few lines:")
        viewer.top_line_num = len(viewer.lines) - 5 # Go near end
        for line_content in viewer.get_display_lines(num_display_lines): # num_display_lines is how many viewer can show
            print(line_content)
        
        # Test scrolling past end (should be capped by get_display_lines)
        print("\nScrolling past end (should show last page):")
        viewer.scroll("down", amount=20) # Try to scroll way past
        for line_content in viewer.get_display_lines(num_display_lines):
            print(line_content)


    # Clean up dummy file
    if os.path.exists(dummy_filepath):
        os.remove(dummy_filepath)
