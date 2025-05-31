import curses
import os
import time
import difflib
import threading
import logging # Added for logging
from .tabs import TabManager
from . import files
from . import tree
from .tree import FileTree
from . import viewer
from .context import ContextManager
from .analyzer import CodeAnalyzer
from .commands import CommandRunner
from .chat import ChatManager
from .config import load_config, save_setting
from .snippets import SnippetManager
from .search_indexer import SemanticIndexer
from .diff_utils import generate_diff

class TerminalUI:
    def __init__(self, stdscr, app_logger=None): # Modified to accept app_logger
        self.stdscr = stdscr
        if app_logger:
            self.logger = app_logger
        else:
            self.logger = logging.getLogger("MasterJulesWalker_UI_Default")
            if not self.logger.handlers:
                self.logger.addHandler(logging.NullHandler())

        self.logger.debug("TerminalUI initializing...")
        app_config = load_config() 

        self.tab_names = ["Main", "Files", "Commands", "Snippets", "Settings"]
        self.tab_manager = TabManager(self.tab_names)
        
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        self.highlight_attr = curses.color_pair(1)
        self.dir_attr = curses.color_pair(2)
        self.prompt_attr = curses.color_pair(3)
        self.error_attr = curses.color_pair(4)
        self.normal_attr = curses.A_NORMAL
        self.hint_bar_attr = curses.A_REVERSE

        self.file_tab_mode = "tree"
        self.project_root = "."
        self.file_tree: FileTree | None = None
        self.selected_tree_index = 0
        self.tree_top_line_index = 0
        self.active_file_viewer = None
        self.file_filter_input_mode: bool = False
        self.current_file_filter_term: str = ""

        self.context_manager = ContextManager(project_root=self.project_root)
        self.context_status_message = ""

        self.code_analyzer = CodeAnalyzer(project_root=self.project_root)
        self.active_analysis_report = None 
        self.analysis_display_lines = []   
        self.analysis_view_top_line = 0    
        self.selected_analysis_item_index = 0
        self.analysis_selectable_items = []
        self.is_analyzing_file = False

        self.chat_manager = ChatManager(config=app_config, ui_reference=self)
        self.is_loading_llm_response = False
        self.is_generating_tests = False
        self.is_requesting_refactor = False
        self.is_fetching_suggestions = False

        self.command_runner = CommandRunner(project_root=self.project_root, chat_manager_ref=self.chat_manager)
        self.available_commands = self.command_runner.list_available_commands()
        self.selected_command_index = 0
        self.command_output_lines = []
        self.command_output_top_line = 0
        self.command_status_message = "" 
        self.commands_view_mode = "list"
        self.suggested_command_names = []

        self.snippet_manager = SnippetManager()
        self.snippet_list = []
        self.selected_snippet_index = 0
        self.snippet_view_top_line = 0
        self.snippet_status_message = ""
        self.snippet_tab_mode = "list"
        self.current_snippet_id_being_edited = None
        self.active_snippet_content_lines = []
        self.snippet_content_scroll_top = 0
        self.snippet_form_data = {}
        self.snippet_form_active_field = "name"
        self.snippet_form_input_buffer = ""
        self.delete_confirm_pending_id = None

        self.chat_input_buffer = ""
        self.chat_scroll_top_index = 0 
        self.diff_display_lines = []
        self.diff_view_scroll_top_index = 0
        self.generated_test_code_lines = [] # Initialize for test viewer
        self.test_viewer_top_line = 0       # Initialize for test viewer

        self.settings_api_key_input_buffer = ""
        loaded_api_key = app_config.get("openrouter_api_key")
        self.current_api_key_display = "Loaded from config (not shown)" if loaded_api_key else "Not set"
        self.settings_status_message = ""
        self.settings_model_input_buffer = app_config.get("mjw_model", "")
        self.show_api_key_startup_message = not bool(loaded_api_key)

        self.refactor_code_item_details = None
        self.available_refactorings = [
            "Identify Anti-Patterns", "Suggest Optimizations", "Convert to List Comprehension",
            "Extract Variable", "Generate Docstring (Python)"
        ]
        self.selected_refactoring_index = 0
        self.refactor_diff_lines = []
        self.original_code_snippet = ""
        self.refactored_code_suggestion = ""

        self.search_indexer = SemanticIndexer(project_root=self.project_root)
        self.search_init_error = self.search_indexer.initialization_error
        self.is_search_index_loading = False
        self.search_status_message = ""
        self.is_file_tree_loading = False

        if not self.search_init_error:
            self.is_search_index_loading = True
            self.context_status_message = "Search index loading..."
            self.search_status_message = "Search index loading..."
            self.search_load_thread = threading.Thread(target=self._load_search_index_background, daemon=True)
            self.search_load_thread.start()
        else:
            self.search_status_message = f"Search Indexer Error: {self.search_init_error}"
            self.context_status_message = f"Search Indexer Error: {self.search_init_error}"

        self.search_query_input_buffer = ""
        self.original_search_query = ""
        self.search_results_list = []
        self.selected_search_result_index = 0
        self.search_results_top_line = 0
        self.logger.debug("TerminalUI initialized.")

    def _load_search_index_background(self):
        try:
            load_success = self.search_indexer.load_index()
            if load_success:
                self.search_status_message = "Search index loaded."
                self.logger.info("Search index loaded successfully in background.")
            else:
                specific_error = getattr(self.search_indexer, 'last_load_error', 'Failed to load existing index.')
                self.search_status_message = f"Search index load failed: {specific_error}"
                self.logger.error(f"Search index load failed in background: {specific_error}")
        except Exception as e:
            self.logger.exception(f"Exception in _load_search_index_background: {e}")
            self.search_status_message = f"Search index load error: {str(e)}"
        finally:
            self.is_search_index_loading = False

    def _get_context_signals(self):
        signals = {
            "current_tab": self.tab_manager.get_current_tab(),
            "context_files": self.context_manager.get_context_summary(),
            "available_commands": self.available_commands
        }
        chat_history = self.chat_manager.get_formatted_history()
        signals["recent_chat_history"] = chat_history[-5:]
        analysis_summary = "None"
        if self.active_analysis_report and isinstance(self.active_analysis_report, dict) and "error" not in self.active_analysis_report:
            raw_summary = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
            max_len = 500
            analysis_summary = raw_summary[:max_len-3] + "..." if len(raw_summary) > max_len else raw_summary
        elif self.active_analysis_report and isinstance(self.active_analysis_report, dict) and "error" in self.active_analysis_report:
            analysis_summary = f"Error in analysis: {self.active_analysis_report['error']}"
        signals["active_analysis"] = analysis_summary
        return signals

    def _load_project_files(self, path="."):
        self.is_file_tree_loading = True
        self.context_status_message = "Loading project files..."
        self.logger.info(f"Loading project files from path: {path}")
        try:
            self.project_root = os.path.abspath(path)
            raw_project_items = files.get_project_files(self.project_root)
            self.file_tree = FileTree(raw_project_items)
            self.selected_tree_index = 0
            self.tree_top_line_index = 0
            self.current_file_filter_term = ""
            if self.file_tree:
                 self.file_tree.set_filter_term("")
            self.context_status_message = "Project files loaded."
            self.logger.info("Project files loaded successfully.")
        except Exception as e:
            self.logger.exception(f"Error loading project files: {e}")
            self.file_tree = None
            self.context_status_message = f"Error loading files: {str(e)}"
        finally:
            self.is_file_tree_loading = False

    def _draw_title(self):
        # ... (content as before, no changes for this subtask)
        title = "MasterJulesWalker"
        h, w = self.stdscr.getmaxyx()
        x = w // 2 - len(title) // 2
        y = 0 
        try: self.stdscr.addstr(y, x, title, curses.A_BOLD)
        except curses.error: pass


    def _draw_tabs(self):
        # ... (content as before, no changes for this subtask)
        h, w = self.stdscr.getmaxyx()
        tab_y_position = 2 ; tab_spacing = 4; current_x = 1
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
        # ... (content as before, no changes for this subtask)
        for y_line in range(content_y_start, h - 2):
            try: self.stdscr.addstr(y_line, 1, " " * (w - 2))
            except curses.error: pass

    def _draw_main_content(self):
        h, w = self.stdscr.getmaxyx()
        content_y_start = 4
        input_line_y = h - 3
        if input_line_y < content_y_start: input_line_y = content_y_start

        self._clear_content_area(content_y_start, h, w)
        current_active_tab = self.tab_manager.get_current_tab()

        if current_active_tab == "Main":
            if self.show_api_key_startup_message:
                # ... (content as before, already includes return)
                startup_message = [
                    "[ MasterJulesWalker Notice ]",
                    "---------------------------------------------------------------",
                    "Your OpenRouter API key is not configured.",
                    "AI-powered features (chat, analysis, suggestions) will not work",
                    "until an API key is provided.",
                    "",
                    "Please go to the \"Settings\" tab (use Right Arrow key)",
                    "to enter your API key.",
                    "---------------------------------------------------------------",
                    "(This message will disappear once you navigate away or save a key.)"
                ]
                for i, line in enumerate(startup_message):
                    if content_y_start + i < input_line_y:
                        line_x = (w - len(line)) // 2
                        line_x = max(1, line_x)
                        try:
                             self.stdscr.addstr(content_y_start + i, line_x, line[:w- (line_x +1)], self.normal_attr)
                        except curses.error:
                            pass
                return
            elif self.chat_manager.is_diff_active:
                # ... (diff display logic, defensive checks added)
                if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, f"Reviewing suggestion for: {os.path.basename(self.chat_manager.active_diff_filepath)}", self.highlight_attr)
                    except curses.error: pass

                if not self.diff_display_lines: # Defensive check
                    self.diff_display_lines = ["No diff content to display or error generating diff."]

                # ... rest of diff display logic
                diff_view_y_start = content_y_start + 1
                diff_view_height = input_line_y - diff_view_y_start
                if diff_view_height < 0: diff_view_height = 0
                num_diff_lines = len(self.diff_display_lines)

                if num_diff_lines <= diff_view_height: self.diff_view_scroll_top_index = 0
                elif self.diff_view_scroll_top_index > num_diff_lines - diff_view_height:
                    self.diff_view_scroll_top_index = num_diff_lines - diff_view_height
                if self.diff_view_scroll_top_index < 0: self.diff_view_scroll_top_index = 0
                for i in range(diff_view_height):
                    line_idx = self.diff_view_scroll_top_index + i
                    if line_idx < num_diff_lines:
                        line_content = self.diff_display_lines[line_idx].rstrip()
                        attr = self.normal_attr
                        if line_content.startswith('+'): attr = curses.color_pair(3)
                        elif line_content.startswith('-'): attr = curses.color_pair(4)
                        elif line_content.startswith('@@'): attr = curses.color_pair(2)
                        try: self.stdscr.addstr(diff_view_y_start + i, 1, line_content[:w-2], attr)
                        except curses.error: pass
            else:
                # ... (chat history display)
                chat_history_lines = self.chat_manager.get_formatted_history()
                chat_display_height = input_line_y - content_y_start
                if chat_display_height < 0: chat_display_height = 0

                if self.is_loading_llm_response:
                    loading_msg = "MJW is thinking..."
                    loading_msg_y = input_line_y - 1
                    if loading_msg_y >= content_y_start and chat_display_height > 0 :
                         try: self.stdscr.addstr(loading_msg_y , 2, loading_msg[:w-3], self.highlight_attr)
                         except curses.error: pass
                         if chat_display_height > 0 : chat_display_height -=1

                num_history_lines = len(chat_history_lines)
                if num_history_lines <= chat_display_height: self.chat_scroll_top_index = 0
                elif self.chat_scroll_top_index > num_history_lines - chat_display_height:
                    self.chat_scroll_top_index = num_history_lines - chat_display_height
                if self.chat_scroll_top_index < 0: self.chat_scroll_top_index = 0
                for i in range(chat_display_height):
                    line_idx = self.chat_scroll_top_index + i
                    if line_idx < num_history_lines:
                        try: self.stdscr.addstr(content_y_start + i, 2, chat_history_lines[line_idx][:w-3], self.normal_attr)
                        except curses.error: pass

                if input_line_y >= content_y_start :
                    prompt_indicator = "> "
                    try:
                        self.stdscr.addstr(input_line_y, 1, prompt_indicator, self.prompt_attr)
                        self.stdscr.addstr(input_line_y, 1 + len(prompt_indicator), self.chat_input_buffer[:w - (2 + len(prompt_indicator))])
                    except curses.error: pass

        elif current_active_tab == "Files":
            # ... (file tree None check as before) ...
            if self.file_tree is None:
                if not self.is_file_tree_loading:
                    is_previous_load_error = self.context_status_message and "Error loading files" in self.context_status_message
                    if not is_previous_load_error or "Search index loading..." in self.context_status_message or \
                       "Search Indexer Error:" in self.context_status_message or \
                       self.context_status_message == "Project files loaded.":
                        self._load_project_files()
                display_message = self.context_status_message
                if not display_message:
                    display_message = "Loading project files..." if self.is_file_tree_loading else "File tree not available."
                if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, display_message[:w-2], self.highlight_attr)
                    except curses.error: pass
                return

            if self.file_tab_mode == "tree":
                # ... (file tree drawing logic as before) ...
                context_summary_list = self.context_manager.get_context_summary()
                num_summary_lines = len(context_summary_list)
                available_height_for_file_tab_content = input_line_y - content_y_start
                if available_height_for_file_tab_content < 0: available_height_for_file_tab_content = 0
                context_header_h = 1 if num_summary_lines > 0 else 0
                info_line_h = 1
                tree_view_height = available_height_for_file_tab_content - num_summary_lines - context_header_h - info_line_h
                tree_view_height = max(1, tree_view_height)
                selected_item_tuple = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                selected_item_path_for_highlight = selected_item_tuple[0] if selected_item_tuple else None
                current_tree_display_tuples = self.file_tree.get_display_lines(selected_item_path_for_highlight) if self.file_tree else []
                if not current_tree_display_tuples:
                    filter_msg = f"Filter: {self.current_file_filter_term}" if self.current_file_filter_term else "No files found or tree not loaded."
                    if content_y_start < input_line_y:
                        try: self.stdscr.addstr(content_y_start, 2, filter_msg[:w-3])
                        except curses.error: pass
                else:
                    if self.selected_tree_index >= self.tree_top_line_index + tree_view_height:
                         self.tree_top_line_index = self.selected_tree_index - tree_view_height + 1
                    if self.selected_tree_index < self.tree_top_line_index:
                         self.tree_top_line_index = self.selected_tree_index
                    self.tree_top_line_index = max(0, self.tree_top_line_index)
                    if len(current_tree_display_tuples) > tree_view_height:
                        self.tree_top_line_index = min(self.tree_top_line_index, len(current_tree_display_tuples) - tree_view_height)
                    else: self.tree_top_line_index = 0
                    for i in range(tree_view_height):
                        current_tree_line_idx_in_filtered_list = self.tree_top_line_index + i
                        if current_tree_line_idx_in_filtered_list < len(current_tree_display_tuples):
                            display_str, item_path_str = current_tree_display_tuples[current_tree_line_idx_in_filtered_list]
                            abs_item_path = os.path.join(self.project_root, item_path_str)
                            prefix_ctx = "[CTX] " if abs_item_path in self.context_manager.context_files else ""
                            attr = self.normal_attr
                            if selected_item_path_for_highlight and item_path_str == selected_item_path_for_highlight:
                                 attr = self.highlight_attr
                            line_to_draw = (prefix_ctx + display_str)[:w-2]
                            if content_y_start + i < input_line_y:
                                try: self.stdscr.addstr(content_y_start + i, 1, line_to_draw, attr)
                                except curses.error: pass
                        else: break
                context_draw_y_start = content_y_start + tree_view_height
                if num_summary_lines > 0:
                    if context_draw_y_start < input_line_y:
                        try: self.stdscr.addstr(context_draw_y_start, 1, "--- Context ('c' to add/remove selected) ---"[:w-2], self.highlight_attr)
                        except curses.error: pass
                    context_draw_y_start += 1
                    for i, summary_line in enumerate(context_summary_list):
                        if context_draw_y_start + i < input_line_y:
                             try: self.stdscr.addstr(context_draw_y_start + i, 1, summary_line[:w-2])
                             except curses.error: pass
                info_line_y_pos = content_y_start + tree_view_height + context_header_h + num_summary_lines
                if info_line_y_pos < input_line_y :
                    info_line_content_to_display = ""
                    highlight_info_line = False
                    if self.file_filter_input_mode:
                        info_line_content_to_display = f"Filter Input: {self.current_file_filter_term}"
                        highlight_info_line = True
                    elif self.is_search_index_loading:
                        info_line_content_to_display = "Search index loading..."
                        highlight_info_line = True
                    elif self.search_init_error:
                        info_line_content_to_display = f"Search unavailable: {self.search_init_error}"
                        highlight_info_line = True
                    elif self.context_status_message:
                        info_line_content_to_display = self.context_status_message
                        highlight_info_line = True
                    elif self.search_status_message and not ("Search index loaded." in self.search_status_message or "Search index rebuilt." in self.search_status_message):
                        info_line_content_to_display = self.search_status_message
                        highlight_info_line = True
                    else:
                        ctx_size_kb = self.context_manager.current_context_size_bytes // 1024
                        num_ctx_files = len(self.context_manager.context_files)
                        max_num_files = ContextManager.MAX_CONTEXT_FILES
                        info_line_content_to_display = f"Ctx: {num_ctx_files}/{max_num_files} {ctx_size_kb}KB. Filter: '{self.current_file_filter_term}'"
                        if self.search_status_message and not ("Search index loaded." in self.search_status_message or "Search index rebuilt." in self.search_status_message):
                             highlight_info_line = True
                    try:
                        self.stdscr.addstr(info_line_y_pos, 1, " " * (w - 2))
                        self.stdscr.addstr(info_line_y_pos, 1, info_line_content_to_display[:w-2],
                                       self.highlight_attr if highlight_info_line else self.normal_attr)
                    except curses.error: pass
                    if self.context_status_message == info_line_content_to_display and \
                       not self.is_search_index_loading and \
                       not (self.context_status_message and "Loading project files..." in self.context_status_message) and \
                       not (self.context_status_message and "Initializing file tree..." in self.context_status_message) and \
                       info_line_y_pos < input_line_y:
                        self.context_status_message = ""
            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                # ... (file viewer drawing as before) ...
                viewer_display_height = input_line_y - content_y_start
                if viewer_display_height < 0: viewer_display_height = 0
                view_lines = self.active_file_viewer.get_display_lines(viewer_display_height)
                for i, line_content in enumerate(view_lines):
                    if i < viewer_display_height and (content_y_start + i < input_line_y ) :
                        try: self.stdscr.addstr(content_y_start + i, 1, line_content[:w-2])
                        except curses.error: pass
                    else: break
            elif self.file_tab_mode == "analyzer":
                # ... (analyzer drawing, defensive checks added)
                analyzer_view_height = input_line_y - content_y_start
                if analyzer_view_height < 0: analyzer_view_height = 0
                if self.is_analyzing_file:
                    loading_msg = "Analyzing file, please wait..."
                    msg_y = content_y_start + analyzer_view_height // 2
                    if msg_y >= content_y_start and msg_y < input_line_y:
                        msg_x = max(1, (w - len(loading_msg)) // 2)
                        try: self.stdscr.addstr(msg_y, msg_x, loading_msg, self.highlight_attr)
                        except curses.error: pass
                elif self.active_analysis_report and isinstance(self.active_analysis_report, dict) and not self.analysis_selectable_items:
                    # ... (selectable items logic as before) ...
                    temp_selectable_items = []
                    def find_item_line_in_display(item_prefix, item_name, display_lines):
                        for idx, line_content_selectable in enumerate(display_lines):
                            if line_content_selectable.strip().startswith(item_prefix + " " + item_name): return idx
                        return -1
                    if 'classes' in self.active_analysis_report:
                        for i_cls, class_info in enumerate(self.active_analysis_report.get('classes',[])):
                            if isinstance(class_info, dict) and 'name' in class_info:
                                line_idx = find_item_line_in_display("Class:", class_info['name'], self.analysis_display_lines)
                                if line_idx != -1: temp_selectable_items.append({'type': 'class', 'name': class_info['name'], 'report_idx': i_cls, 'display_start_line': line_idx})
                    if 'functions' in self.active_analysis_report:
                        for i_func, func_info in enumerate(self.active_analysis_report.get('functions',[])):
                            if isinstance(func_info, dict) and 'name' in func_info:
                                line_idx = find_item_line_in_display("Function:", func_info['name'], self.analysis_display_lines)
                                if line_idx != -1: temp_selectable_items.append({'type': 'function', 'name': func_info['name'], 'report_idx': i_func, 'display_start_line': line_idx})
                    temp_selectable_items.sort(key=lambda x: x['display_start_line'])
                    self.analysis_selectable_items = temp_selectable_items
                if not self.is_analyzing_file and not self.analysis_display_lines:
                    if content_y_start < input_line_y:
                        try: self.stdscr.addstr(content_y_start, 1, "No analysis report to display."[:w-2])
                        except curses.error: pass
                elif not self.is_analyzing_file and self.analysis_display_lines:
                    # ... (rest of analysis display logic) ...
                    if self.analysis_view_top_line < 0: self.analysis_view_top_line = 0
                    if len(self.analysis_display_lines) > analyzer_view_height:
                        self.analysis_view_top_line = min(self.analysis_view_top_line, len(self.analysis_display_lines) - analyzer_view_height)
                    else: self.analysis_view_top_line = 0
                    selected_item_display_start = -1; selected_item_display_end = -1
                    if self.analysis_selectable_items and 0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                        selected_item = self.analysis_selectable_items[self.selected_analysis_item_index]
                        selected_item_display_start = selected_item['display_start_line']
                        if self.selected_analysis_item_index + 1 < len(self.analysis_selectable_items):
                            selected_item_display_end = self.analysis_selectable_items[self.selected_analysis_item_index + 1]['display_start_line']
                        else: selected_item_display_end = len(self.analysis_display_lines)
                    for i_draw in range(analyzer_view_height):
                        current_display_line_idx = self.analysis_view_top_line + i_draw
                        if current_display_line_idx < len(self.analysis_display_lines):
                            line_to_draw = self.analysis_display_lines[current_display_line_idx]
                            attr_to_use = self.normal_attr
                            if selected_item_display_start != -1 and selected_item_display_start <= current_display_line_idx < selected_item_display_end:
                                attr_to_use = self.highlight_attr
                            if content_y_start + i_draw < input_line_y:
                                try: self.stdscr.addstr(content_y_start + i_draw, 1, line_to_draw[:w-2], attr_to_use)
                                except curses.error: pass
                        else: break
                if self.is_generating_tests and not self.is_analyzing_file:
                    loading_msg = "Generating tests, please wait..."
                    msg_y = content_y_start + analyzer_view_height // 2
                    if msg_y >= content_y_start and msg_y < input_line_y:
                        msg_x = max(1, (w - len(loading_msg)) // 2)
                        try: self.stdscr.addstr(msg_y, msg_x, loading_msg, self.highlight_attr)
                        except curses.error: pass
            elif self.file_tab_mode == "refactor_selection":
                # ... (refactor selection list as before) ...
                 if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, f"Select Refactoring for {self.refactor_code_item_details['name'] if self.refactor_code_item_details else 'N/A'}:"[:w-2], self.highlight_attr)
                    except curses.error: pass
                list_y_start = content_y_start + 2
                for i, ref_op in enumerate(self.available_refactorings):
                    attr = self.highlight_attr if i == self.selected_refactoring_index else self.normal_attr
                    if list_y_start + i < input_line_y:
                        try: self.stdscr.addstr(list_y_start + i, 2, ref_op[:w-3], attr)
                        except curses.error: pass
            elif self.file_tab_mode == "refactor_diff_view":
                # ... (refactor diff view, defensive check for self.refactor_diff_lines)
                if self.is_requesting_refactor:
                    loading_msg = "Requesting refactor from LLM..."
                    msg_y = content_y_start + (input_line_y - content_y_start) // 2
                    if msg_y >= content_y_start and msg_y < input_line_y:
                        try: self.stdscr.addstr(msg_y, max(1, (w - len(loading_msg))//2), loading_msg, self.highlight_attr)
                        except curses.error: pass
                else:
                    if content_y_start < input_line_y:
                        try: self.stdscr.addstr(content_y_start, 1, "Refactoring Diff:"[:w-2], self.highlight_attr)
                        except curses.error: pass
                    diff_view_height = (input_line_y - (content_y_start + 1))
                    if diff_view_height < 0: diff_view_height = 0
                    if not self.refactor_diff_lines: # Defensive check
                        self.refactor_diff_lines = ["No diff to display or error generating diff."]
                    for i, line_content in enumerate(self.refactor_diff_lines):
                        if i >= diff_view_height: break
                        line_attr = self.normal_attr
                        if line_content.startswith('+'): line_attr = curses.color_pair(3)
                        elif line_content.startswith('-'): line_attr = curses.color_pair(4)
                        elif line_content.startswith('@@'): line_attr = curses.color_pair(2)
                        if content_y_start + 1 + i < input_line_y:
                            try: self.stdscr.addstr(content_y_start + 1 + i, 1, line_content.rstrip()[:w-2], line_attr)
                            except curses.error: pass
            elif self.file_tab_mode == "test_viewer":
                # ... (test viewer as before) ...
                test_viewer_height = input_line_y - content_y_start
                if test_viewer_height < 0: test_viewer_height = 0
                if not self.generated_test_code_lines:
                    if content_y_start < input_line_y:
                        try: self.stdscr.addstr(content_y_start, 1, "No test code to display."[:w-2])
                        except curses.error: pass
                else:
                    if self.test_viewer_top_line < 0: self.test_viewer_top_line = 0
                    if len(self.generated_test_code_lines) > test_viewer_height:
                        self.test_viewer_top_line = min(self.test_viewer_top_line, len(self.generated_test_code_lines) - test_viewer_height)
                    else: self.test_viewer_top_line = 0
                    for i_draw in range(test_viewer_height):
                        current_display_line_idx = self.test_viewer_top_line + i_draw
                        if current_display_line_idx < len(self.generated_test_code_lines):
                            line_to_draw = self.generated_test_code_lines[current_display_line_idx]
                            if content_y_start + i_draw < input_line_y:
                                try: self.stdscr.addstr(content_y_start + i_draw, 1, line_to_draw[:w-2])
                                except curses.error: pass
                        else: break
            elif self.file_tab_mode == "search_input":
                # ... (search input as before) ...
                 prompt_text = f"Search Query ([Enter] Search, [Esc] Cancel): > {self.search_query_input_buffer}"
                if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, prompt_text[:w-2])
                    except curses.error: pass
            elif self.file_tab_mode == "search_results":
                # ... (search results, defensive checks added)
                if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, f"Search Results for '{self.original_search_query}' ({self.search_status_message})"[:w-2], self.highlight_attr)
                    except curses.error: pass
                results_display_height = input_line_y - (content_y_start + 1)
                if results_display_height < 0: results_display_height = 0
                items_per_page = results_display_height // 2 # Integer division
                if not self.search_results_list: # Defensive check
                     if content_y_start + 2 < input_line_y:
                        try: self.stdscr.addstr(content_y_start + 2, 2, "No results or error in search."[:w-3])
                        except curses.error: pass
                else:
                    # ... rest of search results display ...
                    if self.selected_search_result_index >= self.search_results_top_line + items_per_page and items_per_page > 0 :
                         self.search_results_top_line = self.selected_search_result_index - items_per_page + 1
                    if self.selected_search_result_index < self.search_results_top_line: self.search_results_top_line = self.selected_search_result_index
                    self.search_results_top_line = max(0, self.search_results_top_line)
                    if len(self.search_results_list) > items_per_page and items_per_page > 0:
                         self.search_results_top_line = min(self.search_results_top_line, len(self.search_results_list) - items_per_page)
                    else: self.search_results_top_line = 0
                    current_y_search = content_y_start + 2
                    for i_search in range(items_per_page):
                        idx_to_display = self.search_results_top_line + i_search
                        if idx_to_display < len(self.search_results_list):
                            if current_y_search + 1 >= input_line_y: break
                            item = self.search_results_list[idx_to_display]
                            attr = self.highlight_attr if idx_to_display == self.selected_search_result_index else self.normal_attr
                            if isinstance(item, dict): # Defensive check for item structure
                                display_line = f"{item.get('file_path','N/A')} (L{item.get('start_line','?')}-{item.get('end_line','?')}) Score: {item.get('score',0):.2f}"
                                text_preview = item.get('text','').replace('\n', ' ').strip()
                                try:
                                    self.stdscr.addstr(current_y_search, 2, display_line[:w-3], attr)
                                    self.stdscr.addstr(current_y_search + 1, 4, text_preview[:w-5], attr)
                                except curses.error: pass
                            current_y_search += 2
                        else: break

        elif current_active_tab == "Commands":
            # ... (content as before) ...
            list_view_height = input_line_y - content_y_start
            if list_view_height < 0: list_view_height = 0
            if self.commands_view_mode == "list":
                header_text = "Commands (Suggestions [*], F5 to refresh):"
                if content_y_start < input_line_y:
                    try: self.stdscr.addstr(content_y_start, 1, header_text[:w-2], self.highlight_attr)
                    except curses.error: pass
                actual_list_display_height = list_view_height -1
                if self.command_status_message: actual_list_display_height -=1
                if actual_list_display_height <0: actual_list_display_height = 0
                if self.is_fetching_suggestions:
                    loading_msg = "Fetching command suggestions..."
                    msg_y = content_y_start + 1
                    if msg_y < input_line_y -1 :
                        try: self.stdscr.addstr(msg_y, 2, loading_msg[:w-3])
                        except curses.error: pass
                else:
                    if self.selected_command_index < 0: self.selected_command_index = 0
                    if self.selected_command_index >= len(self.available_commands):
                        self.selected_command_index = max(0, len(self.available_commands) -1)
                    display_y_cmd = content_y_start + 1
                    for i_cmd, (name, desc) in enumerate(self.available_commands):
                        if display_y_cmd >= content_y_start + 1 + actual_list_display_height: break
                        prefix = "[*] " if name in self.suggested_command_names else "    "
                        display_text = f"{prefix}{name}: {desc}"
                        attr = self.highlight_attr if i_cmd == self.selected_command_index else self.normal_attr
                        try: self.stdscr.addstr(display_y_cmd, 2, display_text[:w-3], attr)
                        except curses.error: pass
                        display_y_cmd += 1
                status_line_y_cmd = input_line_y - 1
                if self.command_status_message and status_line_y_cmd > content_y_start:
                     if status_line_y_cmd < input_line_y:
                        try:
                            self.stdscr.addstr(status_line_y_cmd, 1, " " * (w-2))
                            self.stdscr.addstr(status_line_y_cmd, 1, self.command_status_message[:w-2], self.normal_attr)
                        except curses.error: pass
            elif self.commands_view_mode == "output":
                output_view_height = input_line_y - content_y_start
                if output_view_height < 0: output_view_height = 0
                if not self.command_output_lines:
                    if content_y_start < input_line_y:
                        try: self.stdscr.addstr(content_y_start, 1, "No output to display."[:w-2])
                        except curses.error: pass
                else:
                    if self.command_output_top_line < 0: self.command_output_top_line = 0
                    if len(self.command_output_lines) > output_view_height:
                        self.command_output_top_line = min(self.command_output_top_line, len(self.command_output_lines) - output_view_height)
                    else: self.command_output_top_line = 0
                    for i_out in range(output_view_height):
                        current_display_line_idx = self.command_output_top_line + i_out
                        if current_display_line_idx < len(self.command_output_lines):
                            line_to_draw = self.command_output_lines[current_display_line_idx]
                            if content_y_start + i_out < input_line_y :
                                try: self.stdscr.addstr(content_y_start + i_out, 1, line_to_draw[:w-2])
                                except curses.error: pass
                        else: break
        elif current_active_tab == "Snippets":
            # ... (content as before) ...
            snippets_total_available_height = input_line_y - content_y_start
            if snippets_total_available_height < 0: snippets_total_available_height = 0
            status_line_y_snip = input_line_y -1
            snippets_content_height = snippets_total_available_height -1
            if snippets_content_height <0: snippets_content_height = 0
            if self.snippet_tab_mode == "list":
                header_line_y = content_y_start
                if header_line_y < status_line_y_snip :
                    try: self.stdscr.addstr(header_line_y, 1, "Snippets:"[:w-2], self.highlight_attr)
                    except curses.error: pass
                list_display_area_height = snippets_content_height -1
                if list_display_area_height < 0: list_display_area_height = 0
                if not self.snippet_list:
                    if content_y_start + 1 < status_line_y_snip:
                        try: self.stdscr.addstr(content_y_start + 1, 2, "No snippets found."[:w-3])
                        except curses.error: pass
                else:
                    if self.selected_snippet_index < 0: self.selected_snippet_index = 0
                    if self.selected_snippet_index >= len(self.snippet_list): self.selected_snippet_index = max(0, len(self.snippet_list) -1)
                    if self.selected_snippet_index >= self.snippet_view_top_line + list_display_area_height and list_display_area_height > 0:
                        self.snippet_view_top_line = self.selected_snippet_index - list_display_area_height + 1
                    if self.selected_snippet_index < self.snippet_view_top_line: self.snippet_view_top_line = self.selected_snippet_index
                    self.snippet_view_top_line = max(0, self.snippet_view_top_line)
                    if len(self.snippet_list) > list_display_area_height:
                        self.snippet_view_top_line = min(self.snippet_view_top_line, len(self.snippet_list) - list_display_area_height)
                    else: self.snippet_view_top_line = 0
                    display_y_snip = content_y_start + 1
                    for i_snip in range(list_display_area_height):
                        current_list_item_idx = self.snippet_view_top_line + i_snip
                        if current_list_item_idx < len(self.snippet_list):
                            snippet = self.snippet_list[current_list_item_idx]
                            display_text = f"{snippet.get('name', 'Unnamed Snippet')} ({snippet.get('language', 'N/A')})"
                            attr = self.highlight_attr if current_list_item_idx == self.selected_snippet_index else self.normal_attr
                            if display_y_snip < status_line_y_snip :
                                try: self.stdscr.addstr(display_y_snip, 2, display_text[:w-3], attr)
                                except curses.error: pass
                            display_y_snip += 1
                        else: break
            elif self.snippet_tab_mode == "view_content":
                header_line_y = content_y_start
                if header_line_y < status_line_y_snip:
                    try: self.stdscr.addstr(header_line_y, 1, "Snippet Content:"[:w-2], self.highlight_attr)
                    except curses.error: pass
                content_display_height_snip = snippets_content_height -1
                if content_display_height_snip <0: content_display_height_snip = 0
                if not self.active_snippet_content_lines:
                     if content_y_start + 1 < status_line_y_snip:
                        try: self.stdscr.addstr(content_y_start + 1, 2, "No content to display."[:w-3])
                        except curses.error: pass
                else:
                    if self.snippet_content_scroll_top < 0: self.snippet_content_scroll_top = 0
                    if len(self.active_snippet_content_lines) > content_display_height_snip:
                        self.snippet_content_scroll_top = min(self.snippet_content_scroll_top, len(self.active_snippet_content_lines) - content_display_height_snip)
                    else: self.snippet_content_scroll_top = 0
                    display_y_snip_content = content_y_start + 1
                    for i_snip_content in range(content_display_height_snip):
                        line_idx = self.snippet_content_scroll_top + i_snip_content
                        if line_idx < len(self.active_snippet_content_lines):
                            if display_y_snip_content + i_snip_content < status_line_y_snip:
                                try: self.stdscr.addstr(display_y_snip_content + i_snip_content, 2, self.active_snippet_content_lines[line_idx][:w-3])
                                except curses.error: pass
                        else: break
            elif self.snippet_tab_mode == "edit_form":
                form_y = content_y_start
                form_title = "Edit Snippet" if self.current_snippet_id_being_edited else "Add New Snippet"
                if form_y < status_line_y_snip:
                    try: self.stdscr.addstr(form_y, 1, f"{form_title}:"[:w-2], self.highlight_attr)
                    except curses.error: pass
                form_y += 1
                fields = ["name", "language", "category", "tags", "content", "save", "cancel"]
                def draw_field_snip(label, value, y_pos, is_active):
                    if y_pos < status_line_y_snip:
                        attr_f = self.highlight_attr if is_active else self.normal_attr
                        try:
                            self.stdscr.addstr(y_pos, 2, f"{label}: "[:w-3], self.normal_attr)
                            display_value_f = self.snippet_form_input_buffer if is_active else value
                            self.stdscr.addstr(y_pos, 2 + len(label) + 2, display_value_f[:w - (4 + len(label) + 2)], attr_f)
                        except curses.error: pass
                for field_name in fields:
                    if form_y >= status_line_y_snip : break
                    is_active_field = (self.snippet_form_active_field == field_name)
                    if field_name not in ["content", "save", "cancel"]:
                        draw_field_snip(field_name.capitalize(), self.snippet_form_data.get(field_name, ""), form_y, is_active_field); form_y += 1
                    elif field_name == "content":
                        if form_y < status_line_y_snip:
                            try: self.stdscr.addstr(form_y, 2, "Content:"[:w-3], self.normal_attr)
                            except curses.error: pass
                        content_attr = self.highlight_attr if is_active_field else self.normal_attr
                        content_value_to_display = self.snippet_form_input_buffer if is_active_field else self.snippet_form_data.get("content", "")
                        content_lines_to_show = content_value_to_display.split('\n')[:3]
                        for i_content, line_content_f in enumerate(content_lines_to_show):
                            if form_y + 1 + i_content >= status_line_y_snip -1: break
                            try: self.stdscr.addstr(form_y + 1 + i_content, 4, line_content_f[:w-5], content_attr)
                            except curses.error: pass
                        form_y += (1 + min(3, len(content_lines_to_show)))
                    elif field_name in ["save", "cancel"]:
                        if form_y < status_line_y_snip:
                            button_attr = self.highlight_attr if is_active_field else self.normal_attr
                            try: self.stdscr.addstr(form_y, 4, f"[{field_name.capitalize()}]"[:w-5], button_attr)
                            except curses.error: pass
                        form_y += 1
            if status_line_y_snip >= content_y_start and status_line_y_snip < input_line_y:
                try:
                    self.stdscr.addstr(status_line_y_snip, 1, " " * (w-2))
                    if self.snippet_status_message:
                        self.stdscr.addstr(status_line_y_snip, 1, self.snippet_status_message[:w-2], self.normal_attr)
                        self.snippet_status_message = ""
                except curses.error: pass
        elif current_active_tab == "Settings":
            # ... (content as before) ...
            y_offset = content_y_start
            def try_add_settings_line(y_val, x_val, text_val, attr_val=self.normal_attr):
                if y_val < input_line_y:
                    try: self.stdscr.addstr(y_val, x_val, text_val[:w-(x_val+1)], attr_val)
                    except curses.error: pass
                return y_val + 1
            y_offset = try_add_settings_line(y_offset, 2, f"Current API Key: {self.current_api_key_display}")
            y_offset = try_add_settings_line(y_offset +1, 2, "New OpenRouter API Key:")
            y_offset = try_add_settings_line(y_offset, 2, "> " + self.settings_api_key_input_buffer, self.prompt_attr)
            y_offset = try_add_settings_line(y_offset +1, 2, f"Model Name (current: {self.chat_manager.model_name}):")
            y_offset = try_add_settings_line(y_offset, 2, "> " + self.settings_model_input_buffer, self.prompt_attr)
            if self.settings_status_message:
                if y_offset + 1 < input_line_y:
                     try_add_settings_line(y_offset + 1, 2, self.settings_status_message, self.highlight_attr)
                self.settings_status_message = ""
        else: 
            placeholder_text = f"Content for {current_active_tab} tab (Not yet implemented)."
            if content_y_start < input_line_y:
                try: self.stdscr.addstr(content_y_start, 1, placeholder_text[:w-2])
                except curses.error: pass

    def _draw_hint_bar(self):
        # ... (content as before, no changes for this subtask)
        h, w = self.stdscr.getmaxyx()
        hint_bar_y = h - 2
        if hint_bar_y < 0 or hint_bar_y >= h : return

        try:
            current_attr = self.hint_bar_attr
            self.stdscr.attron(current_attr)
            self.stdscr.addstr(hint_bar_y, 0, " " * w)
            self.stdscr.attroff(current_attr)
        except curses.error:
            try:
                self.stdscr.addstr(hint_bar_y, 0, " " * w)
            except curses.error: return

        global_hints = "q:Quit | ←→:Tabs"
        tab_specific_hints = ""
        current_tab = self.tab_manager.get_current_tab()

        if current_tab == "Main":
            if self.show_api_key_startup_message:
                tab_specific_hints = "→:Settings to add API Key"
            elif self.chat_manager.is_diff_active:
                tab_specific_hints = "Scroll:↑/↓ | Cmds:Ctrl+P"
            else:
                tab_specific_hints = "Enter:Send | Hist:↑/↓ | Cmds:Ctrl+P"
        elif current_tab == "Files":
            if self.file_tab_mode == "tree":
                filter_hint = "Esc:Clr" if self.file_filter_input_mode else "/:Filter"
                search_hint = "s:Search" if (not self.search_init_error and not self.is_search_index_loading) else "s:Search(Wait)"
                reindex_hint = "Ctrl+R:ReIdx"
                tab_specific_hints = f"Enter:View|c:Ctx|a:Analyze|{filter_hint}|{search_hint}|{reindex_hint}"
            elif self.file_tab_mode == "viewer":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.file_tab_mode == "analyzer":
                tab_specific_hints = "b:Back | Scroll:↑/↓ | t:GenTests | r:Refactor"
            elif self.file_tab_mode == "test_viewer":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.file_tab_mode == "refactor_selection":
                tab_specific_hints = "Enter:Select | b:Back | Nav:↑/↓"
            elif self.file_tab_mode == "refactor_diff_view":
                tab_specific_hints = "a:Apply | c:Cancel"
            elif self.file_tab_mode == "search_input":
                tab_specific_hints = "Enter:Search | Esc:Cancel"
            elif self.file_tab_mode == "search_results":
                tab_specific_hints = "Enter:Open | Esc/s:NewSearch | Nav:↑/↓"
        elif current_tab == "Commands":
            if self.commands_view_mode == "list":
                tab_specific_hints = "Enter:Run | F5:Suggest | Nav:↑/↓"
            elif self.commands_view_mode == "output":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
        elif current_tab == "Snippets":
            if self.snippet_tab_mode == "list":
                tab_specific_hints = "Nav:↑/↓ | Enter:View|a:Add|e:Edit|d:Del"
            elif self.snippet_tab_mode == "view_content":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.snippet_tab_mode == "edit_form":
                tab_specific_hints = "Tab:NextField | Enter:Save/Action | Esc:Cancel"
        elif current_tab == "Settings":
            tab_specific_hints = "Enter:Save | Esc:Clear"

        final_hints_str = f"{global_hints} || {tab_specific_hints}"

        max_hint_len = w - 2
        if max_hint_len < 0: max_hint_len = 0

        if len(final_hints_str) > max_hint_len:
            overflow = len(final_hints_str) - max_hint_len
            if len(global_hints) < max_hint_len - 5:
                 available_for_tab_specific = max_hint_len - (len(global_hints) + 4)
                 if available_for_tab_specific < 3 : available_for_tab_specific = 3
                 if len(tab_specific_hints) > available_for_tab_specific :
                    tab_specific_hints = tab_specific_hints[:available_for_tab_specific-3] + "..."
                 final_hints_str = f"{global_hints} || {tab_specific_hints}"
            else:
                final_hints_str = final_hints_str[:max_hint_len-3] + "..."
            if len(final_hints_str) > max_hint_len:
                final_hints_str = final_hints_str[:max_hint_len]
        try:
            current_attr = self.hint_bar_attr
            self.stdscr.attron(current_attr)
            self.stdscr.addnstr(hint_bar_y, 1, final_hints_str, w - 2, current_attr)
            self.stdscr.attroff(current_attr)
        except curses.error:
            pass

    def _handle_input(self):
        try:
            key = self.stdscr.getch()
        except curses.error: return True # Should be rare, but treat as no input
        if key == -1: return True # No input
        if key == ord('q') or key == 3: # q or Ctrl+C
            self.logger.info(f"Quit key ({key}) pressed.")
            return False

        current_active_tab = self.tab_manager.get_current_tab()
        
        try:
            max_h, max_w = self.stdscr.getmaxyx()
            input_line_y_for_scroll_calc = max_h - 3

            if current_active_tab == "Settings":
                if key == curses.KEY_ENTER or key == 10 or key == 13:
                    saved_something = False
                    api_key_modified_or_cleared = False
                    try:
                        api_key_to_save_input = self.settings_api_key_input_buffer.strip()

                        if api_key_to_save_input:
                            save_setting('openrouter_api_key', api_key_to_save_input)
                            self.current_api_key_display = "Saved (not shown)"
                            self.show_api_key_startup_message = False
                            saved_something = True
                            api_key_modified_or_cleared = True
                            self.logger.info("OpenRouter API key saved.")
                        elif self.settings_api_key_input_buffer == " ":
                            save_setting('openrouter_api_key', None)
                            self.current_api_key_display = "Cleared"
                            saved_something = True
                            api_key_modified_or_cleared = True
                            self.logger.info("OpenRouter API key cleared.")

                        model_to_save_input = self.settings_model_input_buffer.strip()
                        if model_to_save_input:
                            current_config_model = load_config().get("mjw_model", "")
                            if model_to_save_input != current_config_model or api_key_modified_or_cleared:
                                save_setting('mjw_model', model_to_save_input)
                                saved_something = True
                                self.logger.info(f"MJW model saved: {model_to_save_input}")

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
                    except Exception as e_settings:
                        self.logger.exception(f"Error saving settings: {e_settings}")
                        self.settings_status_message = "Error saving settings. Check logs."
                    return True
                elif key == curses.KEY_BACKSPACE or key == 127:
                    self.settings_api_key_input_buffer = self.settings_api_key_input_buffer[:-1]
                    self.settings_status_message = ""
                    return True
                elif key == curses.KEY_ESCAPE:
                    self.settings_api_key_input_buffer = ""
                    self.settings_model_input_buffer = self.chat_manager.model_name
                    self.settings_status_message = "Input fields cleared."
                    return True
                elif 32 <= key <= 126:
                    self.settings_api_key_input_buffer += chr(key)
                    self.settings_status_message = ""
                    return True
            # ... (rest of _handle_input as it was from the last successful application, including Files, Commands, Snippets tab logic) ...
            # Note: The Snippets tab logic has been updated with try-except blocks in previous steps.
            # This overwrite will include those already applied snippet error handling changes.
            # The Files tab logic also has its error handling from previous steps.
            # The Commands tab logic also has its error handling.
            # The LLM callbacks also have their error logging.
            elif current_active_tab == "Main":
                if self.chat_manager.is_diff_active:
                    content_y_start_scroll = 4
                    diff_view_y_start_scroll = content_y_start_scroll + 1
                    diff_view_height_scroll = input_line_y_for_scroll_calc - diff_view_y_start_scroll
                    if diff_view_height_scroll < 0: diff_view_height_scroll = 0
                    num_diff_lines = len(self.diff_display_lines)
                    if key == curses.KEY_UP:
                        if self.diff_view_scroll_top_index > 0: self.diff_view_scroll_top_index -=1
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.diff_view_scroll_top_index < num_diff_lines - diff_view_height_scroll:
                            self.diff_view_scroll_top_index += 1
                        return True
                    elif key == curses.KEY_PPAGE:
                        self.diff_view_scroll_top_index = max(0, self.diff_view_scroll_top_index - diff_view_height_scroll)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.diff_view_scroll_top_index = min(num_diff_lines - diff_view_height_scroll if num_diff_lines > diff_view_height_scroll else 0, self.diff_view_scroll_top_index + diff_view_height_scroll)
                        if self.diff_view_scroll_top_index < 0: self.diff_view_scroll_top_index = 0
                        return True
                else:
                    chat_display_height_scroll = input_line_y_for_scroll_calc - 4
                    if self.is_loading_llm_response and chat_display_height_scroll > 0 : chat_display_height_scroll -=1
                    if chat_display_height_scroll < 0: chat_display_height_scroll = 0
                    num_history_lines = len(self.chat_manager.get_formatted_history())
                    if self.is_loading_llm_response:
                        if self.tab_manager.handle_input(key): return True
                        return True
                    if key == curses.KEY_UP:
                        if self.chat_scroll_top_index > 0: self.chat_scroll_top_index -= 1
                        return True
                    elif key == curses.KEY_DOWN:
                         if self.chat_scroll_top_index < num_history_lines - chat_display_height_scroll: self.chat_scroll_top_index += 1
                         return True
                    elif key == curses.KEY_PPAGE:
                        self.chat_scroll_top_index = max(0, self.chat_scroll_top_index - chat_display_height_scroll)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.chat_scroll_top_index = min(num_history_lines - chat_display_height_scroll if num_history_lines > chat_display_height_scroll else 0, self.chat_scroll_top_index + chat_display_height_scroll)
                        if self.chat_scroll_top_index < 0 : self.chat_scroll_top_index =0
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        if self.chat_input_buffer.strip():
                            self.is_loading_llm_response = True
                            self.context_status_message = "MJW is thinking..."
                            current_user_input_for_callback = self.chat_input_buffer.strip()
                            def _on_chat_message_complete(response_str, error_str):
                                self.is_loading_llm_response = False
                                if error_str:
                                    self.logger.error(f"ChatManager send_message error: {error_str}")
                                    self.context_status_message = f"Error: {error_str}"
                                h_cb, w_cb = self.stdscr.getmaxyx()
                                chat_display_height_cb = (h_cb - 3) - 4
                                if chat_display_height_cb < 0: chat_display_height_cb = 0
                                num_history_lines_after = len(self.chat_manager.get_formatted_history())
                                if num_history_lines_after > chat_display_height_cb:
                                    self.chat_scroll_top_index = num_history_lines_after - chat_display_height_cb
                                else:
                                    self.chat_scroll_top_index = 0
                            self.chat_manager.send_message(current_user_input_for_callback, _on_chat_message_complete)
                            self.chat_input_buffer = ""
                        return True
                    elif key == curses.KEY_BACKSPACE or key == 127: self.chat_input_buffer = self.chat_input_buffer[:-1]; return True
                    elif 32 <= key <= 126: self.chat_input_buffer += chr(key); return True

            elif current_active_tab == "Files":
                if self.file_tree is None:
                    if self.is_file_tree_loading:
                        self.context_status_message = "Project files are still loading, please wait..."
                    else:
                        self.context_status_message = "File tree not available. Try switching tabs or restarting."
                    if key == curses.KEY_RIGHT or key == curses.KEY_LEFT or key == 9:
                        if self.tab_manager.handle_input(key):
                            if self.tab_manager.get_current_tab() == "Files" and not self.is_file_tree_loading:
                                self._load_project_files()
                            return True
                    return True

                content_area_height_files = (max_h - 3) - 4
                if content_area_height_files < 0 : content_area_height_files = 0
                if self.file_tab_mode == "tree":
                    if self.file_filter_input_mode:
                        if key == curses.KEY_ESCAPE:
                            self.file_filter_input_mode = False
                            if self.current_file_filter_term:
                                self.current_file_filter_term = ""
                                if self.file_tree: self.file_tree.set_filter_term("")
                                self.selected_tree_index = 0; self.tree_top_line_index = 0
                            self.context_status_message = "Filter cleared."
                            return True
                        elif key == curses.KEY_ENTER or key == 10 or key == 13:
                            self.file_filter_input_mode = False
                            self.context_status_message = f"Filter active: '{self.current_file_filter_term}'" if self.current_file_filter_term else "Filter cleared."
                            if self.file_tree and self.file_tree.get_filtered_items_count() > 0:
                                if self.selected_tree_index >= self.file_tree.get_filtered_items_count():
                                    self.selected_tree_index = self.file_tree.get_filtered_items_count() - 1
                            elif self.file_tree and self.file_tree.get_filtered_items_count() == 0:
                                 self.selected_tree_index = 0
                            return True
                        elif key == curses.KEY_BACKSPACE or key == 127:
                            if self.current_file_filter_term:
                                self.current_file_filter_term = self.current_file_filter_term[:-1]
                                if self.file_tree: self.file_tree.set_filter_term(self.current_file_filter_term)
                                self.selected_tree_index = 0; self.tree_top_line_index = 0
                            return True
                        elif 32 <= key <= 126:
                            self.current_file_filter_term += chr(key)
                            if self.file_tree: self.file_tree.set_filter_term(self.current_file_filter_term)
                            self.selected_tree_index = 0; self.tree_top_line_index = 0
                            return True
                        return True
                    else:
                        if key == curses.KEY_UP:
                            if self.selected_tree_index > 0: self.selected_tree_index -= 1
                            return True
                        elif key == curses.KEY_DOWN:
                            if self.file_tree and self.selected_tree_index < self.file_tree.get_filtered_items_count() - 1:
                                self.selected_tree_index += 1
                            return True
                        elif key == ord('c'):
                            selected_item = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                            if selected_item:
                                item_path_rel, item_type = selected_item
                                if item_type == "file":
                                    try:
                                        abs_item_path = os.path.join(self.project_root, item_path_rel)
                                        if abs_item_path in self.context_manager.context_files:
                                            self.context_manager.remove_file(item_path_rel)
                                            self.context_status_message = self.context_manager.get_latest_error() or f"Removed {os.path.basename(item_path_rel)}"
                                            self.logger.info(f"Removed {item_path_rel} from context.")
                                        else:
                                            self.context_manager.add_file(item_path_rel)
                                            self.context_status_message = self.context_manager.get_latest_error() or f"Added {os.path.basename(item_path_rel)}"
                                            self.logger.info(f"Added {item_path_rel} to context.")
                                        if self.context_manager.get_latest_error():
                                            self.logger.error(f"ContextManager error for {item_path_rel}: {self.context_manager.get_latest_error()}")
                                    except Exception as e_ctx:
                                        self.logger.exception(f"Error adding/removing {item_path_rel} from context: {e_ctx}")
                                        self.context_status_message = f"Error updating context for {os.path.basename(item_path_rel)}. Check logs."
                                else:
                                    self.context_status_message = "Cannot add directories to context."
                            return True
                        elif key == ord('a'):
                            selected_item = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                            if selected_item:
                                item_path_rel, item_type = selected_item
                                if item_type == "file" and item_path_rel.endswith(".py"):
                                    self.is_analyzing_file = True
                                    self.context_status_message = f"Analyzing {os.path.basename(item_path_rel)}..."
                                    def _on_analysis_complete(analysis_report_dict):
                                        self.is_analyzing_file = False
                                        self.active_analysis_report = analysis_report_dict
                                        if analysis_report_dict and "error" not in analysis_report_dict:
                                            formatted_analysis = self.code_analyzer.format_analysis_for_llm(analysis_report_dict)
                                            self.analysis_display_lines = formatted_analysis.split('\n')
                                            self.file_tab_mode = "analyzer"
                                            self.analysis_view_top_line = 0; self.selected_analysis_item_index = 0
                                            self.analysis_selectable_items = []
                                            self.context_status_message = f"Analyzed: {os.path.basename(item_path_rel)}"
                                        else:
                                            error_msg = analysis_report_dict.get("error", "Analysis failed.")
                                            self.logger.error(f"Analysis error for {item_path_rel}: {error_msg}")
                                            self.context_status_message = error_msg
                                            self.analysis_display_lines = [f"Analysis Error: {error_msg}"]
                                            self.file_tab_mode = "analyzer"
                                    self.code_analyzer.analyze_file(item_path_rel, callback=_on_analysis_complete)
                                else:
                                    self.context_status_message = "Select a Python file to analyze."
                            else:
                                self.context_status_message = "No file selected to analyze."
                            return True
                        elif key == curses.KEY_ENTER or key == 10 or key == 13:
                            selected_item = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                            if selected_item:
                                item_path_rel, item_type = selected_item
                                if item_type == "file":
                                    if self.active_file_viewer:
                                        try:
                                            self.active_file_viewer.close()
                                        except Exception as e_close:
                                            self.logger.exception(f"Error closing active file viewer: {e_close}")
                                        self.active_file_viewer = None
                                    try:
                                        full_path = os.path.join(self.project_root, item_path_rel)
                                        self.active_file_viewer = viewer.FileViewer(full_path)
                                        self.file_tab_mode = "viewer"
                                        self.context_status_message = f"Viewing {item_path_rel}"
                                        self.logger.info(f"Opened file for viewing: {full_path}")
                                    except Exception as e_viewer:
                                        self.logger.exception(f"Error instantiating FileViewer for {item_path_rel}: {e_viewer}")
                                        self.active_file_viewer = None
                                        self.context_status_message = f"Error opening file {os.path.basename(item_path_rel)}. Check logs."
                            return True
                        elif key == ord('/'):
                            if self.chat_manager.is_diff_active:
                                self.context_status_message = "Cannot filter while diff review is active."
                                return True
                            self.file_filter_input_mode = True
                            self.context_status_message = "Enter filter term (Esc: clear/exit, Enter: apply & exit)."
                            return True
                        elif key == 18:
                            if self.is_search_index_loading:
                                self.context_status_message = "Search index is currently loading, please wait."
                            elif self.search_init_error:
                                self.context_status_message = f"Search Indexer not ready: {self.search_init_error}"
                            elif self.file_tree is None:
                                self.context_status_message = "File tree not loaded. Cannot re-index."
                            else:
                                self.context_status_message = "Rebuilding search index in background...";
                                all_master_items = self.file_tree.project_items_master
                                project_filepaths = [item[0] for item in all_master_items if item[1] == 'file']
                                self.is_search_index_loading = True
                                self.search_status_message = "Re-indexing..."
                                def reindex_and_load_background():
                                    try:
                                        self.search_indexer.build_index(project_filepaths)
                                        load_success = self.search_indexer.load_index()
                                        if load_success:
                                            self.search_status_message = "Search index rebuilt."
                                            self.context_status_message = "Search index rebuilt."
                                        else:
                                            specific_error = getattr(self.search_indexer, 'last_load_error', 'Failed to load after rebuild.')
                                            self.search_status_message = f"Index rebuilt, load failed: {specific_error}"
                                            self.context_status_message = self.search_status_message
                                    except Exception as e:
                                        self.logger.exception(f"Error during background re-indexing for {project_filepaths[:5]}...: {e}")
                                        self.search_status_message = f"Re-index error: {str(e)}"
                                        self.context_status_message = self.search_status_message
                                    finally:
                                        self.is_search_index_loading = False
                                reindex_thread = threading.Thread(target=reindex_and_load_background, daemon=True)
                                reindex_thread.start()
                            return True
                elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                    if key == ord('b'):
                        self.active_file_viewer.close(); self.active_file_viewer = None
                        self.file_tab_mode = "tree"; self.context_status_message = "Closed viewer."
                        return True
                    if self.active_file_viewer.handle_input(key, content_area_height_files): return True
                elif self.file_tab_mode == "analyzer":
                    analyzer_content_height = (max_h - 3) - 4
                    if analyzer_content_height <0: analyzer_content_height = 0
                    if key == ord('b'):
                        self.file_tab_mode = "tree"; self.analysis_display_lines = []; self.active_analysis_report = None
                        self.analysis_selectable_items = []; self.selected_analysis_item_index = 0
                        self.context_status_message = "Closed analyzer."
                        return True
                    if key == curses.KEY_UP:
                        if self.selected_analysis_item_index > 0:
                            self.selected_analysis_item_index -= 1
                            if self.analysis_selectable_items:
                                selected_item_start_line = self.analysis_selectable_items[self.selected_analysis_item_index]['display_start_line']
                                if selected_item_start_line < self.analysis_view_top_line: self.analysis_view_top_line = selected_item_start_line
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.selected_analysis_item_index < len(self.analysis_selectable_items) - 1:
                            self.selected_analysis_item_index += 1
                            if self.analysis_selectable_items:
                                selected_item_start_line = self.analysis_selectable_items[self.selected_analysis_item_index]['display_start_line']
                                selected_item_end_line = len(self.analysis_display_lines)
                                if self.selected_analysis_item_index + 1 < len(self.analysis_selectable_items):
                                    selected_item_end_line = self.analysis_selectable_items[self.selected_analysis_item_index + 1]['display_start_line']
                                if selected_item_start_line >= self.analysis_view_top_line + analyzer_content_height:
                                    self.analysis_view_top_line = selected_item_start_line - analyzer_content_height + 1
                                if selected_item_end_line > self.analysis_view_top_line + analyzer_content_height:
                                     self.analysis_view_top_line = selected_item_end_line - analyzer_content_height
                                     if self.analysis_view_top_line > selected_item_start_line : self.analysis_view_top_line = selected_item_start_line
                        return True
                    elif key == curses.KEY_PPAGE:
                        self.analysis_view_top_line = max(0, self.analysis_view_top_line - analyzer_content_height)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.analysis_view_top_line = min(len(self.analysis_display_lines) - analyzer_content_height if len(self.analysis_display_lines) > analyzer_content_height else 0, self.analysis_view_top_line + analyzer_content_height)
                        if self.analysis_view_top_line < 0: self.analysis_view_top_line = 0
                        return True
                    elif key == ord('t'):
                        if self.analysis_selectable_items and 0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                            selected_item = self.analysis_selectable_items[self.selected_analysis_item_index]
                            item_name = selected_item['name']; item_type = selected_item['type']
                            self.is_generating_tests = True
                            self.context_status_message = f"Generating tests for {item_type} '{item_name}'..."
                            def _on_test_generation_complete(generated_content_str, error_str):
                                self.is_generating_tests = False
                                if error_str:
                                    self.logger.error(f"Test generation error for {item_name} ({item_type}): {error_str}")
                                    self.generated_test_code_lines = [error_str]
                                    self.context_status_message = f"Test gen error: {error_str}"
                                elif generated_content_str:
                                    self.generated_test_code_lines = generated_content_str.split('\n')
                                    self.context_status_message = f"Tests for {item_name} ready."
                                    self.file_tab_mode = "test_viewer"; self.test_viewer_top_line = 0
                                else:
                                    self.generated_test_code_lines = ["# Info: No tests generated or empty response."]
                                    self.context_status_message = "Test generation returned no content."
                            self.chat_manager.request_test_generation(item_name, item_type, callback=_on_test_generation_complete)
                        else:
                            self.context_status_message = "No item selected for test generation."
                        return True
                    elif key == ord('r'):
                        if self.analysis_selectable_items and 0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                            selected_item_details = self.analysis_selectable_items[self.selected_analysis_item_index]
                            item_path_rel = self.active_analysis_report['filepath']
                            element_name = selected_item_details['name']; element_type = selected_item_details['type']
                            code_details = self.code_analyzer.get_code_element_source(item_path_rel, element_name, element_type)
                            if not code_details.get("error"):
                                self.refactor_code_item_details = {'filepath': item_path_rel, 'name': element_name, 'type': element_type, **code_details}
                                self.original_code_snippet = code_details['source_code']; self.selected_refactoring_index = 0
                                self.file_tab_mode = "refactor_selection"; self.context_status_message = f"Select refactoring for {element_name}."
                            else: self.context_status_message = code_details.get("error", "Failed to get source.")
                        else: self.context_status_message = "No item selected."
                        return True
                elif self.file_tab_mode == "refactor_selection":
                    if key == curses.KEY_UP:
                        if self.selected_refactoring_index > 0: self.selected_refactoring_index -= 1
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.selected_refactoring_index < len(self.available_refactorings) - 1: self.selected_refactoring_index += 1
                        return True
                    elif key == ord('b') or key == curses.KEY_ESCAPE:
                        self.file_tab_mode = "analyzer"; self.context_status_message = "Refactoring cancelled."
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        selected_op = self.available_refactorings[self.selected_refactoring_index]
                        self.is_requesting_refactor = True
                        self.file_tab_mode = "refactor_diff_view"
                        self.context_status_message = f"Requesting '{selected_op}'..."
                        def _on_refactor_complete(refactored_code_str, error_str):
                            self.is_requesting_refactor = False
                            if error_str:
                                self.logger.error(f"Refactor request error for '{selected_op}' on item '{self.refactor_code_item_details.get('name', 'unknown')}': {error_str}")
                                self.context_status_message = error_str
                                self.file_tab_mode = "refactor_selection"
                                self.refactor_diff_lines = []
                            elif refactored_code_str:
                                self.refactored_code_suggestion = refactored_code_str
                                self.refactor_diff_lines = list(difflib.unified_diff(
                                    self.original_code_snippet.splitlines(keepends=True),
                                    self.refactored_code_suggestion.splitlines(keepends=True),
                                    fromfile='original', tofile='refactored', lineterm=''
                                ))
                                self.context_status_message = "Suggestion received. Review diff."
                            else:
                                self.context_status_message = "Refactoring returned no content."
                                self.file_tab_mode = "refactor_selection"
                                self.refactor_diff_lines = []
                        self.chat_manager.request_refactor(self.original_code_snippet, selected_op, callback=_on_refactor_complete)
                        return True
                elif self.file_tab_mode == "refactor_diff_view":
                    if key == ord('c') or key == ord('b') or key == curses.KEY_ESCAPE:
                        self.file_tab_mode = "refactor_selection"; self.refactor_diff_lines = []; self.context_status_message = "Refactoring cancelled."
                        return True
                    elif key == ord('a'):
                        if self.refactor_code_item_details and self.refactored_code_suggestion:
                            filepath_rel = self.refactor_code_item_details['filepath']; start_line = self.refactor_code_item_details['start_line']; end_line = self.refactor_code_item_details['end_line']
                            abs_filepath = os.path.join(self.project_root, filepath_rel)
                            try:
                                with open(abs_filepath, 'r', encoding='utf-8') as f_read: file_lines = f_read.readlines()
                                new_code_lines = self.refactored_code_suggestion.splitlines(keepends=True)
                                if new_code_lines and not self.refactored_code_suggestion.endswith('\n'): new_code_lines[-1] += '\n'
                                if not new_code_lines and self.refactored_code_suggestion: new_code_lines = ['\n']
                                prefix = file_lines[:start_line - 1]; suffix = file_lines[end_line:]
                                with open(abs_filepath, 'w', encoding='utf-8') as f_write: f_write.writelines(prefix + new_code_lines + suffix)
                                self.context_status_message = f"Refactoring applied to {os.path.basename(filepath_rel)}."
                                self.logger.info(f"Refactoring applied to {filepath_rel}")
                                self.active_analysis_report = None; self.analysis_display_lines = []
                            except IOError as e_io:
                                self.logger.exception(f"IOError applying refactoring to {filepath_rel}: {e_io}")
                                self.context_status_message = f"IOError applying refactor to {os.path.basename(filepath_rel)}. Check logs."
                            except Exception as e_apply:
                                self.logger.exception(f"Error applying refactoring to {filepath_rel}: {e_apply}")
                                self.context_status_message = f"Error applying refactor to {os.path.basename(filepath_rel)}. Check logs."
                            finally:
                                self.file_tab_mode = "analyzer"; self.refactor_code_item_details = None; self.original_code_snippet = ""; self.refactored_code_suggestion = ""; self.refactor_diff_lines = []; self.selected_refactoring_index = 0
                        else:
                            self.context_status_message = "Error: Missing details for apply."; self.file_tab_mode = "analyzer"
                            self.refactor_code_item_details = None; self.original_code_snippet = ""; self.refactored_code_suggestion = ""; self.refactor_diff_lines = []; self.selected_refactoring_index = 0
                        return True
                elif self.file_tab_mode == "search_input":
                    if self.is_search_index_loading:
                        self.context_status_message = "Search index loading, please wait to search."
                        if key == curses.KEY_ESCAPE:
                             self.file_tab_mode = "tree"; self.search_query_input_buffer = ""; self.context_status_message = "Search cancelled."
                        return True
                    if self.search_init_error:
                        self.context_status_message = f"Search is unavailable: {self.search_init_error}"
                        if key == curses.KEY_ESCAPE:
                             self.file_tab_mode = "tree"; self.search_query_input_buffer = ""; self.context_status_message = "Search cancelled."
                        return True
                    if key == curses.KEY_ESCAPE:
                        self.file_tab_mode = "tree"; self.context_status_message = "Search cancelled."; self.search_query_input_buffer = ""
                        return True
                    elif key == curses.KEY_BACKSPACE or key == 127:
                        self.search_query_input_buffer = self.search_query_input_buffer[:-1]
                        return True
                    elif 32 <= key <= 126:
                        self.search_query_input_buffer += chr(key)
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        query = self.search_query_input_buffer.strip(); self.original_search_query = query
                        if not query: self.search_status_message = "Query is empty"; self.search_results_list = []; self.file_tab_mode = "search_results"; return True
                        self.search_status_message = "Searching..."; self.file_tab_mode = "search_results";
                        search_response = self.search_indexer.search(query, top_n=20)
                        if search_response.get("error"): self.search_status_message = search_response["error"]; self.search_results_list = []
                        else:
                            self.search_results_list = search_response["results"]
                            self.search_status_message = f"{len(self.search_results_list)} results." if self.search_results_list else "No results found."
                        self.selected_search_result_index = 0; self.search_results_top_line = 0
                        return True
                elif self.file_tab_mode == "search_results":
                    results_display_area_height = (max_h - 3) - (4 + 1)
                    if results_display_area_height < 0: results_display_area_height = 0
                    items_per_page = results_display_area_height // 2
                    if items_per_page == 0 and results_display_area_height > 0: items_per_page = 1
                    if key == curses.KEY_UP:
                        if self.selected_search_result_index > 0:
                            self.selected_search_result_index -= 1
                            if self.selected_search_result_index < self.search_results_top_line: self.search_results_top_line = self.selected_search_result_index
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.selected_search_result_index < len(self.search_results_list) - 1:
                            self.selected_search_result_index += 1
                            if self.selected_search_result_index >= self.search_results_top_line + items_per_page and items_per_page >0: self.search_results_top_line = self.selected_search_result_index - items_per_page + 1
                        return True
                    elif key == curses.KEY_PPAGE:
                        self.selected_search_result_index = max(0, self.selected_search_result_index - items_per_page if items_per_page > 0 else 0)
                        self.search_results_top_line = max(0, self.search_results_top_line - items_per_page if items_per_page > 0 else 0)
                        if self.selected_search_result_index < self.search_results_top_line : self.search_results_top_line = self.selected_search_result_index
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.selected_search_result_index = min(len(self.search_results_list) - 1, self.selected_search_result_index + (items_per_page if items_per_page > 0 else 0))
                        if len(self.search_results_list) > items_per_page and items_per_page > 0: self.search_results_top_line = min(len(self.search_results_list) - items_per_page, self.search_results_top_line + items_per_page)
                        if self.selected_search_result_index >= self.search_results_top_line + items_per_page and items_per_page > 0: self.search_results_top_line = self.selected_search_result_index - items_per_page + 1
                        if self.search_results_top_line < 0: self.search_results_top_line = 0
                        return True
                    elif key == curses.KEY_ESCAPE:
                        self.file_tab_mode = "search_input"; self.search_status_message = ""; self.context_status_message = "Enter new query or modify."
                        return True
                    elif key == ord('s'):
                        self.file_tab_mode = "search_input"; self.search_query_input_buffer = ""; self.search_status_message = ""; self.context_status_message = "Enter new search query."
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        if self.search_results_list and 0 <= self.selected_search_result_index < len(self.search_results_list):
                            selected_item = self.search_results_list[self.selected_search_result_index]
                            filepath_rel = selected_item['file_path']; line_to_scroll_to = selected_item['start_line']
                            abs_path = os.path.join(self.project_root, filepath_rel)
                            if os.path.isfile(abs_path):
                                if self.active_file_viewer: self.active_file_viewer.close()
                                self.active_file_viewer = viewer.FileViewer(abs_path)
                                h_dim, w_dim = self.stdscr.getmaxyx()
                                viewer_disp_height = (h_dim - 3) - 4
                                if viewer_disp_height < 0: viewer_disp_height = 0
                                self.active_file_viewer.scroll_to_line(line_to_scroll_to, viewer_disp_height)
                                self.file_tab_mode = "viewer"
                                self.context_status_message = f"Opened {filepath_rel} at line {line_to_scroll_to}."
                            else: self.search_status_message = f"Error: File {filepath_rel} not found."; self.context_status_message = self.search_status_message
                        return True
                elif self.file_tab_mode == "test_viewer":
                    test_viewer_content_height = (max_h - 3) - 4
                    if test_viewer_content_height < 0 : test_viewer_content_height = 0
                    if key == ord('b'):
                        self.file_tab_mode = "analyzer"; self.generated_test_code_lines = []; self.test_viewer_top_line = 0
                        self.context_status_message = "Returned to analyzer."
                        return True
                    elif key == curses.KEY_UP:
                        if self.test_viewer_top_line > 0: self.test_viewer_top_line -= 1
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.test_viewer_top_line < len(self.generated_test_code_lines) - test_viewer_content_height: self.test_viewer_top_line += 1
                        return True
                    elif key == curses.KEY_PPAGE:
                        self.test_viewer_top_line = max(0, self.test_viewer_top_line - test_viewer_content_height)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.test_viewer_top_line = min(len(self.generated_test_code_lines) - test_viewer_content_height if len(self.generated_test_code_lines) > test_viewer_content_height else 0, self.test_viewer_top_line + test_viewer_content_height)
                        if self.test_viewer_top_line < 0: self.test_viewer_top_line = 0
                        return True

            elif current_active_tab == "Commands":
                cmd_content_height = (max_h - 3) - 4
                if cmd_content_height < 0: cmd_content_height = 0
                if self.commands_view_mode == "list":
                    if key == curses.KEY_UP:
                        if self.selected_command_index > 0: self.selected_command_index -= 1
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.selected_command_index < len(self.available_commands) - 1: self.selected_command_index += 1
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        if 0 <= self.selected_command_index < len(self.available_commands):
                            command_name, _ = self.available_commands[self.selected_command_index]
                            self.command_status_message = f"Running {command_name}...";
                            self.logger.info(f"Attempting to run command: {command_name}")
                            self.command_output_lines = [self.command_status_message]; self.commands_view_mode = "output";
                            try:
                                success, output, error_str = self.command_runner.run_command(command_name, args_str=None)
                                if success:
                                    self.command_output_lines = output.split('\n') if output else ["Command ran successfully with no output."]
                                    self.command_status_message = f"'{command_name}' finished."
                                    self.logger.info(f"Command '{command_name}' finished successfully.")
                                else:
                                    self.command_output_lines = (error_str.split('\n') if error_str else [f"Command '{command_name}' failed."])
                                    self.command_status_message = f"Error running '{command_name}'."
                                    self.logger.error(f"Command '{command_name}' failed. Error: {error_str}")
                            except Exception as e_cmd_run:
                                self.logger.exception(f"Exception running command '{command_name}': {e_cmd_run}")
                                self.command_output_lines = [f"Critical error running {command_name}. Check logs."]
                                self.command_status_message = f"Critical error running {command_name}."
                            self.command_output_top_line = 0
                        return True
                    elif key == curses.KEY_F5:
                        self.command_status_message = "Refreshing suggestions..."
                        self.is_fetching_suggestions = True
                        context_signals = self._get_context_signals()
                        def _on_suggestions_complete(suggestions_list, error_str):
                            self.is_fetching_suggestions = False
                            if error_str:
                                self.logger.error(f"Command suggestion fetch error: {error_str}")
                                self.command_status_message = f"Suggestion error: {error_str}"
                                self.suggested_command_names = []
                            elif suggestions_list is not None:
                                self.suggested_command_names = suggestions_list
                                self.command_status_message = f"{len(self.suggested_command_names)} suggestions."
                            else:
                                self.command_status_message = "Failed to get suggestions (unknown error)."
                                self.suggested_command_names = []
                        self.chat_manager.request_command_suggestions(context_signals, _on_suggestions_complete)
                        return True
                elif self.commands_view_mode == "output":
                    cmd_output_content_height_scroll = cmd_content_height
                    if key == ord('b'):
                        self.commands_view_mode = "list"; self.command_output_lines = []; self.command_status_message = "Returned to command list."
                        return True
                    if key == curses.KEY_UP:
                        if self.command_output_top_line > 0: self.command_output_top_line -=1
                        return True
                    elif key == curses.KEY_DOWN:
                         if self.command_output_top_line < len(self.command_output_lines) - cmd_output_content_height_scroll: self.command_output_top_line +=1
                         return True
                    elif key == curses.KEY_PPAGE:
                        self.command_output_top_line = max(0, self.command_output_top_line - cmd_output_content_height_scroll)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.command_output_top_line = min(len(self.command_output_lines) - cmd_output_content_height_scroll if len(self.command_output_lines) > cmd_output_content_height_scroll else 0, self.command_output_top_line + cmd_output_content_height_scroll)
                        if self.command_output_top_line < 0 : self.command_output_top_line = 0
                        return True

            elif current_active_tab == "Snippets":
                snippets_total_available_height = (max_h - 3) - 4
                if snippets_total_available_height < 0: snippets_total_available_height = 0
                list_display_height_snip = snippets_total_available_height -1
                if self.snippet_status_message: list_display_height_snip -=1
                if list_display_height_snip < 0: list_display_height_snip = 0
                content_view_height_snip = snippets_total_available_height -1
                if self.snippet_status_message: content_view_height_snip -=1
                if content_view_height_snip < 0: content_view_height_snip = 0
                if self.snippet_tab_mode == "list":
                    if key == curses.KEY_UP:
                        if self.selected_snippet_index > 0:
                            self.selected_snippet_index -= 1
                            if self.selected_snippet_index < self.snippet_view_top_line: self.snippet_view_top_line = self.selected_snippet_index
                        self.delete_confirm_pending_id = None
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.selected_snippet_index < len(self.snippet_list) - 1:
                            self.selected_snippet_index += 1
                            if self.selected_snippet_index >= self.snippet_view_top_line + list_display_height_snip and list_display_height_snip > 0:
                                self.snippet_view_top_line = self.selected_snippet_index - list_display_height_snip + 1
                        self.delete_confirm_pending_id = None
                        return True
                if not (self.snippet_tab_mode == "list" and key == ord('d')) and \
                   not (self.snippet_tab_mode == "list" and key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE]):
                     self.delete_confirm_pending_id = None
                if self.snippet_tab_mode == "list":
                    if key == curses.KEY_ENTER or key == 10 or key == 13: # View Snippet
                        if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                            snippet_id = self.snippet_list[self.selected_snippet_index]['id']
                            try:
                                snippet = self.snippet_manager.get_snippet_by_id(snippet_id)
                                if snippet:
                                    self.active_snippet_content_lines = snippet.get('content', '').split('\n')
                                    self.snippet_content_scroll_top = 0; self.snippet_tab_mode = "view_content"
                                    self.logger.info(f"Viewing snippet ID: {snippet_id}, Name: {snippet.get('name')}")
                                else:
                                    self.snippet_status_message = "Error: Snippet not found."
                                    self.logger.warning(f"Attempted to view non-existent snippet ID: {snippet_id}")
                            except Exception as e_view_snip:
                                self.logger.exception(f"Error viewing snippet ID {snippet_id}: {e_view_snip}")
                                self.snippet_status_message = "Error viewing snippet. Check logs."
                        return True
                    elif key == ord('a'):
                        self.current_snippet_id_being_edited = None
                        self.snippet_form_data = {"name": "", "content": "", "language": "python", "category": "", "tags": ""}
                        self.snippet_form_active_field = "name"; self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                        self.snippet_tab_mode = "edit_form"; self.snippet_status_message = "Fill details and Save."
                        return True
                    elif key == ord('e'):
                        if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                            snippet_to_edit_id = self.snippet_list[self.selected_snippet_index]['id']
                            try:
                                data = self.snippet_manager.get_snippet_by_id(snippet_to_edit_id)
                                if data:
                                    self.current_snippet_id_being_edited = snippet_to_edit_id; self.snippet_form_data = data.copy()
                                    self.snippet_form_data['tags'] = ", ".join(data.get('tags', []))
                                    self.snippet_form_active_field = "name"; self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                                    self.snippet_tab_mode = "edit_form"; self.snippet_status_message = f"Editing: {data.get('name')}."
                                    self.logger.info(f"Editing snippet ID: {snippet_to_edit_id}, Name: {data.get('name')}")
                                else:
                                    self.snippet_status_message = "Error: Snippet not found for editing."
                                    self.logger.warning(f"Attempted to edit non-existent snippet ID: {snippet_to_edit_id}")
                            except Exception as e_edit_snip_load:
                                self.logger.exception(f"Error loading snippet {snippet_to_edit_id} for editing: {e_edit_snip_load}")
                                self.snippet_status_message = "Error loading snippet for edit. Check logs."
                        return True
                    elif key == ord('d'):
                        if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                            snippet_to_delete = self.snippet_list[self.selected_snippet_index]
                            snippet_id = snippet_to_delete['id']; snippet_name = snippet_to_delete.get('name', 'Unknown')
                            if self.delete_confirm_pending_id == snippet_id:
                                try:
                                    if self.snippet_manager.delete_snippet(snippet_id):
                                        self.snippet_list = self.snippet_manager.list_snippets()
                                        if self.selected_snippet_index >= len(self.snippet_list) and len(self.snippet_list) > 0:
                                            self.selected_snippet_index = len(self.snippet_list) - 1
                                        elif not self.snippet_list:
                                            self.selected_snippet_index = 0
                                        self.snippet_status_message = f"Snippet '{snippet_name}' deleted."
                                        self.logger.info(f"Deleted snippet ID: {snippet_id}, Name: {snippet_name}")
                                    else:
                                        self.snippet_status_message = f"Error deleting '{snippet_name}'."
                                        self.logger.error(f"Failed to delete snippet ID: {snippet_id}, Name: {snippet_name} (manager returned False)")
                                except Exception as e_del_snip:
                                    self.logger.exception(f"Error deleting snippet ID {snippet_id}: {e_del_snip}")
                                    self.snippet_status_message = f"Error deleting '{snippet_name}'. Check logs."
                                finally:
                                    self.delete_confirm_pending_id = None
                            else:
                                self.delete_confirm_pending_id = snippet_id
                                self.snippet_status_message = f"Press 'd' again to confirm deletion of '{snippet_name}'."
                        else: self.snippet_status_message = "No snippet selected to delete."
                        return True
                elif self.snippet_tab_mode == "view_content":
                    if key == ord('b'):
                        self.snippet_tab_mode = "list"; self.active_snippet_content_lines = []; self.snippet_status_message = "Returned to list."
                        return True
                    elif key == curses.KEY_UP:
                        if self.snippet_content_scroll_top > 0: self.snippet_content_scroll_top -= 1
                        return True
                    elif key == curses.KEY_DOWN:
                        if self.snippet_content_scroll_top < len(self.active_snippet_content_lines) - content_view_height_snip: self.snippet_content_scroll_top += 1
                        return True
                    elif key == curses.KEY_PPAGE:
                        self.snippet_content_scroll_top = max(0, self.snippet_content_scroll_top - content_view_height_snip)
                        return True
                    elif key == curses.KEY_NPAGE:
                        self.snippet_content_scroll_top = min(len(self.active_snippet_content_lines) - content_view_height_snip if len(self.active_snippet_content_lines) > content_view_height_snip else 0, self.snippet_content_scroll_top + content_view_height_snip)
                        if self.snippet_content_scroll_top < 0: self.snippet_content_scroll_top = 0
                        return True
                elif self.snippet_tab_mode == "edit_form":
                    form_fields_cycle = ["name", "language", "category", "tags", "content", "save", "cancel"]
                    def store_buffer_to_current_field_data():
                        if self.snippet_form_active_field not in ["save", "cancel"]: self.snippet_form_data[self.snippet_form_active_field] = self.snippet_form_input_buffer
                    def load_buffer_from_current_field_data():
                        if self.snippet_form_active_field not in ["save", "cancel"]: self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                        else: self.snippet_form_input_buffer = ""
                    current_field_idx = form_fields_cycle.index(self.snippet_form_active_field)
                    if key == curses.KEY_ESCAPE:
                        self.snippet_tab_mode = "list"; self.current_snippet_id_being_edited = None; self.snippet_form_data = {}; self.snippet_form_input_buffer = ""; self.snippet_status_message = "Cancelled."
                        return True
                    elif key == ord('\t'):
                        store_buffer_to_current_field_data()
                        next_idx = (current_field_idx + 1) % len(form_fields_cycle)
                        self.snippet_form_active_field = form_fields_cycle[next_idx]; load_buffer_from_current_field_data()
                        return True
                    elif key == curses.KEY_BTAB or key == 353:
                        store_buffer_to_current_field_data()
                        prev_idx = (current_field_idx - 1 + len(form_fields_cycle)) % len(form_fields_cycle)
                        self.snippet_form_active_field = form_fields_cycle[prev_idx]; load_buffer_from_current_field_data()
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        if self.snippet_form_active_field == "save":
                            store_buffer_to_current_field_data()
                            tags_list = [t.strip() for t in self.snippet_form_data.get("tags", "").split(',') if t.strip()]
                            form_payload = {k: self.snippet_form_data.get(k,"").strip() for k in ["name", "language", "category"]}
                            form_payload["content"] = self.snippet_form_data.get("content","")
                            form_payload["tags"] = tags_list
                            if not form_payload["name"] or not form_payload["content"]:
                                 self.snippet_status_message = "Error: Name and Content are required."
                                 return True
                            try:
                                if self.current_snippet_id_being_edited:
                                    updated = self.snippet_manager.update_snippet(self.current_snippet_id_being_edited, **form_payload)
                                    self.snippet_status_message = f"Snippet '{updated['name']}' updated." if updated else "Error updating snippet."
                                    self.logger.info(f"Updated snippet ID: {self.current_snippet_id_being_edited}, Name: {updated.get('name') if updated else 'N/A'}")
                                    if not updated: self.logger.error(f"Updating snippet {self.current_snippet_id_being_edited} returned False/None.")
                                else:
                                    new = self.snippet_manager.add_snippet(**form_payload)
                                    self.snippet_status_message = f"Snippet '{new['name']}' added." if new else "Error adding snippet."
                                    self.logger.info(f"Added new snippet, Name: {new.get('name') if new else 'N/A'}")
                                    if not new: self.logger.error("Adding new snippet returned False/None.")
                                self.snippet_list = self.snippet_manager.list_snippets()
                                self.snippet_tab_mode = "list"
                            except Exception as e_save_snip:
                                self.logger.exception(f"Error saving snippet (ID: {self.current_snippet_id_being_edited if self.current_snippet_id_being_edited else 'New'}): {e_save_snip}")
                                self.snippet_status_message = "Error saving snippet. Check logs."
                            finally:
                                self.current_snippet_id_being_edited = None; self.snippet_form_data = {}; self.snippet_form_input_buffer = ""
                            return True
                        elif self.snippet_form_active_field == "cancel":
                            self.snippet_tab_mode = "list"; self.current_snippet_id_being_edited = None; self.snippet_form_data = {}; self.snippet_form_input_buffer = ""; self.snippet_status_message = "Cancelled."
                            return True
                        elif self.snippet_form_active_field == "content":
                            self.snippet_form_input_buffer += "\n"
                            return True
                    elif self.snippet_form_active_field not in ["save", "cancel"]:
                        if key == curses.KEY_BACKSPACE or key == 127: self.snippet_form_input_buffer = self.snippet_form_input_buffer[:-1]
                        elif 32 <= key <= 126 : self.snippet_form_input_buffer += chr(key)
                        return True

            previous_tab = current_active_tab
            switched_tab = self.tab_manager.handle_input(key)

            if switched_tab:
                newly_selected_tab = self.tab_manager.get_current_tab()
                self.logger.debug(f"Switched tab from {previous_tab} to {newly_selected_tab}")
                if newly_selected_tab == "Main" and self.show_api_key_startup_message:
                    pass
                elif self.show_api_key_startup_message and newly_selected_tab != "Main":
                     self.show_api_key_startup_message = False

                if newly_selected_tab == "Commands" and previous_tab != "Commands":
                    self.command_status_message = "Fetching suggestions..."
                    self.is_fetching_suggestions = True
                    context_signals = self._get_context_signals()
                    def _on_tab_switch_suggestions_complete(suggestions_list, error_str):
                        self.is_fetching_suggestions = False
                        if error_str:
                            self.logger.error(f"Command suggestion fetch error on tab switch: {error_str}")
                            self.command_status_message = f"Suggestion error: {error_str}"
                            self.suggested_command_names = []
                        elif suggestions_list is not None:
                            self.suggested_command_names = suggestions_list
                            self.command_status_message = f"{len(self.suggested_command_names)} suggestions."
                        else:
                            self.command_status_message = "Failed to get suggestions (unknown error)."
                            self.suggested_command_names = []
                    self.chat_manager.request_command_suggestions(context_signals, _on_tab_switch_suggestions_complete)

                elif newly_selected_tab == "Snippets" and previous_tab != "Snippets":
                    try:
                        self.snippet_list = self.snippet_manager.list_snippets()
                        self.selected_snippet_index = 0; self.snippet_view_top_line = 0
                        self.snippet_status_message = f"{len(self.snippet_list)} snippets loaded."
                        self.logger.info(f"Loaded {len(self.snippet_list)} snippets for Snippets tab.")
                    except Exception as e_list_snip:
                        self.logger.exception(f"Error listing snippets on tab switch: {e_list_snip}")
                        self.snippet_list = []
                        self.snippet_status_message = "Error loading snippets. Check logs."

                if self.active_file_viewer and (newly_selected_tab != "Files" or self.file_tab_mode != "viewer"):
                    try:
                        self.active_file_viewer.close()
                    except Exception as e_close_viewer_tab_switch:
                        self.logger.exception(f"Error closing file viewer on tab switch: {e_close_viewer_tab_switch}")
                    self.active_file_viewer = None
                    if newly_selected_tab == "Files" and self.file_tab_mode == "viewer":
                         self.file_tab_mode = "tree"

                if newly_selected_tab == "Files" and self.file_tree is None and not self.is_file_tree_loading:
                    self._load_project_files()

                if newly_selected_tab == "Settings":
                    current_conf = load_config()
                    self.current_api_key_display = "Loaded (not shown)" if current_conf.get("openrouter_api_key") else "Not set"
                    self.settings_model_input_buffer = current_conf.get("mjw_model", ""); self.settings_api_key_input_buffer = ""; self.settings_status_message = ""
                return True
            
        except Exception as e:
            self.logger.exception(f"Error during input processing for key '{key}' in tab '{current_active_tab}':")
            return True

        return True

    def run_loop(self):
        running = True
        try:
            self.logger.info("TerminalUI run_loop starting.")
            while running:
                self.stdscr.erase()
                self._draw_title()
                self._draw_tabs()
                self._draw_main_content()
                self._draw_hint_bar()
                self.stdscr.refresh()
                running = self._handle_input()
                if not running:
                    self.logger.info("Exit signal received from _handle_input or q/Ctrl+C.")
                    break
        except Exception as e:
            self.logger.exception("Unhandled error in TerminalUI run_loop:")
        finally:
            self.logger.info("TerminalUI run_loop ended.")
            if self.active_file_viewer:
                try:
                    self.active_file_viewer.close()
                except Exception as e_final_close: # Catch error on final close
                    self.logger.exception(f"Error closing file viewer during final cleanup: {e_final_close}")
                self.active_file_viewer = None

    def add_file_to_context(self, filepath: str) -> str:
        # ... (content as before)
        if not self.context_manager: return f"Error: ContextManager not available for {os.path.basename(filepath)}."
        success = self.context_manager.add_file(filepath)
        message = self.context_manager.get_latest_error()
        if success: return f"Successfully added {os.path.basename(filepath)} to context."
        else: return message if message else f"Failed to add {os.path.basename(filepath)} to context."


    def get_current_context_for_chat(self):
        # ... (content as before)
        if self.context_manager and self.context_manager.context_files:
            return self.context_manager.get_context_string()
        return None

    def _draw_hint_bar(self):
        # ... (content as before)
        h, w = self.stdscr.getmaxyx()
        hint_bar_y = h - 2
        if hint_bar_y < 0 or hint_bar_y >= h : return

        try:
            current_attr = self.hint_bar_attr
            self.stdscr.attron(current_attr)
            self.stdscr.addstr(hint_bar_y, 0, " " * w)
            self.stdscr.attroff(current_attr)
        except curses.error:
            try:
                self.stdscr.addstr(hint_bar_y, 0, " " * w)
            except curses.error: return

        global_hints = "q:Quit | ←→:Tabs"
        tab_specific_hints = ""
        current_tab = self.tab_manager.get_current_tab()

        if current_tab == "Main":
            if self.show_api_key_startup_message:
                tab_specific_hints = "→:Settings to add API Key"
            elif self.chat_manager.is_diff_active:
                tab_specific_hints = "Scroll:↑/↓ | Cmds:Ctrl+P"
            else:
                tab_specific_hints = "Enter:Send | Hist:↑/↓ | Cmds:Ctrl+P"
        elif current_tab == "Files":
            if self.file_tab_mode == "tree":
                filter_hint = "Esc:Clr" if self.file_filter_input_mode else "/:Filter"
                search_hint = "s:Search" if (not self.search_init_error and not self.is_search_index_loading) else "s:Search(Wait)"
                reindex_hint = "Ctrl+R:ReIdx"
                tab_specific_hints = f"Enter:View|c:Ctx|a:Analyze|{filter_hint}|{search_hint}|{reindex_hint}"
            elif self.file_tab_mode == "viewer":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.file_tab_mode == "analyzer":
                tab_specific_hints = "b:Back | Scroll:↑/↓ | t:GenTests | r:Refactor"
            elif self.file_tab_mode == "test_viewer":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.file_tab_mode == "refactor_selection":
                tab_specific_hints = "Enter:Select | b:Back | Nav:↑/↓"
            elif self.file_tab_mode == "refactor_diff_view":
                tab_specific_hints = "a:Apply | c:Cancel"
            elif self.file_tab_mode == "search_input":
                tab_specific_hints = "Enter:Search | Esc:Cancel"
            elif self.file_tab_mode == "search_results":
                tab_specific_hints = "Enter:Open | Esc/s:NewSearch | Nav:↑/↓"
        elif current_tab == "Commands":
            if self.commands_view_mode == "list":
                tab_specific_hints = "Enter:Run | F5:Suggest | Nav:↑/↓"
            elif self.commands_view_mode == "output":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
        elif current_tab == "Snippets":
            if self.snippet_tab_mode == "list":
                tab_specific_hints = "Nav:↑/↓ | Enter:View|a:Add|e:Edit|d:Del"
            elif self.snippet_tab_mode == "view_content":
                tab_specific_hints = "b:Back | Scroll:↑/↓/PgUp/PgDn"
            elif self.snippet_tab_mode == "edit_form":
                tab_specific_hints = "Tab:NextField | Enter:Save/Action | Esc:Cancel"
        elif current_tab == "Settings":
            tab_specific_hints = "Enter:Save | Esc:Clear"

        final_hints_str = f"{global_hints} || {tab_specific_hints}"

        max_hint_len = w - 2
        if max_hint_len < 0: max_hint_len = 0

        if len(final_hints_str) > max_hint_len:
            overflow = len(final_hints_str) - max_hint_len
            if len(global_hints) < max_hint_len - 5:
                 available_for_tab_specific = max_hint_len - (len(global_hints) + 4)
                 if available_for_tab_specific < 3 : available_for_tab_specific = 3
                 if len(tab_specific_hints) > available_for_tab_specific :
                    tab_specific_hints = tab_specific_hints[:available_for_tab_specific-3] + "..."
                 final_hints_str = f"{global_hints} || {tab_specific_hints}"
            else:
                final_hints_str = final_hints_str[:max_hint_len-3] + "..."
            if len(final_hints_str) > max_hint_len:
                final_hints_str = final_hints_str[:max_hint_len]
        try:
            current_attr = self.hint_bar_attr
            self.stdscr.attron(current_attr)
            self.stdscr.addnstr(hint_bar_y, 1, final_hints_str, w - 2, current_attr)
            self.stdscr.attroff(current_attr)
        except curses.error:
            pass

def main_ui_runner(stdscr_outer, app_logger_param=None):
    if app_logger_param is None:
        app_logger_param = logging.getLogger("MasterJulesWalker_UI_Standalone")
        app_logger_param.setLevel(logging.DEBUG)
        if not app_logger_param.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            app_logger_param.addHandler(console_handler)
            app_logger_param.info("Running UI standalone, configured basic console logger.")

    ui = TerminalUI(stdscr_outer, app_logger_param)
    ui.run_loop()

if __name__ == "__main__":
    dev_logger = logging.getLogger("MasterJulesWalker_Dev_Entry")
    dev_logger.setLevel(logging.DEBUG)
    if not dev_logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'))
        dev_logger.addHandler(ch)

    dev_logger.info("Attempting to run TerminalUI directly (__name__ == '__main__').")
    try:
        curses.wrapper(main_ui_runner, dev_logger)
        dev_logger.info("TerminalUI exited gracefully (when run directly).")
    except Exception as e:
        dev_logger.exception("An error occurred when running UI directly:")
        print(f"An error occurred: {e}")
        print("Make sure your terminal supports curses and is large enough.")
