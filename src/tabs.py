import curses # For key constants like curses.KEY_LEFT, curses.KEY_RIGHT

class TabManager:
    def __init__(self, tab_names):
        if not tab_names:
            raise ValueError("Tab names cannot be empty.")
        self.tab_names = tab_names
        self.current_tab_index = 0

    def get_current_tab(self):
        return self.tab_names[self.current_tab_index]

    def get_all_tabs(self):
        return self.tab_names

    def next_tab(self):
        self.current_tab_index = (self.current_tab_index + 1) % len(self.tab_names)

    def previous_tab(self):
        self.current_tab_index = (self.current_tab_index - 1 + len(self.tab_names)) % len(self.tab_names)

    def handle_input(self, key):
        """
        Handles input for tab switching.
        Returns True if the input was handled (i.e., a tab switch occurred), False otherwise.
        """
        if key == curses.KEY_RIGHT:
            self.next_tab()
            return True
        elif key == curses.KEY_LEFT:
            self.previous_tab()
            return True
        return False

if __name__ == "__main__":
    # Example usage (requires a curses environment to fully test key handling)
    tabs = ["Main", "Files", "Settings"]
    tab_manager = TabManager(tabs)

    print(f"Initial tab: {tab_manager.get_current_tab()}")
    
    # Simulate pressing right arrow
    print("Simulating KEY_RIGHT...")
    tab_manager.handle_input(curses.KEY_RIGHT) # This would ideally be a real curses key
    print(f"After KEY_RIGHT: {tab_manager.get_current_tab()}")

    # Simulate pressing left arrow
    print("Simulating KEY_LEFT...")
    tab_manager.handle_input(curses.KEY_LEFT) # This would ideally be a real curses key
    print(f"After KEY_LEFT: {tab_manager.get_current_tab()}")
    
    # Simulate pressing left arrow again to wrap around
    print("Simulating KEY_LEFT again...")
    tab_manager.handle_input(curses.KEY_LEFT)
    print(f"After KEY_LEFT (wrap): {tab_manager.get_current_tab()}")

    print(f"All tabs: {tab_manager.get_all_tabs()}")
