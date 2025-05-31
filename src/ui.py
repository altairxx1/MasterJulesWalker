import curses
import os
import time 
from .tabs import TabManager
from . import files
from . import tree
from . import viewer
from .context import ContextManager
from .analyzer import CodeAnalyzer
from .commands import CommandRunner
from .chat import ChatManager
from .config import load_config, save_setting
from .snippets import SnippetManager # Added for Snippets Tab

class TerminalUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        app_config = load_config() 

        self.tab_names = ["Main", "Files", "Commands", "Snippets", "Settings"] # Added "Snippets"
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
        self.selected_analysis_item_index = 0
        self.analysis_selectable_items = [] # Stores (type, name, original_idx, display_start_line)
        self.is_generating_tests = False
        self.generated_test_code_lines = []
        self.test_viewer_top_line = 0

        # Command Runner
        self.command_runner = CommandRunner(project_root=self.project_root)
        self.available_commands = self.command_runner.list_available_commands() # Load once
        self.selected_command_index = 0
        self.command_output_lines = []
        self.command_output_top_line = 0
        self.command_status_message = "" 
        self.commands_view_mode = "list" # "list" or "output"
        self.suggested_command_names = []
        self.is_fetching_suggestions = False

        # Snippet Manager & Tab State
        self.snippet_manager = SnippetManager() # Uses "snippets.json" by default
        self.snippet_list = []
        self.selected_snippet_index = 0
        self.snippet_view_top_line = 0
        self.snippet_status_message = ""
        self.snippet_tab_mode = "list"  # "list", "view_content", "edit_form"
        self.current_snippet_id_being_edited = None # For edit mode
        self.active_snippet_content_lines = []
        self.snippet_content_scroll_top = 0
        self.snippet_form_data = {} # For new/edited snippets
        self.snippet_form_active_field = "name" # Default active field
        self.snippet_form_input_buffer = ""   # For single-line field input
        # self.snippet_form_content_buffer = [] # Simplified: content uses snippet_form_input_buffer
        self.snippet_form_content_cursor_y = 0 # Relative to content buffer display (less relevant for single string)
        self.delete_confirm_pending_id = None # For two-step delete confirmation

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

    def _get_context_signals(self):
        signals = {
            "current_tab": self.tab_manager.get_current_tab(),
            "context_files": self.context_manager.get_context_summary(), # Already a list of strings
            "available_commands": self.available_commands # List of (name, description) tuples
        }

        # Recent chat history (e.g., last 3-5 messages)
        chat_history = self.chat_manager.get_formatted_history()
        signals["recent_chat_history"] = chat_history[-5:] # Get last 5, or fewer if less than 5 exist

        # Active analysis summary (truncated if necessary)
        analysis_summary = "None"
        if self.active_analysis_report and "error" not in self.active_analysis_report:
            # Assuming format_analysis_for_llm returns a potentially long string
            raw_summary = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
            max_len = 500 # Max length for analysis summary in context signals
            if len(raw_summary) > max_len:
                analysis_summary = raw_summary[:max_len-3] + "..."
            else:
                analysis_summary = raw_summary
        elif self.active_analysis_report and "error" in self.active_analysis_report:
            analysis_summary = f"Error in analysis: {self.active_analysis_report['error']}"

        signals["active_analysis"] = analysis_summary

        return signals

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

                # Populate selectable items if not already done or if report changed (though it's usually set once on mode entry)
                # This logic might be better placed where self.analysis_display_lines is generated,
                # but for now, let's ensure it's populated before drawing.
                if self.active_analysis_report and not self.analysis_selectable_items: # Only populate if empty
                    current_line_index = 0
                    temp_selectable_items = []

                    # Helper to find the start line of an item
                    def find_item_line_in_display(item_prefix, item_name, display_lines):
                        for idx, line in enumerate(display_lines):
                            if line.strip().startswith(item_prefix + " " + item_name):
                                return idx
                        return -1 # Should not happen if formatting is consistent

                    if 'classes' in self.active_analysis_report:
                        for i, class_info in enumerate(self.active_analysis_report['classes']):
                            class_name = class_info['name']
                            line_idx = find_item_line_in_display("Class:", class_name, self.analysis_display_lines)
                            if line_idx != -1:
                                temp_selectable_items.append({'type': 'class', 'name': class_name, 'report_idx': i, 'display_start_line': line_idx})

                    if 'functions' in self.active_analysis_report:
                        for i, func_info in enumerate(self.active_analysis_report['functions']):
                            func_name = func_info['name']
                            # Functions might be inside classes in the report, but format_analysis_for_llm lists them sequentially
                            line_idx = find_item_line_in_display("Function:", func_name, self.analysis_display_lines)
                            if line_idx != -1:
                                temp_selectable_items.append({'type': 'function', 'name': func_name, 'report_idx': i, 'display_start_line': line_idx})

                    # Sort by display_start_line to ensure correct selection highlighting later
                    temp_selectable_items.sort(key=lambda x: x['display_start_line'])
                    self.analysis_selectable_items = temp_selectable_items

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

                    # Determine selected item's line range for highlighting
                    selected_item_display_start = -1
                    selected_item_display_end = -1

                    if self.analysis_selectable_items and 0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                        selected_item = self.analysis_selectable_items[self.selected_analysis_item_index]
                        selected_item_display_start = selected_item['display_start_line']

                        # Find end line: start of next item or end of all display lines
                        if self.selected_analysis_item_index + 1 < len(self.analysis_selectable_items):
                            next_item = self.analysis_selectable_items[self.selected_analysis_item_index + 1]
                            selected_item_display_end = next_item['display_start_line']
                        else:
                            selected_item_display_end = len(self.analysis_display_lines)

                    for i in range(analyzer_view_height):
                        current_display_line_idx = self.analysis_view_top_line + i
                        if current_display_line_idx < len(self.analysis_display_lines):
                            line_to_draw = self.analysis_display_lines[current_display_line_idx]
                            attr_to_use = self.normal_attr
                            if selected_item_display_start != -1 and \
                               selected_item_display_start <= current_display_line_idx < selected_item_display_end:
                                attr_to_use = self.highlight_attr

                            if content_y_start + i < h - 1:
                                self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2], attr_to_use)
                        else:
                            break # No more lines to draw
                
                analysis_hint_text = "[b] Back to Tree, [t] Gen Tests"
                # Display loading message for test generation if active
                if self.is_generating_tests: # This will be very brief due to synchronous call
                    loading_msg = "Generating tests, please wait..."
                    # Simple way to overlay: draw it near the center of the content area
                    msg_y = content_y_start + analyzer_view_height // 2
                    msg_x = max(1, (w - len(loading_msg)) // 2)
                    if msg_y < h -1 :
                         self.stdscr.addstr(msg_y, msg_x, loading_msg, self.highlight_attr)

                if content_y_start + analyzer_view_height < h -1:
                    self.stdscr.addstr(content_y_start + analyzer_view_height, 2, analysis_hint_text[:w-2], self.highlight_attr)

            elif self.file_tab_mode == "test_viewer":
                test_viewer_height = h - content_y_start - 2 # Reserve 1 line for back hint
                if not self.generated_test_code_lines:
                    if content_y_start < h -1:
                        self.stdscr.addstr(content_y_start, 1, "No test code to display."[:w-2])
                else:
                    # Ensure test_viewer_top_line is valid
                    if self.test_viewer_top_line < 0: self.test_viewer_top_line = 0
                    if len(self.generated_test_code_lines) > test_viewer_height:
                        self.test_viewer_top_line = min(self.test_viewer_top_line, len(self.generated_test_code_lines) - test_viewer_height)
                    else:
                        self.test_viewer_top_line = 0

                    for i in range(test_viewer_height):
                        current_display_line_idx = self.test_viewer_top_line + i
                        if current_display_line_idx < len(self.generated_test_code_lines):
                            line_to_draw = self.generated_test_code_lines[current_display_line_idx]
                            if content_y_start + i < h - 1:
                                self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else:
                            break

                test_viewer_hint = "[b] Back to Analyzer"
                if content_y_start + test_viewer_height < h -1:
                    self.stdscr.addstr(content_y_start + test_viewer_height, 2, test_viewer_hint[:w-2], self.highlight_attr)


        elif current_active_tab == "Commands":
            if self.commands_view_mode == "list":
                list_view_height = h - content_y_start - 2 # Reserve 1 for status, 1 for hint (like F5 refresh)

                header_text = "Commands (Suggestions [*], F5 to refresh):"
                self.stdscr.addstr(content_y_start, 1, header_text[:w-2], self.highlight_attr)
                
                if self.is_fetching_suggestions:
                    loading_msg = "Fetching command suggestions..."
                    msg_y = content_y_start + 1
                    if msg_y < h - 2: # Ensure it's within drawable area
                        self.stdscr.addstr(msg_y, 2, loading_msg[:w-3])
                else:
                    # Ensure selected_command_index is valid
                    if self.selected_command_index < 0: self.selected_command_index = 0
                    if self.selected_command_index >= len(self.available_commands):
                        self.selected_command_index = max(0, len(self.available_commands) -1)

                    # Display commands
                    # For now, simple scrolling not implemented for command list, assuming it fits.
                    # This loop needs to respect list_view_height - 1 (for header)
                    display_y = content_y_start + 1
                    for i, (name, desc) in enumerate(self.available_commands):
                        if display_y >= content_y_start + list_view_height -1: # -1 for status line too
                            break

                        prefix = "[*] " if name in self.suggested_command_names else "    " # 4 spaces for alignment
                        display_text = f"{prefix}{name}: {desc}"

                        attr = self.highlight_attr if i == self.selected_command_index else self.normal_attr
                        self.stdscr.addstr(display_y, 2, display_text[:w-3], attr)
                        display_y += 1
                
                # Draw status message at the bottom of the list view area
                status_line_y = content_y_start + list_view_height -1
                if self.command_status_message and status_line_y < h -1:
                     self.stdscr.addstr(status_line_y, 1, " " * (w-2)) # Clear line
                     self.stdscr.addstr(status_line_y, 1, self.command_status_message[:w-2], self.normal_attr)
                     # Decide if status_message should be cleared:
                     # If it's "Fetched X suggestions", maybe keep it until next action.
                     # If it's "Fetching...", it will be overwritten or cleared by next draw.
                     # For now, let's not auto-clear it here. It will be cleared by _handle_input or next status.


            elif self.commands_view_mode == "output":
                output_view_height = h - content_y_start - 2 # Reserve 1 line for back hint
                if not self.command_output_lines:
                    if content_y_start < h -1: # Check available space
                        self.stdscr.addstr(content_y_start, 1, "No output to display."[:w-2])
                else:
                    if self.command_output_top_line < 0: self.command_output_top_line = 0
                    if len(self.command_output_lines) > output_view_height: # Check if scrollable
                        self.command_output_top_line = min(self.command_output_top_line, len(self.command_output_lines) - output_view_height)
                    else:
                        self.command_output_top_line = 0 # Not enough lines to scroll
                    
                    for i in range(output_view_height):
                        current_display_line_idx = self.command_output_top_line + i
                        if current_display_line_idx < len(self.command_output_lines):
                            line_to_draw = self.command_output_lines[current_display_line_idx]
                            if content_y_start + i < h -1 : # Check available space per line
                                 self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else: break # No more lines
                
                output_hint = "[b] Back to Command List"
                if content_y_start + output_view_height < h -1: # Check available space for hint
                    self.stdscr.addstr(content_y_start + output_view_height, 2, output_hint[:w-2], self.highlight_attr)

        elif current_active_tab == "Snippets":
            snippets_view_height = h - content_y_start - 2 # Reserve 1 for status/hint

            snippets_content_height = h - content_y_start - 1 # Reserve 1 line for status/hint at the very bottom

            if self.snippet_tab_mode == "list":
                self.stdscr.addstr(content_y_start, 1, "Snippets ([Enter] View, [a] Add, [d] Del):"[:w-2], self.highlight_attr)
                list_display_area_height = snippets_content_height - 2 # 1 for header, 1 for status

                if not self.snippet_list:
                    if content_y_start + 1 < h - 2:
                        self.stdscr.addstr(content_y_start + 1, 2, "No snippets found."[:w-3])
                else:
                    # Ensure selected_snippet_index is valid
                if self.selected_snippet_index < 0: self.selected_snippet_index = 0
                if self.selected_snippet_index >= len(self.snippet_list):
                    self.selected_snippet_index = max(0, len(self.snippet_list) -1)

                # Auto-adjust snippet_view_top_line to keep selection visible

                    if self.selected_snippet_index >= self.snippet_view_top_line + list_display_area_height:
                        self.snippet_view_top_line = self.selected_snippet_index - list_display_area_height + 1
                if self.selected_snippet_index < self.snippet_view_top_line:
                    self.snippet_view_top_line = self.selected_snippet_index

                    # Clamp snippet_view_top_line
                    self.snippet_view_top_line = max(0, self.snippet_view_top_line)
                    if len(self.snippet_list) > list_display_area_height: # Only clamp if there are enough items to scroll
                        self.snippet_view_top_line = min(self.snippet_view_top_line, len(self.snippet_list) - list_display_area_height)
                    else:
                        self.snippet_view_top_line = 0

                    display_y = content_y_start + 1
                    for i in range(list_display_area_height):
                        current_list_item_idx = self.snippet_view_top_line + i
                        if current_list_item_idx < len(self.snippet_list):
                            snippet = self.snippet_list[current_list_item_idx]
                            display_text = f"{snippet.get('name', 'Unnamed Snippet')} ({snippet.get('language', 'N/A')})"
                            attr = self.highlight_attr if current_list_item_idx == self.selected_snippet_index else self.normal_attr
                            if display_y < content_y_start + 1 + list_display_area_height :
                                 self.stdscr.addstr(display_y, 2, display_text[:w-3], attr)
                            display_y += 1
                        else:
                            break

            elif self.snippet_tab_mode == "view_content":
                self.stdscr.addstr(content_y_start, 1, "Snippet Content ([b] Back to List):"[:w-2], self.highlight_attr)
                content_display_height = snippets_content_height - 2 # 1 for header, 1 for status

                if not self.active_snippet_content_lines:
                     if content_y_start + 1 < h -2:
                        self.stdscr.addstr(content_y_start + 1, 2, "No content to display."[:w-3])
                else:
                    if self.snippet_content_scroll_top < 0: self.snippet_content_scroll_top = 0
                    if len(self.active_snippet_content_lines) > content_display_height:
                        self.snippet_content_scroll_top = min(self.snippet_content_scroll_top, len(self.active_snippet_content_lines) - content_display_height)
                    else:
                        self.snippet_content_scroll_top = 0

                    display_y = content_y_start + 1
                    for i in range(content_display_height):
                        line_idx = self.snippet_content_scroll_top + i
                        if line_idx < len(self.active_snippet_content_lines):
                            self.stdscr.addstr(display_y + i, 2, self.active_snippet_content_lines[line_idx][:w-3])
                        else:
                            break

            elif self.snippet_tab_mode == "edit_form": # Renamed from "add_form"
                form_y = content_y_start
                form_title = "Edit Snippet" if self.current_snippet_id_being_edited else "Add New Snippet"
                self.stdscr.addstr(form_y, 1, f"{form_title} ([Tab] Next, [Esc] Cancel):"[:w-2], self.highlight_attr)
                form_y += 1

                fields = ["name", "language", "category", "tags", "content", "save", "cancel"] # Keep order

                def draw_field(label, value, y, is_active):
                    attr = self.highlight_attr if is_active else self.normal_attr
                    self.stdscr.addstr(y, 2, f"{label}: "[:w-3], self.normal_attr)
                    # For active field, show input buffer, else show stored data
                    display_value = self.snippet_form_input_buffer if is_active else value
                    self.stdscr.addstr(y, 2 + len(label) + 2, display_value[:w - (4 + len(label) + 2)], attr)

                for field_name in fields:
                    if form_y >= content_y_start + snippets_content_height -1 : break # Stop if no space for status

                    is_active_field = (self.snippet_form_active_field == field_name)

                    if field_name not in ["content", "save", "cancel"]:
                        draw_field(field_name.capitalize(), self.snippet_form_data.get(field_name, ""), form_y, is_active_field)
                        form_y += 1
                    elif field_name == "content":
                        # Simplified content display (shows snippet_form_input_buffer when content is active)
                        self.stdscr.addstr(form_y, 2, "Content:"[:w-3], self.normal_attr)
                        content_attr = self.highlight_attr if is_active_field else self.normal_attr

                        # If active, show buffer. Else, show current form_data for content.
                        content_value_to_display = self.snippet_form_input_buffer if is_active_field else self.snippet_form_data.get("content", "")

                        # Display first few lines of content_value_to_display or placeholder
                        content_lines_to_show = content_value_to_display.split('\n')[:3] # Show max 3 lines in form
                        for i, line in enumerate(content_lines_to_show):
                            if form_y + 1 + i >= content_y_start + snippets_content_height - 2: break # Check bounds
                            self.stdscr.addstr(form_y + 1 + i, 4, line[:w-5], content_attr) # x=4 for indent
                        form_y += (1 + min(3, len(content_lines_to_show))) # Adjust form_y
                    elif field_name in ["save", "cancel"]:
                        button_attr = self.highlight_attr if is_active_field else self.normal_attr # Apply highlight if active
                        self.stdscr.addstr(form_y, 4, f"[{field_name.capitalize()}]"[:w-5], button_attr)
                        form_y += 1

            # Common status line for all snippet modes
            status_line_y = content_y_start + snippets_content_height -1
            if status_line_y < h -1 :
                self.stdscr.addstr(status_line_y, 1, " " * (w-2)) # Clear line
                if self.snippet_status_message:
                    self.stdscr.addstr(status_line_y, 1, self.snippet_status_message[:w-2], self.normal_attr)
                    self.snippet_status_message = "" # Clear after display


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
                                formatted_analysis = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
                                self.analysis_display_lines = formatted_analysis.split('\n')
                                self.file_tab_mode = "analyzer"
                                self.analysis_view_top_line = 0
                                self.selected_analysis_item_index = 0 # Reset selection
                                self.analysis_selectable_items = [] # Clear previous
                                # We will populate self.analysis_selectable_items in _draw_main_content
                                # or right after this block if needed for immediate access.
                                # For now, let's plan to populate it during the draw cycle.
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
                    self.analysis_selectable_items = [] # Clear selectable items too
                    self.selected_analysis_item_index = 0
                    self.context_status_message = "Closed analyzer."
                    return True

                analyzer_content_height = max_h - 4 - 2 # h - content_start_y - hint_lines

                if key == curses.KEY_UP:
                    if self.selected_analysis_item_index > 0:
                        self.selected_analysis_item_index -= 1
                        # Ensure selected item is visible
                        if self.analysis_selectable_items:
                            selected_item_start_line = self.analysis_selectable_items[self.selected_analysis_item_index]['display_start_line']
                            if selected_item_start_line < self.analysis_view_top_line:
                                self.analysis_view_top_line = selected_item_start_line
                    return True
                elif key == curses.KEY_DOWN:
                    if self.selected_analysis_item_index < len(self.analysis_selectable_items) - 1:
                        self.selected_analysis_item_index += 1
                        # Ensure selected item is visible
                        if self.analysis_selectable_items:
                            selected_item_start_line = self.analysis_selectable_items[self.selected_analysis_item_index]['display_start_line']
                            # Determine item end line for visibility check
                            selected_item_end_line = len(self.analysis_display_lines) # Default to end of document
                            if self.selected_analysis_item_index + 1 < len(self.analysis_selectable_items):
                                selected_item_end_line = self.analysis_selectable_items[self.selected_analysis_item_index + 1]['display_start_line']
                            else: # last item, its end is the end of all display lines
                                 # Heuristic: if it's the last item, try to show a few lines of it if possible
                                 # For simplicity, let's say its "block" is at least 1 line.
                                 # The crucial part is that selected_item_start_line should be visible.
                                 pass


                            # If the start of the selected item is below the visible area
                            if selected_item_start_line >= self.analysis_view_top_line + analyzer_content_height:
                                self.analysis_view_top_line = selected_item_start_line - analyzer_content_height + 1
                            # If the selected item is the last one, and its start line is already visible,
                            # but maybe not its full content (if it spans multiple lines beyond its start_line marker)
                            # This part is a bit tricky; for now, ensuring start_line is visible is primary.
                            # A more robust approach would be to also consider the number of lines the selected item occupies.
                            # The current drawing logic highlights from item_start to next_item_start (or end).
                            # So, if item_start is visible, its first line is visible.
                            # We might want to scroll such that the *entire* highlighted block is visible.
                            # Let's refine: if the end of the highlighted block is off screen, adjust.
                            if selected_item_end_line > self.analysis_view_top_line + analyzer_content_height:
                                 # Scroll down to make the end of the item visible, but don't scroll past the item's start
                                 self.analysis_view_top_line = selected_item_end_line - analyzer_content_height
                                 if self.analysis_view_top_line > selected_item_start_line : # Don't scroll top line past start of item
                                     self.analysis_view_top_line = selected_item_start_line


                    return True
                # Page up/down for scrolling the view, not selection
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
                elif key == ord('t'):
                    if self.analysis_selectable_items and \
                       0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                        selected_item = self.analysis_selectable_items[self.selected_analysis_item_index]
                        item_name = selected_item['name']
                        item_type = selected_item['type']

                        self.is_generating_tests = True
                        self.context_status_message = f"Generating tests for {item_type} '{item_name}', please wait..."
                        self.stdscr.refresh() # Force a refresh to show the generating message

                        # TODO: Pass item_code_snippet if available from analysis_report
                        generated_content = self.chat_manager.request_test_generation(item_name, item_type)

                        self.is_generating_tests = False
                        self.generated_test_code_lines = generated_content.split('\n')
                        self.file_tab_mode = "test_viewer"
                        self.test_viewer_top_line = 0
                        if generated_content.startswith("# Error"):
                            self.context_status_message = f"Error generating tests: {self.generated_test_code_lines[0]}"
                        else:
                            self.context_status_message = f"Tests generated for {item_name}. Press 'b' to return to analyzer."
                    else:
                        self.context_status_message = "No item selected or analysis items not available."
                    return True
                # elif key == ord('c'): # TODO: Add analysis to context manager?

            elif self.file_tab_mode == "test_viewer":
                test_viewer_content_height = max_h - 4 - 2 # h - content_start_y - hint_lines
                if key == ord('b'):
                    self.file_tab_mode = "analyzer"
                    self.generated_test_code_lines = []
                    self.test_viewer_top_line = 0
                    self.context_status_message = "Returned to analyzer. Select an item and press 't' to generate tests."
                    # analysis_selectable_items should still be populated from before, so no need to reset that here.
                    return True
                elif key == curses.KEY_UP:
                    if self.test_viewer_top_line > 0:
                        self.test_viewer_top_line -= 1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.test_viewer_top_line < len(self.generated_test_code_lines) - test_viewer_content_height:
                        self.test_viewer_top_line += 1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.test_viewer_top_line = max(0, self.test_viewer_top_line - test_viewer_content_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.test_viewer_top_line = min(
                        len(self.generated_test_code_lines) - test_viewer_content_height if len(self.generated_test_code_lines) > test_viewer_content_height else 0,
                        self.test_viewer_top_line + test_viewer_content_height
                    )
                    if self.test_viewer_top_line < 0: self.test_viewer_top_line = 0
                    return True


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
                elif key == curses.KEY_F5: # Refresh suggestions
                    self.command_status_message = "Refreshing suggestions..."
                    self.is_fetching_suggestions = True
                    self.stdscr.refresh() # Show message immediately

                    context_signals = self._get_context_signals()
                    self.suggested_command_names = self.chat_manager.request_command_suggestions(context_signals)

                    self.is_fetching_suggestions = False
                    if self.suggested_command_names:
                        self.command_status_message = f"{len(self.suggested_command_names)} suggestions refreshed."
                    else:
                        self.command_status_message = "No new suggestions or error refreshing."
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
                    if self.command_output_top_line < 0 : self.command_output_top_line = 0 # Ensure not negative
                    return True

        elif current_active_tab == "Snippets":
            # General navigation (UP/DOWN for list mode handled here, others per mode)
            if self.snippet_tab_mode == "list":
                if key == curses.KEY_UP:
                    if self.selected_snippet_index > 0:
                        self.selected_snippet_index -= 1
                        if self.selected_snippet_index < self.snippet_view_top_line:
                            self.snippet_view_top_line = self.selected_snippet_index
                    self.delete_confirm_pending_id = None # Clear confirmation on navigation
                    return True
                elif key == curses.KEY_DOWN:
                    if self.selected_snippet_index < len(self.snippet_list) - 1:
                        self.selected_snippet_index += 1
                        list_display_area_height = (max_h - 4 - 2) - 1 # From drawing logic
                        if self.selected_snippet_index >= self.snippet_view_top_line + list_display_area_height:
                             self.snippet_view_top_line = self.selected_snippet_index - list_display_area_height + 1
                    self.delete_confirm_pending_id = None # Clear confirmation on navigation
                    return True
                # Other list mode keys (Enter, a, d, e) are handled below

            # Clear delete confirmation if not 'd' or list navigation
            if not (self.snippet_tab_mode == "list" and key == ord('d')) and \
               not (self.snippet_tab_mode == "list" and key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE]):
                 self.delete_confirm_pending_id = None


            if self.snippet_tab_mode == "list":
                if key == curses.KEY_ENTER or key == 10 or key == 13:
                    if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                        snippet_id = self.snippet_list[self.selected_snippet_index]['id']
                        snippet = self.snippet_manager.get_snippet_by_id(snippet_id)
                        if snippet:
                            self.active_snippet_content_lines = snippet.get('content', '').split('\n')
                            self.snippet_content_scroll_top = 0
                            self.snippet_tab_mode = "view_content"
                            self.snippet_status_message = f"Viewing: {snippet.get('name')}"
                        else:
                            self.snippet_status_message = "Error: Snippet not found."
                    return True
                elif key == ord('a'): # Add new snippet
                    self.current_snippet_id_being_edited = None
                    self.snippet_form_data = {"name": "", "content": "", "language": "python", "category": "", "tags": ""}
                    self.snippet_form_active_field = "name"
                    self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                    self.snippet_tab_mode = "edit_form"
                    self.snippet_status_message = "Opened add snippet form. Fill details and Save."
                    return True
                elif key == ord('e'): # Edit selected snippet
                    if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                        snippet_to_edit_id = self.snippet_list[self.selected_snippet_index]['id']
                        data = self.snippet_manager.get_snippet_by_id(snippet_to_edit_id)
                        if data:
                            self.current_snippet_id_being_edited = snippet_to_edit_id
                            self.snippet_form_data = data.copy()
                            self.snippet_form_data['tags'] = ", ".join(data.get('tags', []))
                            self.snippet_form_active_field = "name"
                            self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                            self.snippet_tab_mode = "edit_form"
                            self.snippet_status_message = f"Editing: {data.get('name')}. Modify and Save."
                        else:
                            self.snippet_status_message = "Error: Snippet not found for editing."
                    return True
                elif key == ord('d'): # Delete snippet
                    if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                        snippet_to_delete = self.snippet_list[self.selected_snippet_index]
                        snippet_id = snippet_to_delete['id']
                        snippet_name = snippet_to_delete.get('name', 'Unknown snippet')

                        if self.delete_confirm_pending_id == snippet_id: # Confirmed delete
                            if self.snippet_manager.delete_snippet(snippet_id):
                                self.snippet_list = self.snippet_manager.list_snippets()
                                if self.selected_snippet_index >= len(self.snippet_list) and len(self.snippet_list) > 0:
                                    self.selected_snippet_index = len(self.snippet_list) - 1
                                elif not self.snippet_list:
                                     self.selected_snippet_index = 0
                                self.snippet_status_message = f"Snippet '{snippet_name}' deleted."
                            else:
                                self.snippet_status_message = f"Error deleting snippet '{snippet_name}'."
                            self.delete_confirm_pending_id = None
                        else: # First press of 'd'
                            self.delete_confirm_pending_id = snippet_id
                            self.snippet_status_message = f"Press 'd' again to confirm deletion of '{snippet_name}'."
                    else:
                        self.snippet_status_message = "No snippet selected to delete."
                    return True

            elif self.snippet_tab_mode == "view_content":
                content_view_height = max_h - 4 - 2 -1
                if key == ord('b'):
                    self.snippet_tab_mode = "list"
                    self.active_snippet_content_lines = []
                    self.snippet_status_message = "Returned to snippet list."
                    return True
                elif key == curses.KEY_UP:
                    if self.snippet_content_scroll_top > 0: self.snippet_content_scroll_top -= 1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.snippet_content_scroll_top < len(self.active_snippet_content_lines) - content_view_height:
                         self.snippet_content_scroll_top += 1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.snippet_content_scroll_top = max(0, self.snippet_content_scroll_top - content_view_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.snippet_content_scroll_top = min(
                        len(self.active_snippet_content_lines) - content_view_height if len(self.active_snippet_content_lines) > content_view_height else 0,
                        self.snippet_content_scroll_top + content_view_height
                    )
                    if self.snippet_content_scroll_top < 0: self.snippet_content_scroll_top = 0
                    return True

            elif self.snippet_tab_mode == "edit_form":
                form_fields_cycle = ["name", "language", "category", "tags", "content", "save", "cancel"]

                def store_buffer_to_current_field_data():
                    if self.snippet_form_active_field not in ["save", "cancel"]:
                         self.snippet_form_data[self.snippet_form_active_field] = self.snippet_form_input_buffer

                def load_buffer_from_current_field_data():
                    if self.snippet_form_active_field not in ["save", "cancel"]:
                        self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                    else:
                        self.snippet_form_input_buffer = ""

                current_field_idx = form_fields_cycle.index(self.snippet_form_active_field)

                if key == curses.KEY_ESCAPE:
                    self.snippet_tab_mode = "list"
                    self.current_snippet_id_being_edited = None
                    self.snippet_form_data = {}
                    self.snippet_form_input_buffer = ""
                    self.snippet_status_message = "Operation cancelled."
                    return True
                elif key == ord('\t'): # Tab
                    store_buffer_to_current_field_data()
                    next_idx = (current_field_idx + 1) % len(form_fields_cycle)
                    self.snippet_form_active_field = form_fields_cycle[next_idx]
                    load_buffer_from_current_field_data()
                    return True
                elif key == curses.KEY_BTAB or key == 353: # Shift+Tab
                    store_buffer_to_current_field_data()
                    prev_idx = (current_field_idx - 1 + len(form_fields_cycle)) % len(form_fields_cycle)
                    self.snippet_form_active_field = form_fields_cycle[prev_idx]
                    load_buffer_from_current_field_data()
                    return True
                elif key == curses.KEY_ENTER or key == 10 or key == 13:
                    if self.snippet_form_active_field == "save":
                        store_buffer_to_current_field_data()

                        tags_list_str = self.snippet_form_data.get("tags", "")
                        tags_list = [t.strip() for t in tags_list_str.split(',') if t.strip()]

                        form_payload = {
                            "name": self.snippet_form_data.get("name","").strip(),
                            "content": self.snippet_form_data.get("content",""),
                            "language": self.snippet_form_data.get("language","python").strip(),
                            "category": self.snippet_form_data.get("category","").strip(),
                            "tags": tags_list
                        }

                        if not form_payload["name"] or not form_payload["content"]: # Basic validation
                             self.snippet_status_message = "Error: Name and Content fields are required."
                             return True

                        if self.current_snippet_id_being_edited:
                            updated_snippet = self.snippet_manager.update_snippet(self.current_snippet_id_being_edited, **form_payload)
                            if updated_snippet:
                                self.snippet_status_message = f"Snippet '{updated_snippet['name']}' updated."
                            else:
                                self.snippet_status_message = "Error updating snippet."
                        else:
                            new_snippet = self.snippet_manager.add_snippet(**form_payload)
                            if new_snippet:
                                self.snippet_status_message = f"Snippet '{new_snippet['name']}' added."
                            else:
                                self.snippet_status_message = "Error adding snippet. Name and content are required."

                        self.snippet_list = self.snippet_manager.list_snippets()
                        self.snippet_tab_mode = "list"
                        self.current_snippet_id_being_edited = None
                        self.snippet_form_data = {}
                        self.snippet_form_input_buffer = ""
                        return True
                    elif self.snippet_form_active_field == "cancel":
                        self.snippet_tab_mode = "list"
                        self.current_snippet_id_being_edited = None
                        self.snippet_form_data = {}
                        self.snippet_form_input_buffer = ""
                        self.snippet_status_message = "Operation cancelled."
                        return True
                    elif self.snippet_form_active_field == "content":
                        self.snippet_form_input_buffer += "\n"
                        return True

                elif self.snippet_form_active_field not in ["save", "cancel"]:
                    if key == curses.KEY_BACKSPACE or key == 127:
                        self.snippet_form_input_buffer = self.snippet_form_input_buffer[:-1]
                    elif 32 <= key <= 126 or (key == ord('\t') and self.snippet_form_active_field == "content"):
                        self.snippet_form_input_buffer += chr(key)
                    return True


        # Global tab switching (and other global keys if any added later)
        # Note: tab_manager.handle_input(key) changes the current tab internally.
        previous_tab = current_active_tab # Tab before potential switch
        switched_tab = self.tab_manager.handle_input(key) # This attempts to switch tab

        if switched_tab:
            newly_selected_tab = self.tab_manager.get_current_tab()

            if newly_selected_tab == "Commands" and previous_tab != "Commands":
                self.command_status_message = "Fetching command suggestions..."
                self.is_fetching_suggestions = True
                self.stdscr.refresh() # Show message immediately

                context_signals = self._get_context_signals()
                self.suggested_command_names = self.chat_manager.request_command_suggestions(context_signals)

                self.is_fetching_suggestions = False
                if self.suggested_command_names: # Check if list is not empty
                    self.command_status_message = f"Fetched {len(self.suggested_command_names)} suggestions."
                else: # Empty list or error during fetch (already handled to return [])
                    self.command_status_message = "No command suggestions or error fetching."

            elif newly_selected_tab == "Snippets" and previous_tab != "Snippets":
                self.snippet_list = self.snippet_manager.list_snippets()
                self.selected_snippet_index = 0
                self.snippet_view_top_line = 0
                self.snippet_status_message = f"{len(self.snippet_list)} snippets loaded."


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

    def add_file_to_context(self, filepath: str) -> str:
        """
        Adds a file to the context manager and returns a status message.
        This method is intended to be called by ChatManager.
        """
        if not self.context_manager:
            return f"Error: ContextManager not available for {os.path.basename(filepath)}."

        success = self.context_manager.add_file(filepath)
        message = self.context_manager.get_latest_error()

        if success:
            # If add_file succeeded, and error message is None or doesn't reflect success for *this* file,
            # provide a clear success message.
            # ContextManager.get_latest_error() might hold an old error if not cleared on success.
            return f"Successfully added {os.path.basename(filepath)} to context."
        else:
            # If add_file failed, message should ideally contain the error.
            if message:
                return message
            else:
                # Fallback if add_file returns False but no specific error was set.
                return f"Failed to add {os.path.basename(filepath)} to context."

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
