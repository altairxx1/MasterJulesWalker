import curses
import os
import time 
from .tabs import TabManager
from . import files
from . import tree
from . import viewer
from .chat import ChatManager # Added
from .config import load_config, save_setting # Ensure save_setting is imported

class TerminalUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        app_config = load_config() 

        self.tab_names = ["Main", "Files", "Settings"]
        self.tab_manager = TabManager(self.tab_names)
        
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE) # Highlight
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Dir
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK) # User chat prompt
        self.highlight_attr = curses.color_pair(1)
        self.dir_attr = curses.color_pair(2)
        self.prompt_attr = curses.color_pair(3)
        self.normal_attr = curses.A_NORMAL

        # Files tab state
        self.file_tab_mode = "tree"
        self.project_root = "."
        self.project_items = []
        self.tree_display_lines = []
        self.selected_tree_index = 0
        self.tree_top_line_index = 0
        self.active_file_viewer = None
        self._load_project_files()

        # Main (Chat) tab state
        self.chat_manager = ChatManager(config=app_config)
        self.chat_input_buffer = ""
        self.chat_scroll_top_index = 0 
        self.is_loading_llm_response = False
        # self.status_message = "" # This was for chat, now settings has its own

        # Settings Tab State
        self.settings_api_key_input_buffer = ""
        loaded_api_key = app_config.get("openrouter_api_key")
        self.current_api_key_display = "Loaded from config (not shown)" if loaded_api_key else "Not set"
        self.settings_status_message = ""
        self.settings_model_input_buffer = app_config.get("mjw_model", "") # Also allow editing model

    def _load_project_files(self, path="."):
        self.project_root = os.path.abspath(path)
        self.project_items = files.get_project_files(self.project_root)
        self._update_tree_display()
        self.selected_tree_index = 0
        self.tree_top_line_index = 0

    def _update_tree_display(self):
        self.tree_display_lines = tree.generate_tree_display(self.project_items, self.selected_tree_index)

    def _draw_title(self):
        title = "MasterJulesWalker"
        h, w = self.stdscr.getmaxyx()
        x = w // 2 - len(title) // 2
        y = 0 
        self.stdscr.addstr(y, x, title, curses.A_BOLD)

    def _draw_tabs(self):
        h, w = self.stdscr.getmaxyx()
        tab_y_position = 2
        tab_spacing = 4
        current_x = 1
        for i, tab_name in enumerate(self.tab_manager.get_all_tabs()):
            is_current_tab = (tab_name == self.tab_manager.get_current_tab())
            attr = self.highlight_attr if is_current_tab else self.normal_attr
            display_tab_name = f" {tab_name} "
            try:
                if current_x + len(display_tab_name) < w:
                    self.stdscr.addstr(tab_y_position, current_x, display_tab_name, attr)
                current_x += len(display_tab_name) + tab_spacing
            except curses.error: pass
    
    def _clear_content_area(self, content_y_start, h, w):
        for y_line in range(content_y_start, h -1): # Clear down to one line above bottom
            try:
                self.stdscr.addstr(y_line, 1, " " * (w - 2))
            except curses.error: pass

    def _draw_main_content(self):
        h, w = self.stdscr.getmaxyx()
        content_y_start = 4 # Line below tabs
        input_line_y = h - 2 # Second to last line for input buffer
        
        self._clear_content_area(content_y_start, h, w)

        current_active_tab = self.tab_manager.get_current_tab()

        if current_active_tab == "Main":
            chat_history_lines = self.chat_manager.get_formatted_history()
            chat_display_height = input_line_y - content_y_start
            
            if self.is_loading_llm_response:
                loading_msg = "MJW is thinking..."
                if chat_display_height > 0:
                     self.stdscr.addstr(input_line_y -1 , 2, loading_msg[:w-3], self.highlight_attr)
                     chat_display_height -=1
            
            num_history_lines = len(chat_history_lines)
            if num_history_lines <= chat_display_height: self.chat_scroll_top_index = 0
            elif self.chat_scroll_top_index > num_history_lines - chat_display_height:
                self.chat_scroll_top_index = num_history_lines - chat_display_height
            if self.chat_scroll_top_index < 0: self.chat_scroll_top_index = 0

            for i in range(chat_display_height):
                line_idx = self.chat_scroll_top_index + i
                if line_idx < num_history_lines:
                    self.stdscr.addstr(content_y_start + i, 2, chat_history_lines[line_idx][:w-3], self.normal_attr)
            
            prompt_indicator = "> "
            self.stdscr.addstr(input_line_y, 1, prompt_indicator, self.prompt_attr)
            self.stdscr.addstr(input_line_y, 1 + len(prompt_indicator), self.chat_input_buffer[:w - (2 + len(prompt_indicator))])

        elif current_active_tab == "Files":
            # This logic is complex and assumed correct from previous steps
            if self.file_tab_mode == "tree":
                if not self.tree_display_lines:
                    self.stdscr.addstr(content_y_start, 2, "No files found or error loading tree.")
                else:
                    max_lines_to_show = h - content_y_start - 1
                    if self.tree_top_line_index < 0: self.tree_top_line_index = 0
                    if self.tree_top_line_index >= len(self.tree_display_lines):
                        self.tree_top_line_index = max(0, len(self.tree_display_lines) - max_lines_to_show)
                    for i in range(max_lines_to_show):
                        current_tree_line_idx = self.tree_top_line_index + i
                        if current_tree_line_idx < len(self.tree_display_lines):
                            line_to_draw = self.tree_display_lines[current_tree_line_idx][:w-2]
                            attr = self.highlight_attr if current_tree_line_idx == self.selected_tree_index else self.normal_attr
                            self.stdscr.addstr(content_y_start + i, 1, line_to_draw, attr)
                        else: break
            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                max_lines_to_show = h - content_y_start - 2 
                view_lines = self.active_file_viewer.get_display_lines(max_lines_to_show)
                for i, line_content in enumerate(view_lines):
                    if i < max_lines_to_show:
                        self.stdscr.addstr(content_y_start + i, 1, line_content[:w-2])
                    else: break
                back_hint = "[b] Back to tree"
                self.stdscr.addstr(content_y_start + max_lines_to_show, 2, back_hint, self.highlight_attr)

        elif current_active_tab == "Settings":
            y_offset = content_y_start
            
            self.stdscr.addstr(y_offset, 2, f"Current API Key: {self.current_api_key_display}", self.normal_attr)
            y_offset += 2

            self.stdscr.addstr(y_offset, 2, "New OpenRouter API Key:", self.normal_attr)
            self.stdscr.addstr(y_offset + 1, 2, "> " + self.settings_api_key_input_buffer, self.prompt_attr)
            y_offset += 3

            self.stdscr.addstr(y_offset, 2, f"Model Name (current: {self.chat_manager.model_name}):", self.normal_attr)
            self.stdscr.addstr(y_offset + 1, 2, "> " + self.settings_model_input_buffer, self.prompt_attr)
            y_offset += 3

            self.stdscr.addstr(y_offset, 2, "Press Enter in a field to Save. Esc to clear field.", self.normal_attr)
            y_offset += 2
            
            if self.settings_status_message:
                self.stdscr.addstr(y_offset, 2, self.settings_status_message, self.highlight_attr)

        else: 
            placeholder_text = f"Content for {current_active_tab} tab (Not yet implemented)."
            self.stdscr.addstr(content_y_start, 1, placeholder_text[:w-2])

    def _handle_input(self):
        try:
            key = self.stdscr.getch()
        except curses.error: return True
        if key == -1: return True
        if key == ord('q') or key == 3: return False # Global Exit

        current_active_tab = self.tab_manager.get_current_tab()
        max_h, max_w = self.stdscr.getmaxyx()
        
        if current_active_tab == "Settings":
            if key == curses.KEY_ENTER or key == 10 or key == 13:
                saved_something = False
                api_key_to_save = self.settings_api_key_input_buffer.strip()
                if api_key_to_save: 
                    save_setting('openrouter_api_key', api_key_to_save)
                    self.current_api_key_display = "Saved (not shown)" 
                    saved_something = True
                elif self.settings_api_key_input_buffer == " ": 
                    save_setting('openrouter_api_key', None)
                    self.current_api_key_display = "Cleared"
                    api_key_to_save = None 
                    saved_something = True

                model_to_save = self.settings_model_input_buffer.strip()
                if model_to_save:
                    save_setting('mjw_model', model_to_save)
                    saved_something = True
                
                if saved_something:
                    new_config = load_config()
                    self.chat_manager.update_api_config(
                        new_api_key=new_config.get("openrouter_api_key"),
                        new_model_name=new_config.get("mjw_model")
                    )
                    self.settings_status_message = "Settings saved. Chat client updated."
                    self.settings_api_key_input_buffer = "" 
                    self.settings_model_input_buffer = new_config.get("mjw_model", "") 
                else:
                    self.settings_status_message = "No changes to save."
                return True

            elif key == curses.KEY_BACKSPACE or key == 127:
                # This needs to be context-aware if multiple input fields are truly active.
                # For now, assume editing API key or model based on some prior selection (not implemented)
                # Simplified: operate on API key buffer for now if no other logic.
                # This part of the provided diff is simplified and may need more robust field selection.
                # Let's assume for now it applies to settings_api_key_input_buffer primarily.
                self.settings_api_key_input_buffer = self.settings_api_key_input_buffer[:-1]
                self.settings_status_message = "" 
                return True
            elif key == curses.KEY_ESCAPE: 
                self.settings_api_key_input_buffer = ""
                self.settings_model_input_buffer = self.chat_manager.model_name 
                self.settings_status_message = "Input fields cleared."
                return True
            elif 32 <= key <= 126: 
                 # Simplified: append to API key buffer.
                self.settings_api_key_input_buffer += chr(key)
                self.settings_status_message = "" 
                return True
            elif self.tab_manager.handle_input(key): # Allow tab switching
                 return True

        elif current_active_tab == "Main":
            chat_display_height = (max_h - 2) - 4 
            num_history_lines = len(self.chat_manager.get_formatted_history())
            if self.is_loading_llm_response: # Only allow tab switch or exit if loading
                if self.tab_manager.handle_input(key): return True
                return True # Ignore other inputs

            if key == curses.KEY_UP: 
                if self.chat_scroll_top_index > 0: self.chat_scroll_top_index -= 1
                return True
            elif key == curses.KEY_DOWN:
                 if self.chat_scroll_top_index < num_history_lines - chat_display_height: self.chat_scroll_top_index += 1
                 return True
            elif key == curses.KEY_PPAGE:
                self.chat_scroll_top_index = max(0, self.chat_scroll_top_index - chat_display_height)
                return True
            elif key == curses.KEY_NPAGE:
                self.chat_scroll_top_index = min(num_history_lines - chat_display_height, self.chat_scroll_top_index + chat_display_height)
                if self.chat_scroll_top_index < 0 : self.chat_scroll_top_index =0
                return True
            elif key == curses.KEY_ENTER or key == 10 or key == 13: 
                if self.chat_input_buffer.strip():
                    self.is_loading_llm_response = True; self.stdscr.erase(); self._draw_title(); self._draw_tabs(); self._draw_main_content(); self.stdscr.refresh()
                    # Error/status is handled by chat_manager adding to its history or UI displaying it
                    self.chat_manager.send_message(self.chat_input_buffer.strip()) 
                    self.chat_input_buffer = ""; self.is_loading_llm_response = False
                    num_history_lines_after = len(self.chat_manager.get_formatted_history()) 
                    if num_history_lines_after > chat_display_height: self.chat_scroll_top_index = num_history_lines_after - chat_display_height
                    else: self.chat_scroll_top_index = 0
                return True
            elif key == curses.KEY_BACKSPACE or key == 127: self.chat_input_buffer = self.chat_input_buffer[:-1]; return True
            elif 32 <= key <= 126: self.chat_input_buffer += chr(key); return True
            elif self.tab_manager.handle_input(key): return True # Tab switching
        
        elif current_active_tab == "Files":
            content_area_height = max_h - 4 -1
            if self.file_tab_mode == "tree":
                if key == curses.KEY_UP: 
                    if self.selected_tree_index > 0: 
                        self.selected_tree_index -= 1
                        if self.selected_tree_index < self.tree_top_line_index: self.tree_top_line_index = self.selected_tree_index
                    self._update_tree_display(); return True
                elif key == curses.KEY_DOWN:
                    if self.selected_tree_index < len(self.project_items) - 1:
                        self.selected_tree_index += 1
                        if self.selected_tree_index >= self.tree_top_line_index + content_area_height: self.tree_top_line_index = self.selected_tree_index - content_area_height + 1
                    self._update_tree_display(); return True
                elif key == curses.KEY_ENTER or key == 10 or key == 13: 
                     if 0 <= self.selected_tree_index < len(self.project_items):
                        item_path_rel, item_type = self.project_items[self.selected_tree_index]
                        if item_type == "file": 
                            self.file_tab_mode = "viewer"
                            self.active_file_viewer = viewer.FileViewer(os.path.join(self.project_root, item_path_rel))
                     return True
                elif self.tab_manager.handle_input(key): return True # Tab switching

            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                if key == ord('b'): self.file_tab_mode = "tree"; self.active_file_viewer = None; return True
                if self.active_file_viewer.handle_input(key, content_area_height): return True
                elif self.tab_manager.handle_input(key): return True # Tab switching

        # Fallback to global tab switching if not handled by specific tab context
        if self.tab_manager.handle_input(key):
            if self.tab_manager.get_current_tab() == "Files" and not self.project_items:
                self._load_project_files()
            if self.tab_manager.get_current_tab() == "Settings":
                current_conf = load_config()
                self.current_api_key_display = "Loaded (not shown)" if current_conf.get("openrouter_api_key") else "Not set"
                self.settings_model_input_buffer = current_conf.get("mjw_model", "")
                self.settings_api_key_input_buffer = "" 
                self.settings_status_message = "" 
            return True
            
        return True

    def run_loop(self):
        # ... (existing run_loop, no changes needed here) ...
        running = True
        while running:
            self.stdscr.erase()
            self._draw_title()
            self._draw_tabs()
            self._draw_main_content()
            self.stdscr.refresh()
            running = self._handle_input()
            if not running: break
            # curses.napms(10) 

def main_ui_runner(stdscr_outer):
    ui = TerminalUI(stdscr_outer)
    ui.run_loop()

if __name__ == "__main__":
    print("Attempting to run TerminalUI with Chat and Files tab integration.")
    try:
        curses.wrapper(main_ui_runner)
        print("TerminalUI exited gracefully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Make sure your terminal supports curses and is large enough.")
        print("And OPENROUTER_API_KEY is set in env for chat functionality.")
