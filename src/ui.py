import curses
import os
import time
import difflib
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
    def __init__(self, stdscr):
        self.stdscr = stdscr
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
        self.highlight_attr = curses.color_pair(1)
        self.dir_attr = curses.color_pair(2)
        self.prompt_attr = curses.color_pair(3)
        self.normal_attr = curses.A_NORMAL

        self.file_tab_mode = "tree"
        self.project_root = "."
        self.file_tree: FileTree | None = None
        self.selected_tree_index = 0
        self.tree_top_line_index = 0
        self.active_file_viewer = None
        self.file_filter_input_mode: bool = False
        self.current_file_filter_term: str = ""
        self._load_project_files()

        self.context_manager = ContextManager(project_root=self.project_root)
        self.context_status_message = ""

        self.code_analyzer = CodeAnalyzer(project_root=self.project_root)
        self.active_analysis_report = None 
        self.analysis_display_lines = []   
        self.analysis_view_top_line = 0    
        self.selected_analysis_item_index = 0
        self.analysis_selectable_items = []
        self.is_generating_tests = False
        self.generated_test_code_lines = []
        self.test_viewer_top_line = 0

        self.chat_manager = ChatManager(config=app_config, ui_reference=self)
        self.command_runner = CommandRunner(project_root=self.project_root, chat_manager_ref=self.chat_manager)
        self.available_commands = self.command_runner.list_available_commands()
        self.selected_command_index = 0
        self.command_output_lines = []
        self.command_output_top_line = 0
        self.command_status_message = "" 
        self.commands_view_mode = "list"
        self.suggested_command_names = []
        self.is_fetching_suggestions = False

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
        self.is_loading_llm_response = False
        self.diff_display_lines = []
        self.diff_view_scroll_top_index = 0

        self.settings_api_key_input_buffer = ""
        loaded_api_key = app_config.get("openrouter_api_key")
        self.current_api_key_display = "Loaded from config (not shown)" if loaded_api_key else "Not set"
        self.settings_status_message = ""
        self.settings_model_input_buffer = app_config.get("mjw_model", "")

        self.refactor_code_item_details = None
        self.available_refactorings = [
            "Identify Anti-Patterns", "Suggest Optimizations", "Convert to List Comprehension",
            "Extract Variable", "Generate Docstring (Python)"
        ]
        self.selected_refactoring_index = 0
        self.refactor_diff_lines = []
        self.is_requesting_refactor = False
        self.original_code_snippet = ""
        self.refactored_code_suggestion = ""

        self.search_indexer = SemanticIndexer(project_root=self.project_root)
        self.search_init_error = self.search_indexer.initialization_error
        if not self.search_init_error:
            self.search_indexer.load_index()
        else:
            self.context_status_message = f"Search Indexer Error: {self.search_init_error}"

        self.search_query_input_buffer = ""
        self.original_search_query = ""
        self.search_results_list = []
        self.selected_search_result_index = 0
        self.search_results_top_line = 0
        self.search_status_message = ""

    def _get_context_signals(self):
        signals = {
            "current_tab": self.tab_manager.get_current_tab(),
            "context_files": self.context_manager.get_context_summary(),
            "available_commands": self.available_commands
        }
        chat_history = self.chat_manager.get_formatted_history()
        signals["recent_chat_history"] = chat_history[-5:]
        analysis_summary = "None"
        if self.active_analysis_report and "error" not in self.active_analysis_report:
            raw_summary = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
            max_len = 500
            analysis_summary = raw_summary[:max_len-3] + "..." if len(raw_summary) > max_len else raw_summary
        elif self.active_analysis_report and "error" in self.active_analysis_report:
            analysis_summary = f"Error in analysis: {self.active_analysis_report['error']}"
        signals["active_analysis"] = analysis_summary
        return signals

    def _load_project_files(self, path="."):
        self.project_root = os.path.abspath(path)
        raw_project_items = files.get_project_files(self.project_root)
        self.file_tree = FileTree(raw_project_items)
        self.selected_tree_index = 0
        self.tree_top_line_index = 0
        self.current_file_filter_term = ""
        if self.file_tree:
             self.file_tree.set_filter_term("")

    def _draw_title(self):
        title = "MasterJulesWalker"
        h, w = self.stdscr.getmaxyx()
        x = w // 2 - len(title) // 2
        y = 0 
        self.stdscr.addstr(y, x, title, curses.A_BOLD)

    def _draw_tabs(self):
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
        for y_line in range(content_y_start, h -1):
            try: self.stdscr.addstr(y_line, 1, " " * (w - 2))
            except curses.error: pass

    def _draw_main_content(self):
        h, w = self.stdscr.getmaxyx()
        content_y_start = 4
        input_line_y = h - 2
        self._clear_content_area(content_y_start, h, w)
        current_active_tab = self.tab_manager.get_current_tab()

        if current_active_tab == "Main":
            if self.chat_manager.is_diff_active:
                self.stdscr.addstr(content_y_start, 1, f"Reviewing suggestion for: {os.path.basename(self.chat_manager.active_diff_filepath)}", self.highlight_attr)
                diff_instructions = "Type 'accept_suggestion' or 'reject_suggestion' in command input (Ctrl+P then type command)."
                self.stdscr.addstr(content_y_start + 1, 1, diff_instructions[:w-2], self.normal_attr)
                if self.chat_manager.active_diff_original_content is not None and \
                   self.chat_manager.active_diff_suggested_content is not None:
                    self.diff_display_lines = generate_diff(
                        self.chat_manager.active_diff_original_content,
                        self.chat_manager.active_diff_suggested_content,
                        fromfile=os.path.basename(self.chat_manager.active_diff_filepath) + " (original)",
                        tofile=os.path.basename(self.chat_manager.active_diff_filepath) + " (suggested)"
                    )
                else: self.diff_display_lines = ["Error: Diff content not available."]
                diff_view_y_start = content_y_start + 3
                diff_view_height = input_line_y - diff_view_y_start
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
                        elif line_content.startswith('-'): attr = curses.A_BOLD
                        elif line_content.startswith('@@'): attr = curses.color_pair(2)
                        self.stdscr.addstr(diff_view_y_start + i, 1, line_content[:w-2], attr)
            else: # Normal Chat Mode
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
            if self.file_tab_mode == "tree":
                context_summary_list = self.context_manager.get_context_summary()
                num_summary_lines = len(context_summary_list)
                context_area_reserved_height = 1
                if num_summary_lines > 0: context_area_reserved_height += 1
                context_area_reserved_height += num_summary_lines
                tree_view_height = (h - content_y_start - 1) - context_area_reserved_height
                tree_view_height = max(3, tree_view_height)

                selected_item_tuple = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                selected_item_path_for_highlight = selected_item_tuple[0] if selected_item_tuple else None
                current_tree_display_tuples = self.file_tree.get_display_lines(selected_item_path_for_highlight) if self.file_tree else []

                if not current_tree_display_tuples:
                    filter_msg = f"Filter: {self.current_file_filter_term}" if self.current_file_filter_term else "No files found."
                    if content_y_start < h -1: self.stdscr.addstr(content_y_start, 2, filter_msg[:w-3])
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
                            if content_y_start + i < h -1:
                                self.stdscr.addstr(content_y_start + i, 1, line_to_draw, attr)
                        else: break
                context_draw_y_start = content_y_start + tree_view_height
                if num_summary_lines > 0:
                    if context_draw_y_start < h -1:
                        self.stdscr.addstr(context_draw_y_start, 1, "--- Context ('c' to add/remove selected) ---"[:w-2], self.highlight_attr)
                    context_draw_y_start += 1
                    for i, summary_line in enumerate(context_summary_list):
                        if context_draw_y_start + i < h -1: 
                             self.stdscr.addstr(context_draw_y_start + i, 1, summary_line[:w-2])
                info_line_y = content_y_start + tree_view_height + (1 if num_summary_lines > 0 else 0) + num_summary_lines
                if info_line_y < h -1 :
                    current_info_line_content = ""
                    if self.context_status_message:
                        current_info_line_content = self.context_status_message
                    else: 
                        ctx_size_kb = self.context_manager.current_context_size_bytes // 1024
                        num_ctx_files = len(self.context_manager.context_files)
                        max_num_files = ContextManager.MAX_CONTEXT_FILES
                        current_info_line_content = f"Ctx: {num_ctx_files}/{max_num_files} {ctx_size_kb}KB. Filter: '{self.current_file_filter_term}'"
                        if self.file_filter_input_mode:
                            current_info_line_content = f"Filter Input: {self.current_file_filter_term}"
                        elif self.search_init_error:
                            current_info_line_content = f"Search unavailable: {self.search_init_error}"
                    self.stdscr.addstr(info_line_y, 1, " " * (w - 2))
                    self.stdscr.addstr(info_line_y, 1, current_info_line_content[:w-2],
                                       self.highlight_attr if self.context_status_message or self.search_init_error or self.file_filter_input_mode else self.normal_attr)
                    if self.context_status_message == current_info_line_content:
                        self.context_status_message = ""
            elif self.file_tab_mode == "viewer" and self.active_file_viewer:
                viewer_display_height = h - content_y_start - 2 
                view_lines = self.active_file_viewer.get_display_lines(viewer_display_height)
                for i, line_content in enumerate(view_lines):
                    if i < viewer_display_height and (content_y_start + i < h -1 ) :
                        self.stdscr.addstr(content_y_start + i, 1, line_content[:w-2])
                    else: break
                back_hint = "[b] Back to tree"
                if content_y_start + viewer_display_height < h -1:
                     self.stdscr.addstr(content_y_start + viewer_display_height, 2, back_hint, self.highlight_attr)
            
            elif self.file_tab_mode == "analyzer":
                analyzer_view_height = h - content_y_start - 2
                if self.active_analysis_report and not self.analysis_selectable_items:
                    temp_selectable_items = []
                    def find_item_line_in_display(item_prefix, item_name, display_lines):
                        for idx, line_content in enumerate(display_lines):
                            if line_content.strip().startswith(item_prefix + " " + item_name): return idx
                        return -1
                    if 'classes' in self.active_analysis_report:
                        for i, class_info in enumerate(self.active_analysis_report['classes']):
                            line_idx = find_item_line_in_display("Class:", class_info['name'], self.analysis_display_lines)
                            if line_idx != -1: temp_selectable_items.append({'type': 'class', 'name': class_info['name'], 'report_idx': i, 'display_start_line': line_idx})
                    if 'functions' in self.active_analysis_report:
                        for i, func_info in enumerate(self.active_analysis_report['functions']):
                            line_idx = find_item_line_in_display("Function:", func_info['name'], self.analysis_display_lines)
                            if line_idx != -1: temp_selectable_items.append({'type': 'function', 'name': func_info['name'], 'report_idx': i, 'display_start_line': line_idx})
                    temp_selectable_items.sort(key=lambda x: x['display_start_line'])
                    self.analysis_selectable_items = temp_selectable_items
                if not self.analysis_display_lines:
                    if content_y_start < h -1: self.stdscr.addstr(content_y_start, 1, "No analysis report to display."[:w-2])
                else:
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
                    for i in range(analyzer_view_height):
                        current_display_line_idx = self.analysis_view_top_line + i
                        if current_display_line_idx < len(self.analysis_display_lines):
                            line_to_draw = self.analysis_display_lines[current_display_line_idx]
                            attr_to_use = self.normal_attr
                            if selected_item_display_start != -1 and selected_item_display_start <= current_display_line_idx < selected_item_display_end:
                                attr_to_use = self.highlight_attr
                            if content_y_start + i < h - 1: self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2], attr_to_use)
                        else: break
                analysis_hint_text = "[b] Back to Tree, [t] Gen Tests"
                if self.analysis_selectable_items: analysis_hint_text += ", [r] Refactor"
                if self.is_generating_tests:
                    loading_msg = "Generating tests, please wait..."
                    msg_y = content_y_start + analyzer_view_height // 2; msg_x = max(1, (w - len(loading_msg)) // 2)
                    if msg_y < h -1 : self.stdscr.addstr(msg_y, msg_x, loading_msg, self.highlight_attr)
                if content_y_start + analyzer_view_height < h -1:
                    self.stdscr.addstr(content_y_start + analyzer_view_height, 2, analysis_hint_text[:w-2], self.highlight_attr)
            elif self.file_tab_mode == "refactor_selection":
                title = f"Select Refactoring for {self.refactor_code_item_details['name']}:"
                self.stdscr.addstr(content_y_start, 1, title[:w-2], self.highlight_attr)
                list_y_start = content_y_start + 2
                for i, ref_op in enumerate(self.available_refactorings):
                    attr = self.highlight_attr if i == self.selected_refactoring_index else self.normal_attr
                    if list_y_start + i < h - 2: self.stdscr.addstr(list_y_start + i, 2, ref_op[:w-3], attr)
                hints = "[Enter] Confirm, [b] Back"; self.stdscr.addstr(h - 2, 2, hints[:w-3], self.highlight_attr)
            elif self.file_tab_mode == "refactor_diff_view":
                if self.is_requesting_refactor:
                    loading_msg = "Requesting refactor from LLM..."
                    self.stdscr.addstr(content_y_start + (h - content_y_start -1) // 2, max(1, (w - len(loading_msg))//2), loading_msg, self.highlight_attr)
                else:
                    self.stdscr.addstr(content_y_start, 1, "Refactoring Diff:"[:w-2], self.highlight_attr)
                    diff_view_height = h - content_y_start - 3
                    for i, line_content in enumerate(self.refactor_diff_lines):
                        if i >= diff_view_height: break
                        line_attr = self.normal_attr
                        if line_content.startswith('+'): line_attr = curses.color_pair(3)
                        elif line_content.startswith('-'): line_attr = curses.A_BOLD
                        elif line_content.startswith('@@'): line_attr = curses.color_pair(2)
                        if content_y_start + 1 + i < h -2: self.stdscr.addstr(content_y_start + 1 + i, 1, line_content.rstrip()[:w-2], line_attr)
                    hints = "[a] Apply, [c] Cancel/Back"; self.stdscr.addstr(h - 2, 2, hints[:w-3], self.highlight_attr)
            elif self.file_tab_mode == "test_viewer":
                test_viewer_height = h - content_y_start - 2
                if not self.generated_test_code_lines:
                    if content_y_start < h -1: self.stdscr.addstr(content_y_start, 1, "No test code to display."[:w-2])
                else:
                    if self.test_viewer_top_line < 0: self.test_viewer_top_line = 0
                    if len(self.generated_test_code_lines) > test_viewer_height:
                        self.test_viewer_top_line = min(self.test_viewer_top_line, len(self.generated_test_code_lines) - test_viewer_height)
                    else: self.test_viewer_top_line = 0
                    for i in range(test_viewer_height):
                        current_display_line_idx = self.test_viewer_top_line + i
                        if current_display_line_idx < len(self.generated_test_code_lines):
                            line_to_draw = self.generated_test_code_lines[current_display_line_idx]
                            if content_y_start + i < h - 1: self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else: break
                test_viewer_hint = "[b] Back to Analyzer"
                if content_y_start + test_viewer_height < h -1:
                    self.stdscr.addstr(content_y_start + test_viewer_height, 2, test_viewer_hint[:w-2], self.highlight_attr)
            elif self.file_tab_mode == "search_input":
                self._clear_content_area(content_y_start, h, w)
                prompt_text = f"Search Query ([Enter] Search, [Esc] Cancel): > {self.search_query_input_buffer}"
                self.stdscr.addstr(content_y_start, 1, prompt_text[:w-2])
            elif self.file_tab_mode == "search_results":
                self._clear_content_area(content_y_start, h, w)
                title = f"Search Results for '{self.original_search_query}' ({self.search_status_message})"
                self.stdscr.addstr(content_y_start, 1, title[:w-2], self.highlight_attr)
                results_display_height = h - content_y_start - 3
                if self.selected_search_result_index >= self.search_results_top_line + results_display_height:
                    self.search_results_top_line = self.selected_search_result_index - results_display_height + 1
                if self.selected_search_result_index < self.search_results_top_line: self.search_results_top_line = self.selected_search_result_index
                self.search_results_top_line = max(0, self.search_results_top_line)
                if len(self.search_results_list) > results_display_height:
                     self.search_results_top_line = min(self.search_results_top_line, len(self.search_results_list) - results_display_height)
                else: self.search_results_top_line = 0
                current_y = content_y_start + 2
                for i in range(results_display_height // 2):
                    idx_to_display = self.search_results_top_line + i
                    if idx_to_display < len(self.search_results_list):
                        if current_y + 1 >= h - 2: break
                        item = self.search_results_list[idx_to_display]
                        attr = self.highlight_attr if idx_to_display == self.selected_search_result_index else self.normal_attr
                        display_line = f"{item['file_path']} (L{item['start_line']}-{item['end_line']}) Score: {item['score']:.2f}"
                        self.stdscr.addstr(current_y, 2, display_line[:w-3], attr)
                        text_preview = item['text'].replace('\n', ' ').strip()
                        self.stdscr.addstr(current_y + 1, 4, text_preview[:w-5], attr)
                        current_y += 2
                    else: break
                hints = "[Enter] Open, [Esc] Back to Query, [s] New Search"
                if content_y_start + results_display_height +1 < h -1 :
                    self.stdscr.addstr(content_y_start + results_display_height + 1, 1, hints[:w-2])
        elif current_active_tab == "Commands":
            if self.commands_view_mode == "list":
                list_view_height = h - content_y_start - 2
                header_text = "Commands (Suggestions [*], F5 to refresh):"
                self.stdscr.addstr(content_y_start, 1, header_text[:w-2], self.highlight_attr)
                if self.is_fetching_suggestions:
                    loading_msg = "Fetching command suggestions..."
                    msg_y = content_y_start + 1
                    if msg_y < h - 2: self.stdscr.addstr(msg_y, 2, loading_msg[:w-3])
                else:
                    if self.selected_command_index < 0: self.selected_command_index = 0
                    if self.selected_command_index >= len(self.available_commands):
                        self.selected_command_index = max(0, len(self.available_commands) -1)
                    display_y = content_y_start + 1
                    for i, (name, desc) in enumerate(self.available_commands):
                        if display_y >= content_y_start + list_view_height -1: break
                        prefix = "[*] " if name in self.suggested_command_names else "    "
                        display_text = f"{prefix}{name}: {desc}"
                        attr = self.highlight_attr if i == self.selected_command_index else self.normal_attr
                        self.stdscr.addstr(display_y, 2, display_text[:w-3], attr)
                        display_y += 1
                status_line_y = content_y_start + list_view_height -1
                if self.command_status_message and status_line_y < h -1:
                     self.stdscr.addstr(status_line_y, 1, " " * (w-2))
                     self.stdscr.addstr(status_line_y, 1, self.command_status_message[:w-2], self.normal_attr)
            elif self.commands_view_mode == "output":
                output_view_height = h - content_y_start - 2
                if not self.command_output_lines:
                    if content_y_start < h -1: self.stdscr.addstr(content_y_start, 1, "No output to display."[:w-2])
                else:
                    if self.command_output_top_line < 0: self.command_output_top_line = 0
                    if len(self.command_output_lines) > output_view_height:
                        self.command_output_top_line = min(self.command_output_top_line, len(self.command_output_lines) - output_view_height)
                    else: self.command_output_top_line = 0
                    for i in range(output_view_height):
                        current_display_line_idx = self.command_output_top_line + i
                        if current_display_line_idx < len(self.command_output_lines):
                            line_to_draw = self.command_output_lines[current_display_line_idx]
                            if content_y_start + i < h -1 : self.stdscr.addstr(content_y_start + i, 1, line_to_draw[:w-2])
                        else: break
                output_hint = "[b] Back to Command List"
                if content_y_start + output_view_height < h -1:
                    self.stdscr.addstr(content_y_start + output_view_height, 2, output_hint[:w-2], self.highlight_attr)
        elif current_active_tab == "Snippets":
            snippets_content_height = h - content_y_start - 1
            if self.snippet_tab_mode == "list":
                self.stdscr.addstr(content_y_start, 1, "Snippets ([Enter] View, [a] Add, [d] Del):"[:w-2], self.highlight_attr)
                list_display_area_height = snippets_content_height - 2
                if not self.snippet_list:
                    if content_y_start + 1 < h - 2: self.stdscr.addstr(content_y_start + 1, 2, "No snippets found."[:w-3])
                else:
                    if self.selected_snippet_index < 0: self.selected_snippet_index = 0
                    if self.selected_snippet_index >= len(self.snippet_list): self.selected_snippet_index = max(0, len(self.snippet_list) -1)
                    if self.selected_snippet_index >= self.snippet_view_top_line + list_display_area_height:
                        self.snippet_view_top_line = self.selected_snippet_index - list_display_area_height + 1
                    if self.selected_snippet_index < self.snippet_view_top_line: self.snippet_view_top_line = self.selected_snippet_index
                    self.snippet_view_top_line = max(0, self.snippet_view_top_line)
                    if len(self.snippet_list) > list_display_area_height:
                        self.snippet_view_top_line = min(self.snippet_view_top_line, len(self.snippet_list) - list_display_area_height)
                    else: self.snippet_view_top_line = 0
                    display_y = content_y_start + 1
                    for i in range(list_display_area_height):
                        current_list_item_idx = self.snippet_view_top_line + i
                        if current_list_item_idx < len(self.snippet_list):
                            snippet = self.snippet_list[current_list_item_idx]
                            display_text = f"{snippet.get('name', 'Unnamed Snippet')} ({snippet.get('language', 'N/A')})"
                            attr = self.highlight_attr if current_list_item_idx == self.selected_snippet_index else self.normal_attr
                            if display_y < content_y_start + 1 + list_display_area_height : self.stdscr.addstr(display_y, 2, display_text[:w-3], attr)
                            display_y += 1
                        else: break
            elif self.snippet_tab_mode == "view_content":
                self.stdscr.addstr(content_y_start, 1, "Snippet Content ([b] Back to List):"[:w-2], self.highlight_attr)
                content_display_height = snippets_content_height - 2
                if not self.active_snippet_content_lines:
                     if content_y_start + 1 < h -2: self.stdscr.addstr(content_y_start + 1, 2, "No content to display."[:w-3])
                else:
                    if self.snippet_content_scroll_top < 0: self.snippet_content_scroll_top = 0
                    if len(self.active_snippet_content_lines) > content_display_height:
                        self.snippet_content_scroll_top = min(self.snippet_content_scroll_top, len(self.active_snippet_content_lines) - content_display_height)
                    else: self.snippet_content_scroll_top = 0
                    display_y = content_y_start + 1
                    for i in range(content_display_height):
                        line_idx = self.snippet_content_scroll_top + i
                        if line_idx < len(self.active_snippet_content_lines):
                            self.stdscr.addstr(display_y + i, 2, self.active_snippet_content_lines[line_idx][:w-3])
                        else: break
            elif self.snippet_tab_mode == "edit_form":
                form_y = content_y_start
                form_title = "Edit Snippet" if self.current_snippet_id_being_edited else "Add New Snippet"
                self.stdscr.addstr(form_y, 1, f"{form_title} ([Tab] Next, [Esc] Cancel):"[:w-2], self.highlight_attr); form_y += 1
                fields = ["name", "language", "category", "tags", "content", "save", "cancel"]
                def draw_field(label, value, y_pos, is_active):
                    attr = self.highlight_attr if is_active else self.normal_attr
                    self.stdscr.addstr(y_pos, 2, f"{label}: "[:w-3], self.normal_attr)
                    display_value = self.snippet_form_input_buffer if is_active else value
                    self.stdscr.addstr(y_pos, 2 + len(label) + 2, display_value[:w - (4 + len(label) + 2)], attr)
                for field_name in fields:
                    if form_y >= content_y_start + snippets_content_height -1 : break
                    is_active_field = (self.snippet_form_active_field == field_name)
                    if field_name not in ["content", "save", "cancel"]:
                        draw_field(field_name.capitalize(), self.snippet_form_data.get(field_name, ""), form_y, is_active_field); form_y += 1
                    elif field_name == "content":
                        self.stdscr.addstr(form_y, 2, "Content:"[:w-3], self.normal_attr)
                        content_attr = self.highlight_attr if is_active_field else self.normal_attr
                        content_value_to_display = self.snippet_form_input_buffer if is_active_field else self.snippet_form_data.get("content", "")
                        content_lines_to_show = content_value_to_display.split('\n')[:3]
                        for i, line_content in enumerate(content_lines_to_show):
                            if form_y + 1 + i >= content_y_start + snippets_content_height - 2: break
                            self.stdscr.addstr(form_y + 1 + i, 4, line_content[:w-5], content_attr)
                        form_y += (1 + min(3, len(content_lines_to_show)))
                    elif field_name in ["save", "cancel"]:
                        button_attr = self.highlight_attr if is_active_field else self.normal_attr
                        self.stdscr.addstr(form_y, 4, f"[{field_name.capitalize()}]"[:w-5], button_attr); form_y += 1
            status_line_y = content_y_start + snippets_content_height -1
            if status_line_y < h -1 :
                self.stdscr.addstr(status_line_y, 1, " " * (w-2))
                if self.snippet_status_message:
                    self.stdscr.addstr(status_line_y, 1, self.snippet_status_message[:w-2], self.normal_attr)
                    self.snippet_status_message = ""
        elif current_active_tab == "Settings":
            y_offset = content_y_start
            self.stdscr.addstr(y_offset, 2, f"Current API Key: {self.current_api_key_display}", self.normal_attr); y_offset += 2
            self.stdscr.addstr(y_offset, 2, "New OpenRouter API Key:", self.normal_attr)
            self.stdscr.addstr(y_offset + 1, 2, "> " + self.settings_api_key_input_buffer, self.prompt_attr); y_offset += 3
            self.stdscr.addstr(y_offset, 2, f"Model Name (current: {self.chat_manager.model_name}):", self.normal_attr)
            self.stdscr.addstr(y_offset + 1, 2, "> " + self.settings_model_input_buffer, self.prompt_attr); y_offset += 3
            self.stdscr.addstr(y_offset, 2, "Press Enter in a field to Save. Esc to clear field.", self.normal_attr); y_offset += 2
            if self.settings_status_message:
                self.stdscr.addstr(y_offset, 2, self.settings_status_message, self.highlight_attr)
                self.settings_status_message = ""
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
                else: self.settings_status_message = "No changes to save."
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
            # Tab switching is handled globally at the end

        elif current_active_tab == "Main":
            if self.chat_manager.is_diff_active:
                content_y_start = 4; input_line_y = max_h - 2
                diff_view_y_start = content_y_start + 3
                diff_view_height = input_line_y - diff_view_y_start
                num_diff_lines = len(self.diff_display_lines)
                if key == curses.KEY_UP:
                    if self.diff_view_scroll_top_index > 0: self.diff_view_scroll_top_index -=1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.diff_view_scroll_top_index < num_diff_lines - diff_view_height:
                        self.diff_view_scroll_top_index += 1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.diff_view_scroll_top_index = max(0, self.diff_view_scroll_top_index - diff_view_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.diff_view_scroll_top_index = min(num_diff_lines - diff_view_height if num_diff_lines > diff_view_height else 0, self.diff_view_scroll_top_index + diff_view_height)
                    if self.diff_view_scroll_top_index < 0: self.diff_view_scroll_top_index = 0
                    return True
                # Allow tab switching even in diff mode - handled globally
                # Other inputs are ignored if diff is active (commands via Ctrl+P)
                # return True # Consume other keys, but allow tab switch to be processed

            else: # Normal Chat Mode
                chat_display_height = (max_h - 2) - 4
                num_history_lines = len(self.chat_manager.get_formatted_history())
                if self.is_loading_llm_response:
                    if self.tab_manager.handle_input(key): return True # Allow tab switch
                    return True # Ignore other inputs while loading
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
                    self.chat_scroll_top_index = min(num_history_lines - chat_display_height if num_history_lines > chat_display_height else 0, self.chat_scroll_top_index + chat_display_height)
                    if self.chat_scroll_top_index < 0 : self.chat_scroll_top_index =0
                    return True
                elif key == curses.KEY_ENTER or key == 10 or key == 13: 
                    if self.chat_input_buffer.strip():
                        self.is_loading_llm_response = True; self.stdscr.erase(); self._draw_title(); self._draw_tabs(); self._draw_main_content(); self.stdscr.refresh()
                        self.chat_manager.send_message(self.chat_input_buffer.strip())
                        self.chat_input_buffer = ""; self.is_loading_llm_response = False
                        num_history_lines_after = len(self.chat_manager.get_formatted_history())
                        if num_history_lines_after > chat_display_height: self.chat_scroll_top_index = num_history_lines_after - chat_display_height
                        else: self.chat_scroll_top_index = 0
                    return True
                elif key == curses.KEY_BACKSPACE or key == 127: self.chat_input_buffer = self.chat_input_buffer[:-1]; return True
                elif 32 <= key <= 126: self.chat_input_buffer += chr(key); return True

        elif current_active_tab == "Files":
            content_area_height = max_h - 4 -1
            if self.file_tab_mode == "tree":
                if self.file_filter_input_mode:
                    if key == curses.KEY_ESCAPE:
                        self.file_filter_input_mode = False
                        if self.current_file_filter_term:
                            self.current_file_filter_term = ""
                            if self.file_tree: self.file_tree.set_filter_term("")
                            self.selected_tree_index = 0
                            self.tree_top_line_index = 0
                        self.context_status_message = "Filter cleared."
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        self.file_filter_input_mode = False
                        self.context_status_message = f"Filter active: '{self.current_file_filter_term}'" if self.current_file_filter_term else "Filter cleared."
                        if self.file_tree and self.selected_tree_index >= self.file_tree.get_filtered_items_count() and self.file_tree.get_filtered_items_count() > 0:
                            self.selected_tree_index = self.file_tree.get_filtered_items_count() - 1
                        elif self.file_tree and self.file_tree.get_filtered_items_count() == 0:
                             self.selected_tree_index = 0
                        return True
                    elif key == curses.KEY_BACKSPACE or key == 127:
                        if self.current_file_filter_term:
                            self.current_file_filter_term = self.current_file_filter_term[:-1]
                            if self.file_tree: self.file_tree.set_filter_term(self.current_file_filter_term)
                            self.selected_tree_index = 0
                            self.tree_top_line_index = 0
                        return True
                    elif 32 <= key <= 126:
                        self.current_file_filter_term += chr(key)
                        if self.file_tree: self.file_tree.set_filter_term(self.current_file_filter_term)
                        self.selected_tree_index = 0
                        self.tree_top_line_index = 0
                        return True
                    # Allow tab switching even in filter input mode - handled globally
                    return True # Consume other keys
                else: # Normal tree navigation
                    if key == curses.KEY_UP:
                        if self.selected_tree_index > 0:
                            self.selected_tree_index -= 1
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
                                abs_item_path = os.path.join(self.project_root, item_path_rel)
                                if abs_item_path in self.context_manager.context_files:
                                    self.context_manager.remove_file(item_path_rel)
                                    self.context_status_message = self.context_manager.get_latest_error() or f"Removed {os.path.basename(item_path_rel)}"
                                else:
                                    self.context_manager.add_file(item_path_rel)
                                    self.context_status_message = self.context_manager.get_latest_error() or f"Added {os.path.basename(item_path_rel)}"
                            else: self.context_status_message = "Cannot add directories to context."
                        return True
                    elif key == ord('a'):
                        selected_item = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                        if selected_item:
                            item_path_rel, item_type = selected_item
                            if item_type == "file" and item_path_rel.endswith(".py"):
                                self.active_analysis_report = self.code_analyzer.analyze_file(item_path_rel)
                                if self.active_analysis_report and "error" not in self.active_analysis_report:
                                    formatted_analysis = self.code_analyzer.format_analysis_for_llm(self.active_analysis_report)
                                    self.analysis_display_lines = formatted_analysis.split('\n')
                                    self.file_tab_mode = "analyzer"; self.analysis_view_top_line = 0; self.selected_analysis_item_index = 0; self.analysis_selectable_items = []
                                    self.context_status_message = f"Analyzed: {os.path.basename(item_path_rel)}"
                                else: self.context_status_message = self.active_analysis_report.get("error", "Analysis failed.")
                            else: self.context_status_message = "Select a Python file to analyze."
                        return True
                    elif key == curses.KEY_ENTER or key == 10 or key == 13:
                        selected_item = self.file_tree.get_item_by_index(self.selected_tree_index) if self.file_tree else None
                        if selected_item:
                            item_path_rel, item_type = selected_item
                            if item_type == "file":
                                if self.active_file_viewer: self.active_file_viewer.close()
                                self.file_tab_mode = "viewer"; self.active_file_viewer = viewer.FileViewer(os.path.join(self.project_root, item_path_rel))
                        return True
                    elif key == ord('/'):
                        if self.chat_manager.is_diff_active:
                            self.context_status_message = "Cannot filter while diff review is active."
                            return True
                        self.file_filter_input_mode = True
                        self.context_status_message = "Enter filter term (Esc: clear/exit, Enter: apply & exit)."
                        return True
                    elif key == 18: # CTRL_R for Re-index
                        if self.search_init_error: self.context_status_message = f"Search Indexer not ready: {self.search_init_error}"
                        else:
                            self.context_status_message = "Building search index..."; self.stdscr.refresh()
                            all_master_items = self.file_tree.project_items_master if self.file_tree else []
                            project_filepaths = [item[0] for item in all_master_items if item[1] == 'file']
                            self.search_indexer.build_index(project_filepaths)
                            load_success = self.search_indexer.load_index()
                            self.context_status_message = "Search index rebuilt." if load_success else "Index rebuilt, load failed."
                        return True

            elif self.file_tab_mode == "viewer" and self.active_file_viewer: # Viewer Mode
                if key == ord('b'):
                    self.active_file_viewer.close(); self.active_file_viewer = None
                    self.file_tab_mode = "tree"; self.context_status_message = "Closed viewer."
                    return True
                if self.active_file_viewer.handle_input(key, content_area_height): return True
            
            elif self.file_tab_mode == "analyzer": # Analyzer mode inputs
                if key == ord('b'):
                    self.file_tab_mode = "tree"; self.analysis_display_lines = []; self.active_analysis_report = None
                    self.analysis_selectable_items = []; self.selected_analysis_item_index = 0
                    self.context_status_message = "Closed analyzer."
                    return True
                analyzer_content_height = max_h - 4 - 2
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
                elif key == ord('t'): # Generate tests
                    if self.analysis_selectable_items and 0 <= self.selected_analysis_item_index < len(self.analysis_selectable_items):
                        selected_item = self.analysis_selectable_items[self.selected_analysis_item_index]
                        item_name = selected_item['name']; item_type = selected_item['type']
                        self.is_generating_tests = True; self.context_status_message = f"Generating tests for {item_type} '{item_name}'..."; self.stdscr.refresh()
                        generated_content = self.chat_manager.request_test_generation(item_name, item_type)
                        self.is_generating_tests = False; self.generated_test_code_lines = generated_content.split('\n')
                        self.file_tab_mode = "test_viewer"; self.test_viewer_top_line = 0
                        self.context_status_message = f"Tests for {item_name} ready." if not generated_content.startswith("# Error") else f"Test gen error: {self.generated_test_code_lines[0]}"
                    else: self.context_status_message = "No item selected."
                    return True
                elif key == ord('r'): # Refactor
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
            elif self.file_tab_mode == "refactor_selection": # Refactor operation selection
                if key == curses.KEY_UP:
                    if self.selected_refactoring_index > 0: self.selected_refactoring_index -= 1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.selected_refactoring_index < len(self.available_refactorings) - 1: self.selected_refactoring_index += 1
                    return True
                elif key == ord('b') or key == curses.KEY_ESCAPE:
                    self.file_tab_mode = "analyzer"; self.context_status_message = "Refactoring cancelled."
                    return True
                elif key == curses.KEY_ENTER or key == 10 or key == 13: # Confirm refactoring operation
                    selected_op = self.available_refactorings[self.selected_refactoring_index]
                    self.is_requesting_refactor = True; self.file_tab_mode = "refactor_diff_view"; self.stdscr.erase(); self._draw_title(); self._draw_tabs(); self._draw_main_content(); self.stdscr.refresh()
                    self.refactored_code_suggestion = self.chat_manager.request_refactor(self.original_code_snippet, selected_op)
                    self.is_requesting_refactor = False
                    if not self.refactored_code_suggestion or self.refactored_code_suggestion.startswith("# Error:"):
                        self.context_status_message = self.refactored_code_suggestion or "LLM failed."
                        self.file_tab_mode = "refactor_selection"; self.refactor_diff_lines = []
                    else:
                        self.refactor_diff_lines = list(difflib.unified_diff(self.original_code_snippet.splitlines(keepends=True), self.refactored_code_suggestion.splitlines(keepends=True), fromfile='original', tofile='refactored', lineterm=''))
                        self.context_status_message = "Suggestion received. Review diff."
                    return True
            elif self.file_tab_mode == "refactor_diff_view": # Diff view for refactoring
                if key == ord('c') or key == ord('b') or key == curses.KEY_ESCAPE:
                    self.file_tab_mode = "refactor_selection"; self.refactor_diff_lines = []; self.context_status_message = "Refactoring cancelled."
                    return True
                elif key == ord('a'): # Apply refactoring
                    if self.refactor_code_item_details and self.refactored_code_suggestion:
                        filepath_rel = self.refactor_code_item_details['filepath']; start_line = self.refactor_code_item_details['start_line']; end_line = self.refactor_code_item_details['end_line']
                        abs_filepath = os.path.join(self.project_root, filepath_rel)
                        try:
                            with open(abs_filepath, 'r', encoding='utf-8') as f: file_lines = f.readlines()
                            new_code_lines = self.refactored_code_suggestion.splitlines(keepends=True)
                            if new_code_lines and not self.refactored_code_suggestion.endswith('\n'): new_code_lines[-1] += '\n'
                            if not new_code_lines and self.refactored_code_suggestion: new_code_lines = ['\n']
                            prefix = file_lines[:start_line - 1]; suffix = file_lines[end_line:]
                            with open(abs_filepath, 'w', encoding='utf-8') as f: f.writelines(prefix + new_code_lines + suffix)
                            self.context_status_message = f"Refactoring applied to {os.path.basename(filepath_rel)}."
                            self.active_analysis_report = None; self.analysis_display_lines = []
                        except Exception as e: self.context_status_message = f"Error applying: {str(e)}"
                        finally: self.file_tab_mode = "analyzer"; self.refactor_code_item_details = None; self.original_code_snippet = ""; self.refactored_code_suggestion = ""; self.refactor_diff_lines = []; self.selected_refactoring_index = 0
                    else:
                        self.context_status_message = "Error: Missing details for apply."; self.file_tab_mode = "analyzer"
                        self.refactor_code_item_details = None; self.original_code_snippet = ""; self.refactored_code_suggestion = ""; self.refactor_diff_lines = []; self.selected_refactoring_index = 0
                    return True
            elif self.file_tab_mode == "search_input": # Semantic search input
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
                    self.search_status_message = "Searching..."; self.file_tab_mode = "search_results"; self.stdscr.refresh()
                    search_response = self.search_indexer.search(query, top_n=20)
                    if search_response.get("error"): self.search_status_message = search_response["error"]; self.search_results_list = []
                    else:
                        self.search_results_list = search_response["results"]
                        self.search_status_message = f"{len(self.search_results_list)} results." if self.search_results_list else "No results found."
                    self.selected_search_result_index = 0; self.search_results_top_line = 0
                    return True
            elif self.file_tab_mode == "search_results": # Semantic search results
                results_display_area_height = max_h - 4 - 3; items_per_page = results_display_area_height // 2
                if key == curses.KEY_UP:
                    if self.selected_search_result_index > 0:
                        self.selected_search_result_index -= 1
                        if self.selected_search_result_index < self.search_results_top_line: self.search_results_top_line = self.selected_search_result_index
                    return True
                elif key == curses.KEY_DOWN:
                    if self.selected_search_result_index < len(self.search_results_list) - 1:
                        self.selected_search_result_index += 1
                        if self.selected_search_result_index >= self.search_results_top_line + items_per_page: self.search_results_top_line = self.selected_search_result_index - items_per_page + 1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.selected_search_result_index = max(0, self.selected_search_result_index - items_per_page)
                    self.search_results_top_line = max(0, self.search_results_top_line - items_per_page)
                    if self.selected_search_result_index < self.search_results_top_line : self.search_results_top_line = self.selected_search_result_index
                    return True
                elif key == curses.KEY_NPAGE:
                    self.selected_search_result_index = min(len(self.search_results_list) - 1, self.selected_search_result_index + items_per_page)
                    if len(self.search_results_list) > items_per_page: self.search_results_top_line = min(len(self.search_results_list) - items_per_page, self.search_results_top_line + items_per_page)
                    if self.selected_search_result_index >= self.search_results_top_line + items_per_page: self.search_results_top_line = self.selected_search_result_index - items_per_page + 1
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
                            h_dim, w_dim = self.stdscr.getmaxyx(); content_y = 4
                            viewer_disp_height = h_dim - content_y - 2
                            self.active_file_viewer.scroll_to_line(line_to_scroll_to, viewer_disp_height)
                            self.file_tab_mode = "viewer"
                            self.context_status_message = f"Opened {filepath_rel} at line {line_to_scroll_to}."
                        else: self.search_status_message = f"Error: File {filepath_rel} not found."; self.context_status_message = self.search_status_message
                    return True
            elif self.file_tab_mode == "test_viewer": # Test viewer mode
                test_viewer_content_height = max_h - 4 - 2
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
                        self.command_status_message = f"Running {command_name}..."; self.command_output_lines = [self.command_status_message]; self.commands_view_mode = "output"; self.stdscr.refresh()
                        # Note: If command needs args, this needs to change.
                        # For now, assuming commands run by selected_command_index don't take args from user directly here.
                        # For commands like 'semantic_search' or 'review_code_suggestion' that take args,
                        # they are typically invoked via the chat window's command parsing (Ctrl+P), not this list.
                        # This list is more for parameter-less commands or those with fixed/no args.
                        # If a command from this list *does* need args, it should probably prompt or handle it.
                        # For now, passing None for args_str.
                        success, output, error_str = self.command_runner.run_command(command_name, args_str=None)
                        if success:
                            self.command_output_lines = output.split('\n') if output else ["Command ran successfully with no output."]
                            self.command_status_message = f"'{command_name}' finished."
                        else:
                            self.command_output_lines = (error_str.split('\n') if error_str else [f"Command '{command_name}' failed."])
                            self.command_status_message = f"Error running '{command_name}'."
                        self.command_output_top_line = 0
                    return True
                elif key == curses.KEY_F5:
                    self.command_status_message = "Refreshing suggestions..."; self.is_fetching_suggestions = True; self.stdscr.refresh()
                    context_signals = self._get_context_signals()
                    self.suggested_command_names = self.chat_manager.request_command_suggestions(context_signals)
                    self.is_fetching_suggestions = False
                    self.command_status_message = f"{len(self.suggested_command_names)} suggestions." if self.suggested_command_names else "No suggestions or error."
                    return True
            elif self.commands_view_mode == "output":
                if key == ord('b'):
                    self.commands_view_mode = "list"; self.command_output_lines = []; self.command_status_message = "Returned to command list."
                    return True
                cmd_output_content_height = max_h - 4 - 2
                if key == curses.KEY_UP:
                    if self.command_output_top_line > 0: self.command_output_top_line -=1
                    return True
                elif key == curses.KEY_DOWN:
                     if self.command_output_top_line < len(self.command_output_lines) - cmd_output_content_height: self.command_output_top_line +=1
                     return True
                elif key == curses.KEY_PPAGE:
                    self.command_output_top_line = max(0, self.command_output_top_line - cmd_output_content_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.command_output_top_line = min(len(self.command_output_lines) - cmd_output_content_height if len(self.command_output_lines) > cmd_output_content_height else 0, self.command_output_top_line + cmd_output_content_height)
                    if self.command_output_top_line < 0 : self.command_output_top_line = 0
                    return True

        elif current_active_tab == "Snippets":
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
                        list_display_area_height = (max_h - 4 - 2) - 1
                        if self.selected_snippet_index >= self.snippet_view_top_line + list_display_area_height: self.snippet_view_top_line = self.selected_snippet_index - list_display_area_height + 1
                    self.delete_confirm_pending_id = None
                    return True
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
                            self.snippet_content_scroll_top = 0; self.snippet_tab_mode = "view_content"
                            self.snippet_status_message = f"Viewing: {snippet.get('name')}"
                        else: self.snippet_status_message = "Error: Snippet not found."
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
                        data = self.snippet_manager.get_snippet_by_id(snippet_to_edit_id)
                        if data:
                            self.current_snippet_id_being_edited = snippet_to_edit_id; self.snippet_form_data = data.copy()
                            self.snippet_form_data['tags'] = ", ".join(data.get('tags', []))
                            self.snippet_form_active_field = "name"; self.snippet_form_input_buffer = self.snippet_form_data.get(self.snippet_form_active_field, "")
                            self.snippet_tab_mode = "edit_form"; self.snippet_status_message = f"Editing: {data.get('name')}."
                        else: self.snippet_status_message = "Error: Snippet not found for editing."
                    return True
                elif key == ord('d'):
                    if self.snippet_list and 0 <= self.selected_snippet_index < len(self.snippet_list):
                        snippet_to_delete = self.snippet_list[self.selected_snippet_index]
                        snippet_id = snippet_to_delete['id']; snippet_name = snippet_to_delete.get('name', 'Unknown')
                        if self.delete_confirm_pending_id == snippet_id:
                            if self.snippet_manager.delete_snippet(snippet_id):
                                self.snippet_list = self.snippet_manager.list_snippets()
                                if self.selected_snippet_index >= len(self.snippet_list) and len(self.snippet_list) > 0: self.selected_snippet_index = len(self.snippet_list) - 1
                                elif not self.snippet_list: self.selected_snippet_index = 0
                                self.snippet_status_message = f"Snippet '{snippet_name}' deleted."
                            else: self.snippet_status_message = f"Error deleting '{snippet_name}'."
                            self.delete_confirm_pending_id = None
                        else:
                            self.delete_confirm_pending_id = snippet_id
                            self.snippet_status_message = f"Press 'd' again to confirm deletion of '{snippet_name}'."
                    else: self.snippet_status_message = "No snippet selected to delete."
                    return True
            elif self.snippet_tab_mode == "view_content":
                content_view_height = max_h - 4 - 2 -1
                if key == ord('b'):
                    self.snippet_tab_mode = "list"; self.active_snippet_content_lines = []; self.snippet_status_message = "Returned to list."
                    return True
                elif key == curses.KEY_UP:
                    if self.snippet_content_scroll_top > 0: self.snippet_content_scroll_top -= 1
                    return True
                elif key == curses.KEY_DOWN:
                    if self.snippet_content_scroll_top < len(self.active_snippet_content_lines) - content_view_height: self.snippet_content_scroll_top += 1
                    return True
                elif key == curses.KEY_PPAGE:
                    self.snippet_content_scroll_top = max(0, self.snippet_content_scroll_top - content_view_height)
                    return True
                elif key == curses.KEY_NPAGE:
                    self.snippet_content_scroll_top = min(len(self.active_snippet_content_lines) - content_view_height if len(self.active_snippet_content_lines) > content_view_height else 0, self.snippet_content_scroll_top + content_view_height)
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
                        if self.current_snippet_id_being_edited:
                            updated = self.snippet_manager.update_snippet(self.current_snippet_id_being_edited, **form_payload)
                            self.snippet_status_message = f"Snippet '{updated['name']}' updated." if updated else "Error updating."
                        else:
                            new = self.snippet_manager.add_snippet(**form_payload)
                            self.snippet_status_message = f"Snippet '{new['name']}' added." if new else "Error adding."
                        self.snippet_list = self.snippet_manager.list_snippets(); self.snippet_tab_mode = "list"; self.current_snippet_id_being_edited = None; self.snippet_form_data = {}; self.snippet_form_input_buffer = ""
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
            if newly_selected_tab == "Commands" and previous_tab != "Commands":
                self.command_status_message = "Fetching suggestions..."; self.is_fetching_suggestions = True; self.stdscr.refresh()
                context_signals = self._get_context_signals()
                self.suggested_command_names = self.chat_manager.request_command_suggestions(context_signals)
                self.is_fetching_suggestions = False
                self.command_status_message = f"{len(self.suggested_command_names)} suggestions." if self.suggested_command_names else "No suggestions or error."
            elif newly_selected_tab == "Snippets" and previous_tab != "Snippets":
                self.snippet_list = self.snippet_manager.list_snippets(); self.selected_snippet_index = 0; self.snippet_view_top_line = 0
                self.snippet_status_message = f"{len(self.snippet_list)} snippets loaded."
            if self.active_file_viewer and (newly_selected_tab != "Files" or self.file_tab_mode != "viewer"):
                self.active_file_viewer.close(); self.active_file_viewer = None
                if newly_selected_tab == "Files" and self.file_tab_mode == "viewer": self.file_tab_mode = "tree"
            if newly_selected_tab == "Files" and not self.file_tree:
                self._load_project_files()
            if newly_selected_tab == "Settings":
                current_conf = load_config()
                self.current_api_key_display = "Loaded (not shown)" if current_conf.get("openrouter_api_key") else "Not set"
                self.settings_model_input_buffer = current_conf.get("mjw_model", ""); self.settings_api_key_input_buffer = ""; self.settings_status_message = ""
            return True
            
        return True

    def run_loop(self):
        running = True
        try:
            while running:
                self.stdscr.erase()
                self._draw_title()
                self._draw_tabs()
                self._draw_main_content()
                self.stdscr.refresh()
                running = self._handle_input()
                if not running: break
        finally:
            if self.active_file_viewer:
                self.active_file_viewer.close()
                self.active_file_viewer = None

    def add_file_to_context(self, filepath: str) -> str:
        if not self.context_manager: return f"Error: ContextManager not available for {os.path.basename(filepath)}."
        success = self.context_manager.add_file(filepath)
        message = self.context_manager.get_latest_error()
        if success: return f"Successfully added {os.path.basename(filepath)} to context."
        else: return message if message else f"Failed to add {os.path.basename(filepath)} to context."

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
