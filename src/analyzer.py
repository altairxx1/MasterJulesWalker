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

    def get_code_element_source(self, relative_filepath, element_name, element_type):
        """
        Extracts the source code of a specific function or class from a Python file.

        Args:
            relative_filepath (str): Path to the Python file relative to project_root.
            element_name (str): The name of the function or class.
            element_type (str): "function" or "class".

        Returns:
            dict: {"source_code": str, "start_line": int, "end_line": int}
                  or {"error": str} if not found or an error occurs.
                  Line numbers are 1-indexed.
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
                # Try ast.get_source_segment (Python 3.8+)
                if hasattr(ast, 'get_source_segment'):
                    segment = ast.get_source_segment(source_code_full, node_to_find)
                    if segment:
                         # ast.unparse might add extra newlines for some nodes, so segment is better.
                         # To get accurate line numbers, we count lines in the segment and use node.lineno.
                        num_lines = len(segment.splitlines())
                        return {
                            "source_code": segment,
                            "start_line": node_to_find.lineno,
                            "end_line": node_to_find.lineno + num_lines -1
                        }

                # Fallback: manual extraction using line numbers if get_source_segment is not available or fails
                start_line = node_to_find.lineno
                end_line = getattr(node_to_find, 'end_lineno', None)

                if start_line and end_line:
                    source_lines = source_code_full.splitlines(keepends=True)
                    # Adjust to 0-indexed for slicing, then extract
                    extracted_lines = source_lines[start_line - 1 : end_line]
                    return {
                        "source_code": "".join(extracted_lines),
                        "start_line": start_line,
                        "end_line": end_line
                    }
                else: # Fallback if end_lineno is not available
                    source_lines = source_code_full.splitlines(keepends=True)
                    extracted_code = ""
                    # Iterate from the starting line of the node
                    # This is a basic heuristic and might grab too much or too little
                    # if there are nested structures or complex layouts.
                    # It also doesn't perfectly handle decorators if they are not part of node.lineno span.

                    # Try to get all lines from the start of the node until the start of the next node or EOF
                    # This is a common way to handle this when full parsing of end lines is not available

                    # Get all top-level nodes to find where the next one starts
                    relevant_nodes_in_body = []
                    parent_body = tree.body # Default to module level

                    # Find the parent body of the current node_to_find
                    for parent_node in ast.walk(tree):
                        if hasattr(parent_node, 'body') and isinstance(parent_node.body, list) and node_to_find in parent_node.body:
                            parent_body = parent_node.body
                            break
                        # Handle classes where methods are in class.body
                        if isinstance(parent_node, ast.ClassDef) and node_to_find in parent_node.body:
                            parent_body = parent_node.body
                            break

                    node_index = -1
                    for i, n in enumerate(parent_body):
                        if n == node_to_find:
                            node_index = i
                            break

                    next_node_start_line = len(source_lines) + 1 # Default to end of file
                    if node_index != -1 and node_index + 1 < len(parent_body):
                        next_node_start_line = parent_body[node_index+1].lineno

                    # Extract lines from start_line up to the line before next_node_start_line
                    # or up to the end of the file if it's the last element.
                    # Ensure we don't try to read beyond the file if next_node_start_line is beyond current scope

                    # Corrected logic for line extraction
                    # node.lineno is 1-indexed
                    # We need to extract from source_lines[node.lineno-1] up to source_lines[next_node_start_line-2]
                    # or up to the end if it's the last element.

                    end_extraction_line = next_node_start_line -1
                    if node_to_find.name == "async_function": # DEBUG
                        pass


                    # If node_to_find is the last element in its body, its end is the end_lineno of its parent or EOF
                    # This part is tricky without end_lineno on the node itself.
                    # A simpler heuristic: read until indentation decreases or EOF (for non-nested)
                    # However, ast.get_source_segment is the primary method. This is a rough fallback.

                    # Let's refine the fallback to be simpler: just read based on lineno and hope for the best
                    # as detailed block extraction without end_lineno is complex and error-prone.
                    # The most robust fallback if end_lineno is None is to just return the line it starts on,
                    # or accept that ast.get_source_segment is required for full accuracy.
                    # Given the constraints, we'll rely on ast.get_source_segment mostly.
                    # The existing start_line/end_line logic with getattr is probably the best we can do for a fallback.
                    # If end_lineno is None from getattr, it will trigger the error below.
                    return {"error": f"Could not reliably determine end line for {element_name} in {relative_filepath} for manual extraction. Python 3.8+ with ast.get_source_segment is recommended."}


            except Exception as e:
                return {"error": f"Error extracting source for {element_name}: {str(e)}"}
        else:
            return {"error": f"{element_type.capitalize()} '{element_name}' not found in {relative_filepath}."}


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

# Simulating decorators for testing source extraction
def decorator_example(func_or_class):
    # In a real scenario, this would modify func_or_class or return a wrapper
    return func_or_class

@decorator_example
class MyClass:
    \"\"\"A simple class for testing.\"\"\"
    CLASS_VAR = 100

    def __init__(self, value):
        self.value = value

    @decorator_example
    def get_value(self):
        \"\"\"Returns the value.\"\"\"
        return self.value

    def another_method(self):
        pass

@decorator_example
def top_level_function(x, y):
    \"\"\"A top-level function.\"\"\"
    z = x + y
    return z

async def async_function(): # Async functions are also ast.FunctionDef or ast.AsyncFunctionDef
    \"\"\"An async function example.\"\"\"
    await asyncio.sleep(0)

@decorator_example
class DecoratedClass:
    \"\"\"A class with a decorator.\"\"\"
    @classmethod
    def cm(cls):
        pass
"""
    # Need asyncio for the async function example if we were to run it, but for parsing it's fine
    # import asyncio
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

    print("\n\n--- Testing get_code_element_source ---")
    sm_path = os.path.join("src", "simple_module.py") # relative path for analyzer

    analyzer_for_source = CodeAnalyzer(project_root=test_analyzer_project_root) # Analyzer needs project root

    print("\nExtracting 'MyClass':")
    class_src = analyzer_for_source.get_code_element_source(sm_path, "MyClass", "class")
    if "error" in class_src:
        print(f"Error: {class_src['error']}")
    else:
        print(f"Source (lines {class_src['start_line']}-{class_src['end_line']}):\n{class_src['source_code']}")
        assert "class MyClass:" in class_src['source_code']
        assert "@decorator_example" in class_src['source_code'] # ast.get_source_segment should include decorators
        assert "CLASS_VAR = 100" in class_src['source_code']
        assert "def __init__(self, value):" in class_src['source_code']
        assert "def another_method(self):" in class_src['source_code']


    print("\nExtracting 'top_level_function':")
    func_src = analyzer_for_source.get_code_element_source(sm_path, "top_level_function", "function")
    if "error" in func_src:
        print(f"Error: {func_src['error']}")
    else:
        print(f"Source (lines {func_src['start_line']}-{func_src['end_line']}):\n{func_src['source_code']}")
        assert "@decorator_example" in func_src['source_code'] # Decorators included
        assert "def top_level_function(x, y):" in func_src['source_code']
        assert "z = x + y" in func_src['source_code']
        assert func_src['start_line'] > 0

    print("\nExtracting 'get_value' (method within MyClass):")
    # Note: For methods, element_name is just the method name, element_type is "function"
    method_src = analyzer_for_source.get_code_element_source(sm_path, "get_value", "function")
    if "error" in method_src:
        print(f"Error: {method_src['error']}")
    else:
        print(f"Source (lines {method_src['start_line']}-{method_src['end_line']}):\n{method_src['source_code']}")
        assert "@decorator_example" in method_src['source_code'] # Decorator for method
        assert "def get_value(self):" in method_src['source_code']

    print("\nExtracting 'async_function':")
    async_func_src = analyzer_for_source.get_code_element_source(sm_path, "async_function", "function")
    if "error" in async_func_src:
        print(f"Error: {async_func_src['error']}")
    else:
        print(f"Source (lines {async_func_src['start_line']}-{async_func_src['end_line']}):\n{async_func_src['source_code']}")
        assert "async def async_function():" in async_func_src['source_code']
        assert '"""An async function example."""' in async_func_src['source_code']

    print("\nExtracting 'DecoratedClass':")
    decorated_class_src = analyzer_for_source.get_code_element_source(sm_path, "DecoratedClass", "class")
    if "error" in decorated_class_src:
        print(f"Error: {decorated_class_src['error']}")
    else:
        print(f"Source (lines {decorated_class_src['start_line']}-{decorated_class_src['end_line']}):\n{decorated_class_src['source_code']}")
        assert "@decorator_example" in decorated_class_src['source_code']
        assert "class DecoratedClass:" in decorated_class_src['source_code']
        assert "@classmethod" in decorated_class_src['source_code']


    print("\nExtracting non-existent function 'no_such_func':")
    no_func_src = analyzer_for_source.get_code_element_source(sm_path, "no_such_func", "function")
    print(no_func_src)
    assert "error" in no_func_src and "not found" in no_func_src["error"]

    print("\nExtracting from non-existent file:")
    err_file_src = analyzer_for_source.get_code_element_source("bad_path.py", "some_func", "function")
    print(err_file_src)
    assert "error" in err_file_src and "File not found" in err_file_src["error"]

    print("\nExtracting from non-Python file:")
    err_file_src_2 = analyzer_for_source.get_code_element_source("not_python.txt", "some_func", "function")
    print(err_file_src_2)
    assert "error" in err_file_src_2 and "Not a Python file" in err_file_src_2["error"]


    # Clean up dummy project
    print("\nCleaning up test_analyzer_project...")
    try:
        import shutil
        shutil.rmtree(test_analyzer_project_root)
        print(f"Removed {test_analyzer_project_root}")
    except Exception as e:
        print(f"Error cleaning up: {e}")

    print("\nCodeAnalyzer test finished.")
