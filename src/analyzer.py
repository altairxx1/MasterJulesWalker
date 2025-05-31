import ast
import os
import threading

class CodeAnalyzer:
    def __init__(self, project_root="."):
        self.project_root = os.path.abspath(project_root)

    def analyze_file(self, relative_filepath, callback):
        """
        Performs a basic analysis of a Python file in a background thread,
        extracting an overview, classes, functions, and global variables/constants.

        Args:
            relative_filepath (str): Path to the Python file relative to project_root.
            callback (function): Function to call with the analysis result.
                                 The callback will receive one argument: the report dictionary.
                                 This dictionary will contain an "error" key if analysis failed.
        """
        thread = threading.Thread(
            target=self._analyze_work,
            args=(relative_filepath, callback),
            daemon=True
        )
        thread.start()

    def _analyze_work(self, relative_filepath, callback):
        """Worker function for file analysis."""
        absolute_filepath = os.path.join(self.project_root, relative_filepath)
        report = {"filepath": relative_filepath} # Initialize report with filepath

        if not os.path.isfile(absolute_filepath):
            report["error"] = "File not found."
            if callback: callback(report)
            return
        
        if not relative_filepath.endswith(".py"):
            report["error"] = "Not a Python file."
            if callback: callback(report)
            return

        try:
            with open(absolute_filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
            tree = ast.parse(source_code, filename=relative_filepath)
        except Exception as e:
            report["error"] = f"Error parsing file: {str(e)}"
            if callback: callback(report)
            return

        report.update({
            "overview": ast.get_docstring(tree) or "No file-level docstring.",
            "classes": [],
            "functions": [],
            "globals": []
        })

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "methods": [],
                    "docstring": ast.get_docstring(node) or "No class docstring."
                }
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_info["methods"].append(item.name)
                report["classes"].append(class_info)
            
            elif isinstance(node, ast.FunctionDef):
                report["functions"].append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node) or "No function docstring."
                })
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_type = "constant" if target.id.isupper() else "variable"
                        report["globals"].append({"name": target.id, "type": var_type})
            
            elif isinstance(node, ast.AnnAssign):
                 if isinstance(node.target, ast.Name):
                    var_type = "constant" if node.target.id.isupper() else "variable"
                    report["globals"].append({"name": node.target.id, "type": var_type})

        if callback: callback(report)

    def format_analysis_for_llm(self, analysis_report):
        """
        Formats the analysis report into a string suitable for an LLM prompt.
        """
        if not analysis_report or "error" in analysis_report:
            return f"Could not analyze file {analysis_report.get('filepath', 'unknown')}. Error: {analysis_report.get('error', 'Unknown error')}"

        filepath = analysis_report['filepath']
        lines = [f"Analysis of: {filepath}"]
        lines.append(f"Overview: {analysis_report['overview']}")

        if analysis_report['classes']:
            lines.append("\nClasses:")
            for c_info in analysis_report['classes']:
                lines.append(f"  - Class: {c_info['name']}")
                if c_info['docstring'] and c_info['docstring'] != "No class docstring.":
                    lines.append(f"    Docstring: {c_info['docstring'][:100]}...")
                if c_info['methods']:
                    lines.append(f"    Methods: {', '.join(c_info['methods'])}")
        
        if analysis_report['functions']:
            lines.append("\nFunctions:")
            for f_info in analysis_report['functions']:
                args_str = ", ".join(f_info['args'])
                lines.append(f"  - Function: {f_info['name']}({args_str})")
                if f_info['docstring'] and f_info['docstring'] != "No function docstring.":
                     lines.append(f"    Docstring: {f_info['docstring'][:100]}...")
        
        if analysis_report['globals']:
            lines.append("\nGlobal Variables/Constants:")
            for g_info in analysis_report['globals']:
                lines.append(f"  - {g_info['name']} ({g_info['type']})")
        
        return "\n".join(lines)

    def get_code_element_source(self, relative_filepath, element_name, element_type):
        """
        Extracts the source code of a specific function or class from a Python file.
        """
        absolute_filepath = os.path.join(self.project_root, relative_filepath)

        if not os.path.isfile(absolute_filepath):
            return {"error": f"File not found: {relative_filepath}"}

        if not relative_filepath.endswith(".py"):
            return {"error": "Not a Python file."}

        try:
            with open(absolute_filepath, 'r', encoding='utf-8') as f:
                source_code_full = f.read()
            tree = ast.parse(source_code_full, filename=relative_filepath)
        except Exception as e:
            return {"error": f"Error parsing file {relative_filepath}: {str(e)}"}

        node_to_find = None
        for node in ast.walk(tree):
            if element_type == "function" and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == element_name:
                node_to_find = node
                break
            elif element_type == "class" and isinstance(node, ast.ClassDef) and node.name == element_name:
                node_to_find = node
                break

        if node_to_find:
            try:
                if hasattr(ast, 'get_source_segment'):
                    segment = ast.get_source_segment(source_code_full, node_to_find)
                    if segment:
                        num_lines = len(segment.splitlines())
                        return {
                            "source_code": segment,
                            "start_line": node_to_find.lineno,
                            "end_line": node_to_find.lineno + num_lines -1
                        }

                start_line = node_to_find.lineno
                end_line = getattr(node_to_find, 'end_lineno', None)

                if start_line and end_line:
                    source_lines = source_code_full.splitlines(keepends=True)
                    extracted_lines = source_lines[start_line - 1 : end_line]
                    return {
                        "source_code": "".join(extracted_lines),
                        "start_line": start_line,
                        "end_line": end_line
                    }
                else:
                    return {"error": f"Could not reliably determine end line for {element_name} in {relative_filepath} for manual extraction. Python 3.8+ with ast.get_source_segment is recommended."}
            except Exception as e:
                return {"error": f"Error extracting source for {element_name}: {str(e)}"}
        else:
            return {"error": f"{element_type.capitalize()} '{element_name}' not found in {relative_filepath}."}


if __name__ == '__main__':
    # Test requires creating dummy files and then cleaning them up.
    # This is a simplified version for brevity.
    print("Testing CodeAnalyzer (async)...")
    
    # Dummy callback for testing
    def test_callback(report):
        print(f"\n--- Analysis Report (via callback) for: {report.get('filepath')} ---")
        if "error" in report:
            print(f"Error: {report['error']}")
        else:
            print(f"  Overview: {report.get('overview','N/A')[:50]}...")
            print(f"  Classes: {len(report.get('classes',[]))}")
            print(f"  Functions: {len(report.get('functions',[]))}")
            print(f"  Globals: {len(report.get('globals',[]))}")

    # Create a dummy project root and file for testing
    test_project_root = "temp_analyzer_test_project"
    if not os.path.exists(test_project_root):
        os.makedirs(test_project_root)

    dummy_py_file = os.path.join(test_project_root, "dummy_module.py")
    with open(dummy_py_file, "w") as f:
        f.write("def hello():\n    print('world')\n\nclass MyTest:\n    pass\n")

    analyzer = CodeAnalyzer(project_root=test_project_root)

    print("Requesting analysis for dummy_module.py...")
    analyzer.analyze_file("dummy_module.py", test_callback)

    print("Requesting analysis for non_existent.py...")
    analyzer.analyze_file("non_existent.py", test_callback)

    # Allow some time for threads to complete for testing output
    import time
    time.sleep(0.1)

    # Clean up
    if os.path.exists(dummy_py_file):
        os.remove(dummy_py_file)
    if os.path.exists(test_project_root):
        try:
            os.rmdir(test_project_root) # Only if empty
        except OSError: # If not empty (e.g. due to other test artifacts)
            import shutil
            shutil.rmtree(test_project_root, ignore_errors=True)

    print("\nCodeAnalyzer async test finished.")
