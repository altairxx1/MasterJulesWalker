import curses
import os
import time 
from .tabs import TabManager
from . import files
from . import tree
from . import viewer
from .context import ContextManager
from .analyzer import CodeAnalyzer
from .commands import CommandRunner # Added
from .chat import ChatManager
from .config import load_config, save_setting

class TerminalUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        app_config = load_config() 

        self.tab_names = ["Main", "Files", "Commands", "Settings"] # Added "Commands"
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
        self._load_project_files() # Sets self.project_root

        # Context Manager
        self.context_manager = ContextManager(project_root=self.project_root)
        self.context_status_message = "" # For messages related to context operations

        # Code Analyzer
        self.code_analyzer = CodeAnalyzer(project_root=self.project_root)
        self.active_analysis_report = None 
        self.analysis_display_lines = []   
        self.analysis_view_top_line = 0    

        # Command Runner
        self.command_runner = CommandRunner(project_root=self.project_root)
        self.available_commands = self.command_runner.list_available_commands() # Load once
        self.selected_command_index = 0
        self.command_output_lines = []
        self.command_output_top_line = 0
        self.command_status_message = "" 
        self.commands_view_mode = "list" # "list" or "output"

        # Main (Chat) tab state
        # Pass a reference to self (TerminalUI instance) for ChatManager to access context
        self.chat_manager = ChatManager(config=app_config, ui_reference=self)
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
            # Files Tab Drawing
            if self.file_tab_mode == "tree":
                # Layout: File tree, then context summary, then context status
                context_summary_list = self.context_manager.get_context_summary()
                num_summary_lines = len(context_summary_list)
                
                # Calculate heights: status (1 line), summary title (1 if items >0), N summary lines
                context_area_reserved_height = 1 # For status message / general info line
                if num_summary_lines > 0:
                    context_area_reserved_height += 1 # For "--- Context Files ---" title
                context_area_reserved_height += num_summary_lines

                # tree_view_height is the space left for the actual file tree
                tree_view_height = (h - content_y_start - 1) - context_area_reserved_height
                tree_view_height = max(3, tree_view_height) # Ensure tree view has some min height (e.g. 3 lines)

                # Draw File Tree
                if not self.tree_display_lines:
                    if content_y_start < h -1: # Ensure there's space to draw this
                        self.stdscr.addstr(content_y_start, 2, "No files found or error loading tree."[:w-3])
                else:
                    # Auto-adjust tree_top_line_index to keep selection visible
                    if self.selected_tree_index >= self.tree_top_line_index + tree_view_height:
                         self.tree_top_line_index = self.selected_tree_index - tree_view_height + 1
                    if self.selected_tree_index < self.tree_top_line_index:
                         self.tree_top_line_index = self.selected_tree_index
                    
                    # Clamp tree_top_line_index based on total items and available view height
                    self.tree_top_line_index = max(0, self.tree_top_line_index)
                    if len(self.tree_display_lines) > tree_view_height:
                        self.tree_top_line_index = min(self.tree_top_line_index, len(self.tree_display_lines) - tree_view_height)
                    else: # Not enough items to scroll, so top is 0
                        self.tree_top_line_index = 0

                    for i in range(tree_view_height):
                        current_tree_line_idx = self.tree_top_line_index + i
                        if current_tree_line_idx < len(self.tree_display_lines):
                            line_content = self.tree_display_lines[current_tree_line_idx]
                            # TODO: Indicate if file is in context e.g. "[CTX] filename"
                            # This requires generate_tree_display to know about context_manager.context_files
                            # For now, check here directly (less efficient, but ok for a few context files)
                            item_path_rel, _ = self.project_items[current_tree_line_idx] # Assuming tree_display_lines maps 1:1 to project_items
                            abs_item_path = os.path.join(self.project_root, item_path_rel)
                            prefix = "[CTX] " if abs_item_path in self.context_manager.context_files else ""
                            line_to_draw = (prefix + line_content)[:w-2] # Apply prefix
                            
                            attr = self.highlight_attr if current_tree_line_idx == self.selected_tree_index else self.normal_attr
                            if content_y_start + i < h -1:
                                self.stdscr.addstr(content_y_start + i, 1, line_to_draw, attr)
                        else: break # No more lines in tree_display_lines
                
                # Draw Context Summary Area (below tree)
                context_draw_y_start = content_y_start + tree_view_height
                
                if num_summary_lines > 0:
                    if context_draw_y_start < h -1:
                        self.stdscr.addstr(context_draw_y_start, 1, "--- Context ('c' to add/remove selected) ---"[:w-2], self.highlight_attr)
                    context_draw_y_start += 1
                    for i, summary_line in enumerate(context_summary_list):
                        if context_draw_y_start + i < h -1: 
                             self.stdscr.addstr(context_draw_y_start + i, 1, summary_line[:w-2])
                
                # Draw Context Status Message / General Info (at the bottom of the reserved context area)
                info_line_y = content_y_start + tree_view_height + (1 if num_summary_lines > 0 else 0) + num_summary_lines
                if info_line_y < h -1 : # Ensure it's on screen
                    current_info_line_content = ""
                    if self.context_status_message: # Prioritize context status message
                        current_info_line_content = self.context_status_message
                        # self.context_status_message = "" # Clear after showing once
                    else: 
                        ctx_size_kb = self.context_manager.current_context_size_bytes // 1024
                        max_ctx_size_kb = ContextManager.MAX_TOTAL_CONTEXT_SIZE_BYTES // 1024
                        num_ctx_files = len(self.context_manager.context_files)
                        max_num_files = ContextManager.MAX_CONTEXT_FILES
                        current_info_line_content = f"Ctx Files: {num_ctx_files}/{max_num_files}, Size: {ctx_size_kb}KB/{max_ctx_size_kb}KB. ('a' to analyze)"
                    
                    self.stdscr.addstr(info_line_y, 1, " " * (w - 2)) # Clear previous
                    self.stdscr.addstr(info_line_y, 1, current_info_line_content[:w-2], self.highlight_attr if self.context_status_message else self.normal_attr)
                    if self.context_status_message == current_info_line_content: # Ensure we only clear if it was the message displayed
                        self.context_status_message = "" # Clear after display


            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                # Viewer mode takes full height available in content_y_start, less 1 for back_hint
                viewer_display_height = h - content_y_start - 2 
                view_lines = self.active_file_viewer.get_display_lines(viewer_display_height)
                for i, line_content in enumerate(view_lines):
                    # Ensure we do not write outside allocated space for viewer content
                    if i < viewer_display_height and (content_y_start + i < h -1 ) :
                        self.stdscr.addstr(content_y_start + i, 1, line_content[:w-2])
                    else: break
                back_hint = "[b] Back to tree"
                # Ensure back_hint is drawn on its dedicated line
                if content_y_start + viewer_display_height < h -1:
                     self.stdscr.addstr(content_y_start + viewer_display_height, 2, back_hint, self.highlight_attr)
            
            elif self.file_tab_mode == "analyzer":
                analyzer_view_height = h - content_y_start - 2 # Reserve 1 line for back hint
                if not self.analysis_display_lines:
                    if content_y_start < h -1:
                         self.stdscr.addstr(content_y_start, 1, "No analysis report to display."[:w-2])
                else:
                    # Ensure analysis_view_top_line is valid
                    if self.analysis_view_top_line < 0: self.analysis_view_top_line = 0
                    if len(self.analysis_display_lines) > analyzer_view_height:
                        self.analysis_view_top_line = min(self.analysis_view_top_line, len(self.analysis_display_lines) - analyzer_view_height)
                    else:
                        self.analysis_view_top_line = 0 # Not enough lines to scroll

                    for i in range(analyzer_view_height):
                        current_display_line_idx = self.analysis_view_top_line + i
                        if current_display_line_idx < len(self.analysis_display_lines):
                            line_to_draw = self.analysis_display_lines[current_display_line_idx]
                            if content_y_start + i < h - 1:
                                self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else:
                            break # No more lines to draw
                
                analysis_hint = "[b] Back to Tree" # Future: "[c] Add to context"
                if content_y_start + analyzer_view_height < h -1:
                    self.stdscr.addstr(content_y_start + analyzer_view_height, 2, analysis_hint[:w-2], self.highlight_attr)

        elif current_active_tab == "Commands":
            if self.commands_view_mode == "list":
                list_view_height = h - content_y_start - 2 # Reserve 1 for status, 1 for hint
                self.stdscr.addstr(content_y_start, 1, "Available Commands ('Enter' to run):"[:w-2], self.highlight_attr)
                
                # Ensure selected_command_index is valid
                if self.selected_command_index < 0: self.selected_command_index = 0
                if self.selected_command_index >= len(self.available_commands):
                    self.selected_command_index = max(0, len(self.available_commands) -1)

                # Simple scrolling for command list if needed (not implemented for now, assume fits)
                # For now, just display what fits. Max ~20 commands for typical screen.
                for i, (name, desc) in enumerate(self.available_commands):
                    if content_y_start + 1 + i < h - 2:
                        display_text = f"{name}: {desc}"
                        attr = self.highlight_attr if i == self.selected_command_index else self.normal_attr
                        self.stdscr.addstr(content_y_start + 1 + i, 2, display_text[:w-3], attr)
                
                if self.command_status_message and content_y_start + 1 + len(self.available_commands) < h -2 :
                     self.stdscr.addstr(content_y_start + 1 + len(self.available_commands), 1, self.command_status_message[:w-2], self.normal_attr)
                     self.command_status_message = "" # Clear after display

            elif self.commands_view_mode == "output":
                output_view_height = h - content_y_start - 2 # Reserve 1 line for back hint
                if not self.command_output_lines:
                    if content_y_start < h -1:
                        self.stdscr.addstr(content_y_start, 1, "No output to display."[:w-2])
                else:
                    if self.command_output_top_line < 0: self.command_output_top_line = 0
                    if len(self.command_output_lines) > output_view_height:
                        self.command_output_top_line = min(self.command_output_top_line, len(self.command_output_lines) - output_view_height)
                    else:
                        self.command_output_top_line = 0
                    
                    for i in range(output_view_height):
                        current_display_line_idx = self.command_output_top_line + i
                        if current_display_line_idx < len(self.command_output_lines):
                            line_to_draw = self.command_output_lines[current_display_line_idx]
                            if content_y_start + i < h -1 :
                                 self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else: break
                
                output_hint = "[b] Back to Command List"
                if content_y_start + output_view_height < h -1:
                    self.stdscr.addstr(content_y_start + output_view_height, 2, output_hint[:w-2], self.highlight_attr)


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
                self.settings_status_message = "" # Clear after display

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
                        # _draw_main_content will handle adjusting tree_top_line_index if selection goes out of view
                    self._update_tree_display(); return True
                elif key == ord('c'): # Add/remove selected file from/to context
                    if 0 <= self.selected_tree_index < len(self.project_items):
                        item_path_rel, item_type = self.project_items[self.selected_tree_index]
                        if item_type == "file":
                            # Use a local var for status to avoid race if it's cleared quickly by draw loop
                            current_op_status = ""
                            # Check if already in context by its absolute path
                            abs_item_path = os.path.join(self.project_root, item_path_rel)
                            if abs_item_path in self.context_manager.context_files:
                                self.context_manager.remove_file(item_path_rel)
                                current_op_status = self.context_manager.get_latest_error() or f"Removed {os.path.basename(item_path_rel)}"
                            else:
                                self.context_manager.add_file(item_path_rel)
                                current_op_status = self.context_manager.get_latest_error() or f"Added {os.path.basename(item_path_rel)}"
                            self.context_status_message = current_op_status # Set for display
                        else:
                            self.context_status_message = "Cannot add directories to context."
                        self._update_tree_display() 
                    return True
                elif key == ord('a'): # Analyze selected file
                    if 0 <= self.selected_tree_index < len(self.project_items):
                        item_path_rel, item_type = self.project_items[self.selected_tree_index]
                        if item_type == "file" and item_path_rel.endswith(".py"):
                            self.active_analysis_report = self.code_analyzer.analyze_file(item_path_rel)
                            if self.active_analysis_report and "error" not in self.active_analysis_report:
                                formatted_analysis = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
                                self.analysis_display_lines = formatted_analysis.split('\n')
                                self.file_tab_mode = "analyzer"
                                self.analysis_view_top_line = 0
                                self.context_status_message = f"Analyzed: {os.path.basename(item_path_rel)}"
                            else:
                                error_msg = self.active_analysis_report.get("error", "Unknown analysis error.")
                                self.context_status_message = f"Analyze error: {error_msg}"
                        else:
                            self.context_status_message = "Select a Python file (.py) to analyze."
                    return True

                elif key == curses.KEY_ENTER or key == 10 or key == 13: 
                     if 0 <= self.selected_tree_index < len(self.project_items):
                        item_path_rel, item_type = self.project_items[self.selected_tree_index]
                        if item_type == "file":
                            if self.active_file_viewer: # Close previous viewer if any
                                self.active_file_viewer.close()
                            self.file_tab_mode = "viewer"
                            self.active_file_viewer = viewer.FileViewer(os.path.join(self.project_root, item_path_rel))
                     return True
                # elif self.tab_manager.handle_input(key): return True # Tab switching - Handled by global below

            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                if key == ord('b'):
                    self.active_file_viewer.close()
                    self.active_file_viewer = None
                    self.file_tab_mode = "tree"
                    self.context_status_message = "Closed viewer." # Give some feedback
                    return True
                if self.active_file_viewer.handle_input(key, content_area_height): return True
                # elif self.tab_manager.handle_input(key): return True # Tab switching - Handled by global below
            
            elif self.file_tab_mode == "analyzer":
                if key == ord('b'):
                    self.file_tab_mode = "tree"
                    self.analysis_display_lines = [] # Clear analysis
                    self.active_analysis_report = None
                    self.context_status_message = "Closed analyzer."
                    return True
                # Scrolling for analysis view
                analyzer_content_height = max_h - 4 - 2 # h - content_start_y - hint_lines
                if key == curses.KEY_UP:
                    if self.analysis_view_top_line > 0: self.analysis_view_top_line -=1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.analysis_view_top_line < len(self.analysis_display_lines) - analyzer_content_height:
                         self.analysis_view_top_line +=1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.analysis_view_top_line = max(0, self.analysis_view_top_line - analyzer_content_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.analysis_view_top_line = min(
                        len(self.analysis_display_lines) - analyzer_content_height if len(self.analysis_display_lines) > analyzer_content_height else 0,
                        self.analysis_view_top_line + analyzer_content_height
                    )
                    if self.analysis_view_top_line < 0: self.analysis_view_top_line = 0
                    return True
                # elif key == ord('c'): # TODO: Add analysis to context manager?

        elif current_active_tab == "Commands":
            if self.commands_view_mode == "list":
                if key == curses.KEY_UP:
                    if self.selected_command_index > 0:
                        self.selected_command_index -= 1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.selected_command_index < len(self.available_commands) - 1:
                        self.selected_command_index += 1
                    return True
                elif key == curses.KEY_ENTER or key == 10 or key == 13:
                    if 0 <= self.selected_command_index < len(self.available_commands):
                        command_name, _ = self.available_commands[self.selected_command_index]
                        # Clear previous status before running new command
                        self.command_status_message = f"Running {command_name}..." 
                        self.command_output_lines = [self.command_status_message] # Show running message immediately
                        self.commands_view_mode = "output"
                        self.stdscr.refresh() # Force refresh to show "Running..."
                        
                        success, output, error_str = self.command_runner.run_command(command_name)
                        
                        if success:
                            self.command_output_lines = output.split('\n') if output else ["Command ran successfully with no output."]
                            self.command_status_message = f"'{command_name}' finished."
                        else:
                            self.command_output_lines = (error_str.split('\n') if error_str 
                                                         else [f"Command '{command_name}' failed with no specific error output."])
                            self.command_status_message = f"Error running '{command_name}'."
                        self.command_output_top_line = 0
                    return True

            elif self.commands_view_mode == "output":
                if key == ord('b'):
                    self.commands_view_mode = "list"
                    self.command_output_lines = []
                    self.command_status_message = "Returned to command list." # Provide feedback
                    return True
                # Scrolling for command output
                cmd_output_content_height = max_h - 4 - 2 # h - content_start_y - hint_lines
                if key == curses.KEY_UP:
                    if self.command_output_top_line > 0: self.command_output_top_line -=1
                    return True
                elif key == curses.KEY_DOWN:
                     if self.command_output_top_line < len(self.command_output_lines) - cmd_output_content_height:
                         self.command_output_top_line +=1
                     return True
                elif key == curses.KEY_PPAGE:
                    self.command_output_top_line = max(0, self.command_output_top_line - cmd_output_content_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.command_output_top_line = min(
                        len(self.command_output_lines) - cmd_output_content_height if len(self.command_output_lines) > cmd_output_content_height else 0,
                        self.command_output_top_line + cmd_output_content_height
                    )
                    if self.command_output_top_line < 0 : self.command_output_top_line = 0
                    return True

        # Global tab switching (and other global keys if any added later)
        # Note: tab_manager.handle_input(key) changes the current tab internally.
        previous_tab = current_active_tab # Tab before potential switch
        switched_tab = self.tab_manager.handle_input(key) # This attempts to switch tab

        if switched_tab:
            newly_selected_tab = self.tab_manager.get_current_tab()
            # If we were in file viewer mode and switched away from Files tab, or are no longer in viewer mode
            if self.active_file_viewer and (newly_selected_tab != "Files" or self.file_tab_mode != "viewer"):
                self.active_file_viewer.close()
                self.active_file_viewer = None
                # If we switched to Files tab but were previously in viewer mode (e.g. via a direct shortcut not yet impl),
                # ensure we are back in tree mode. This is defensive.
                if newly_selected_tab == "Files" and self.file_tab_mode == "viewer":
                    self.file_tab_mode = "tree"


            if newly_selected_tab == "Files" and not self.project_items:
                self._load_project_files()
            if newly_selected_tab == "Settings":
                current_conf = load_config()
                self.current_api_key_display = "Loaded (not shown)" if current_conf.get("openrouter_api_key") else "Not set"
                self.settings_model_input_buffer = current_conf.get("mjw_model", "")
                self.settings_api_key_input_buffer = "" 
                self.settings_status_message = ""
            return True # Input was handled by tab switching
            
        return True # Default: input was handled (e.g. by a specific tab, or ignored)

    def run_loop(self):
        running = True
        try:
            while running:
                self.stdscr.erase()
                self._draw_title()
                self._draw_tabs()
                self._draw_main_content() # This will now also draw context info
                self.stdscr.refresh()
                running = self._handle_input()
                if not running: break
                # curses.napms(10) 
        finally:
            # Cleanup, important for releasing resources like file handles
            if self.active_file_viewer:
                self.active_file_viewer.close() # Already here from previous step
                self.active_file_viewer = None
            # Potentially close context_manager if it held resources, but it doesn't currently (no open files)

    # Method to be called by ChatManager to get current context
    def get_current_context_for_chat(self):
        if self.context_manager and self.context_manager.context_files:
            return self.context_manager.get_context_string()
        return None

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
