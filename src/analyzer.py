import ast
import os

class CodeAnalyzer:
    def __init__(self, project_root="."):
        self.project_root = os.path.abspath(project_root)

    def analyze_file(self, relative_filepath):
        """
        Performs a basic analysis of a Python file, extracting an overview,
        classes, functions, and global variables/constants.

        Args:
            relative_filepath (str): Path to the Python file relative to project_root.

        Returns:
            dict: An analysis report for the file, or None if analysis fails.
                  Report format:
                  {
                      "filepath": relative_filepath,
                      "overview": "File docstring or basic summary.",
                      "classes": [{"name": "ClassName", "methods": ["method1", ...], "docstring": "..."}, ...],
                      "functions": [{"name": "func_name", "args": ["arg1", ...], "docstring": "..."}, ...],
                      "globals": [{"name": "VAR_NAME", "type": "variable|constant"}, ...]
                  }
        """
        absolute_filepath = os.path.join(self.project_root, relative_filepath)

        if not os.path.isfile(absolute_filepath):
            # This should ideally not be reached if called from UI that lists valid files
            return {"filepath": relative_filepath, "error": "File not found."}
        
        if not relative_filepath.endswith(".py"):
            return {"filepath": relative_filepath, "error": "Not a Python file."}

        try:
            with open(absolute_filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
            tree = ast.parse(source_code, filename=relative_filepath)
        except Exception as e:
            return {"filepath": relative_filepath, "error": f"Error parsing file: {str(e)}"}

        analysis = {
            "filepath": relative_filepath,
            "overview": ast.get_docstring(tree) or "No file-level docstring.",
            "classes": [],
            "functions": [],
            "globals": []
        }

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "methods": [],
                    "docstring": ast.get_docstring(node) or "No class docstring."
                }
                for item in node.body:
                    if isinstance(item, ast.FunctionDef): # Includes methods, staticmethods, classmethods
                        class_info["methods"].append(item.name)
                analysis["classes"].append(class_info)
            
            elif isinstance(node, ast.FunctionDef):
                analysis["functions"].append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node) or "No function docstring."
                })
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Basic heuristic for constants: all uppercase
                        var_type = "constant" if target.id.isupper() else "variable"
                        analysis["globals"].append({"name": target.id, "type": var_type})
            
            elif isinstance(node, ast.AnnAssign): # Annotated assignment e.g. VAR: int = 10
                 if isinstance(node.target, ast.Name):
                    var_type = "constant" if node.target.id.isupper() else "variable"
                    analysis["globals"].append({"name": node.target.id, "type": var_type})


        return analysis

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
                    lines.append(f"    Docstring: {c_info['docstring'][:100]}...") # Truncate long docstrings
                if c_info['methods']:
                    lines.append(f"    Methods: {', '.join(c_info['methods'])}")
        
        if analysis_report['functions']:
            lines.append("\nFunctions:")
            for f_info in analysis_report['functions']:
                args_str = ", ".join(f_info['args'])
                lines.append(f"  - Function: {f_info['name']}({args_str})")
                if f_info['docstring'] and f_info['docstring'] != "No function docstring.":
                     lines.append(f"    Docstring: {f_info['docstring'][:100]}...") # Truncate
        
        if analysis_report['globals']:
            lines.append("\nGlobal Variables/Constants:")
            for g_info in analysis_report['globals']:
                lines.append(f"  - {g_info['name']} ({g_info['type']})")
        
        return "\n".join(lines)

if __name__ == '__main__':
    print("Testing CodeAnalyzer...")
    # Create dummy project structure for testing
    test_analyzer_project_root = "test_analyzer_project"
    src_path = os.path.join(test_analyzer_project_root, "src")
    os.makedirs(src_path, exist_ok=True)

    # Dummy file 1: simple_module.py
    simple_module_content = """
\"\"\"This is a simple test module.
It demonstrates basic analysis capabilities.
\"\"\"

GLOBAL_CONSTANT = "TestValue"
another_global = [1, 2, 3]

class MyClass:
    \"\"\"A simple class for testing.\"\"\"
    def __init__(self, value):
        self.value = value

    def get_value(self):
        \"\"\"Returns the value.\"\"\"
        return self.value

def top_level_function(x, y):
    \"\"\"A top-level function.\"\"\"
    return x + y

async def async_function():
    pass # Supported by ast.FunctionDef
"""
    with open(os.path.join(src_path, "simple_module.py"), "w", encoding='utf-8') as f:
        f.write(simple_module_content)

    # Dummy file 2: another_module.py (no docstrings)
    another_module_content = """
MY_VAR: int = 100

def func_no_doc(a, b, c):
    return a + b + c

class Another:
    pass
"""
    with open(os.path.join(src_path, "another_module.py"), "w", encoding='utf-8') as f:
        f.write(another_module_content)
        
    # Dummy file 3: not_python.txt
    with open(os.path.join(test_analyzer_project_root, "not_python.txt"), "w", encoding='utf-8') as f:
        f.write("This is not a python file.")


    analyzer = CodeAnalyzer(project_root=test_analyzer_project_root)

    print("\n--- Analyzing simple_module.py ---")
    report1 = analyzer.analyze_file(os.path.join("src", "simple_module.py"))
    if "error" in report1:
        print(f"Error: {report1['error']}")
    else:
        print("Raw Analysis Report:")
        # print(report1) # Can be verbose
        print(f"  Filepath: {report1['filepath']}")
        print(f"  Overview: {report1['overview']}")
        print(f"  Classes: {len(report1['classes'])}")
        for c in report1['classes']: print(f"    - {c['name']}")
        print(f"  Functions: {len(report1['functions'])}")
        for f in report1['functions']: print(f"    - {f['name']}")
        print(f"  Globals: {len(report1['globals'])}")
        for g in report1['globals']: print(f"    - {g['name']} ({g['type']})")

        print("\nFormatted for LLM:")
        print(analyzer.format_analysis_for_llm(report1))

    print("\n--- Analyzing another_module.py ---")
    report2 = analyzer.analyze_file(os.path.join("src", "another_module.py"))
    if "error" in report2:
        print(f"Error: {report2['error']}")
    else:
        print("Formatted for LLM:")
        print(analyzer.format_analysis_for_llm(report2))
        
    print("\n--- Analyzing not_python.txt ---")
    report3 = analyzer.analyze_file("not_python.txt")
    print("Formatted for LLM (should be error):")
    print(analyzer.format_analysis_for_llm(report3))
    
    print("\n--- Analyzing non_existent_file.py ---")
    report4 = analyzer.analyze_file("non_existent_file.py")
    print("Formatted for LLM (should be error):")
    print(analyzer.format_analysis_for_llm(report4))


    # Clean up dummy project
    print("\nCleaning up test_analyzer_project...")
    try:
        import shutil
        shutil.rmtree(test_analyzer_project_root)
        print(f"Removed {test_analyzer_project_root}")
    except Exception as e:
        print(f"Error cleaning up: {e}")

    print("\nCodeAnalyzer test finished.")
