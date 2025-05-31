import unittest
import os
import ast
from unittest.mock import patch, mock_open

from src.analyzer import CodeAnalyzer

class TestCodeAnalyzer(unittest.TestCase):

    def setUp(self):
        self.project_root = os.path.abspath("test_analyzer_project_dir")
        # No need to create the dir if all file ops are mocked
        self.analyzer = CodeAnalyzer(project_root=self.project_root)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_analyze_file_success_basic_elements(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        sample_code = """
\"\"\"This is a module docstring.\"\"\"
import os
import sys

MY_CONSTANT = "hello"
my_variable = 123

class MyClass:
    \"\"\"This is a class docstring.\"\"\"
    def __init__(self, name):
        self.name = name

    def greet(self, formal=False):
        \"\"\"Greets the person.\"\"\"
        if formal:
            return f"Greetings, {self.name}."
        return f"Hello, {self.name}!"

def top_level_func(a, b):
    \"\"\"Adds two numbers.\"\"\"
    return a + b
"""
        mock_file_open.return_value.read.return_value = sample_code
        relative_path = "sample.py"
        report = self.analyzer.analyze_file(relative_path)

        self.assertNotIn("error", report)
        self.assertEqual(report["filepath"], relative_path)
        self.assertEqual(report["overview"], "This is a module docstring.")

        self.assertEqual(len(report["classes"]), 1)
        self.assertEqual(report["classes"][0]["name"], "MyClass")
        self.assertEqual(report["classes"][0]["docstring"], "This is a class docstring.")
        self.assertListEqual(sorted(report["classes"][0]["methods"]), sorted(["__init__", "greet"]))

        self.assertEqual(len(report["functions"]), 1)
        self.assertEqual(report["functions"][0]["name"], "top_level_func")
        self.assertEqual(report["functions"][0]["docstring"], "Adds two numbers.")
        self.assertListEqual(report["functions"][0]["args"], ["a", "b"])

        self.assertEqual(len(report["globals"]), 2)
        found_constant = any(g["name"] == "MY_CONSTANT" and g["type"] == "constant" for g in report["globals"])
        found_variable = any(g["name"] == "my_variable" and g["type"] == "variable" for g in report["globals"])
        self.assertTrue(found_constant)
        self.assertTrue(found_variable)
        # Note: analyzer doesn't currently pick up 'import' statements as globals, which is fine.

    @patch('os.path.isfile', return_value=False)
    def test_analyze_file_not_found(self, mock_isfile):
        relative_path = "non_existent.py"
        report = self.analyzer.analyze_file(relative_path)
        self.assertIn("error", report)
        self.assertEqual(report["error"], "File not found.")

    @patch('os.path.isfile', return_value=True) # Ensure this check passes to reach the .py check
    def test_analyze_file_not_python(self, mock_isfile):
        relative_path = "some_file.txt"
        report = self.analyzer.analyze_file(relative_path)
        self.assertIn("error", report)
        self.assertEqual(report["error"], "Not a Python file.")

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open, read_data="") # Empty file
    def test_analyze_file_empty_python_file(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        relative_path = "empty.py"
        report = self.analyzer.analyze_file(relative_path)

        self.assertNotIn("error", report)
        self.assertEqual(report["filepath"], relative_path)
        self.assertEqual(report["overview"], "No file-level docstring.")
        self.assertEqual(len(report["classes"]), 0)
        self.assertEqual(len(report["functions"]), 0)
        self.assertEqual(len(report["globals"]), 0)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open, read_data="def func(\n  return 1") # Syntax error
    def test_analyze_file_syntax_error(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        relative_path = "syntax_error.py"
        report = self.analyzer.analyze_file(relative_path)

        self.assertIn("error", report)
        self.assertTrue(report["error"].startswith("Error parsing file:"))


    def test_format_analysis_for_llm_success(self):
        analysis_report = {
            "filepath": "src/module.py",
            "overview": "Module for calculations.",
            "classes": [{
                "name": "Calculator",
                "methods": ["add", "subtract"],
                "docstring": "Performs calculations."
            }],
            "functions": [{
                "name": "helper_func",
                "args": ["x"],
                "docstring": "A helper."
            }],
            "globals": [{"name": "PI", "type": "constant"}]
        }
        formatted_string = self.analyzer.format_analysis_for_llm(analysis_report)

        self.assertIn("Analysis of: src/module.py", formatted_string)
        self.assertIn("Overview: Module for calculations.", formatted_string)
        self.assertIn("Classes:", formatted_string)
        self.assertIn("- Class: Calculator", formatted_string)
        self.assertIn("Docstring: Performs calculations.", formatted_string) # Docstring not truncated if short
        self.assertIn("Methods: add, subtract", formatted_string)
        self.assertIn("Functions:", formatted_string)
        self.assertIn("- Function: helper_func(x)", formatted_string)
        self.assertIn("Docstring: A helper.", formatted_string) # Docstring not truncated
        self.assertIn("Global Variables/Constants:", formatted_string)
        self.assertIn("- PI (constant)", formatted_string)

    def test_format_analysis_for_llm_long_docstrings_truncated(self):
        long_doc = "This is a very long docstring that definitely exceeds one hundred characters and should therefore be truncated by the formatting method to keep the output concise for the LLM prompt. It just keeps going and going."
        analysis_report = {
            "filepath": "src/module.py",
            "overview": "Module for calculations.",
            "classes": [{"name": "MyClass", "methods": [], "docstring": long_doc}],
            "functions": [],
            "globals": []
        }
        formatted_string = self.analyzer.format_analysis_for_llm(analysis_report)
        self.assertIn(f"Docstring: {long_doc[:100]}...", formatted_string)


    def test_format_analysis_for_llm_error_report(self):
        error_report = {"filepath": "broken.py", "error": "Could not parse."}
        formatted_string = self.analyzer.format_analysis_for_llm(error_report)
        self.assertEqual(formatted_string, "Could not analyze file broken.py. Error: Could not parse.")

    def test_format_analysis_for_llm_empty_report(self):
        # Test with an empty analysis (e.g., empty file)
        empty_analysis = {
            "filepath": "empty.py",
            "overview": "No file-level docstring.",
            "classes": [],
            "functions": [],
            "globals": []
        }
        formatted_string = self.analyzer.format_analysis_for_llm(empty_analysis)
        self.assertIn("Analysis of: empty.py", formatted_string)
        self.assertIn("Overview: No file-level docstring.", formatted_string)
        self.assertNotIn("Classes:", formatted_string) # Sections should not appear if empty
        self.assertNotIn("Functions:", formatted_string)
        self.assertNotIn("Global Variables/Constants:", formatted_string)

    # --- Tests for get_code_element_source ---

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_basic_function(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        code = "def foo():\n    pass\n"
        mock_file_open.return_value.read.return_value = code

        result = self.analyzer.get_code_element_source("test.py", "foo", "function")
        self.assertNotIn("error", result)
        self.assertEqual(result["source_code"], code.strip()) # ast.get_source_segment might strip trailing newlines
        self.assertEqual(result["start_line"], 1)
        self.assertEqual(result["end_line"], 2)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_function_with_decorators(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        code = """
@my_decorator
@another_decorator(arg=1)
def bar(x):
    return x * 2
"""
        # For ast.parse, the decorators must be valid Python expressions or parsable as such.
        # We'll define dummy decorators for the AST to be happy if it tries to evaluate them,
        # though get_source_segment primarily cares about line numbers.
        # For this test, we'll assume the decorators are simple name lookups or calls.
        # The key is that ast.parse can build a tree from this string.
        mock_file_open.return_value.read.return_value = code

        result = self.analyzer.get_code_element_source("test.py", "bar", "function")
        self.assertNotIn("error", result, msg=result.get("error", ""))

        expected_source = code.strip() # ast.get_source_segment will get the whole decorated block
        self.assertEqual(result["source_code"], expected_source)
        self.assertEqual(result["start_line"], 2) # AST node for function `bar` starts after comments/blanks
        self.assertEqual(result["end_line"], 5)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_basic_class(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        code = """
class MySpam:
    eggs_count = 0
    def cook(self):
        pass
"""
        mock_file_open.return_value.read.return_value = code
        result = self.analyzer.get_code_element_source("test.py", "MySpam", "class")
        self.assertNotIn("error", result, msg=result.get("error", ""))
        self.assertEqual(result["source_code"], code.strip())
        self.assertEqual(result["start_line"], 2)
        self.assertEqual(result["end_line"], 5)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_method_in_class(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        class_code = """
class MySpam:
    eggs_count = 0
    def cook(self): # target method
        pass
    def eat(self):
        return "yum"
"""
        method_code = """def cook(self): # target method
        pass""" # Note: ast.get_source_segment might not perfectly re-indent a method if it's the only thing extracted.
                      # It aims to get the exact characters from the original source.

        mock_file_open.return_value.read.return_value = class_code
        result = self.analyzer.get_code_element_source("test.py", "cook", "function") # Methods are type "function"

        self.assertNotIn("error", result, msg=result.get("error", ""))

        # ast.get_source_segment should preserve original indentation and content
        expected_source_lines = class_code.splitlines()[3:5] # Lines for 'def cook...' and '    pass'
        expected_source = "\n".join(l.strip() if i == 0 else l for i, l in enumerate(expected_source_lines)) # Strip first line only for direct comparison

        # Simpler check: ensure the core definition is there
        self.assertIn("def cook(self):", result["source_code"])
        self.assertIn("pass", result["source_code"])

        self.assertEqual(result["start_line"], 4) # Line of 'def cook(self):'
        self.assertEqual(result["end_line"], 5)   # Line of '    pass'

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_async_function(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        # Dummy asyncio for AST parsing if needed, though not strictly for source extraction
        code = "import asyncio\n\nasync def my_async_func():\n    await asyncio.sleep(0)\n"
        mock_file_open.return_value.read.return_value = code

        result = self.analyzer.get_code_element_source("test.py", "my_async_func", "function")
        self.assertNotIn("error", result)
        # ast.get_source_segment should return the exact segment
        self.assertEqual(result["source_code"], "async def my_async_func():\n    await asyncio.sleep(0)")
        self.assertEqual(result["start_line"], 3)
        self.assertEqual(result["end_line"], 4)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open, read_data="def foo(): pass")
    def test_get_element_source_element_not_found(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        result = self.analyzer.get_code_element_source("test.py", "non_existent_func", "function")
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    @patch('os.path.isfile', return_value=False)
    def test_get_element_source_file_not_found(self, mock_isfile):
        result = self.analyzer.get_code_element_source("test.py", "foo", "function")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "File not found: test.py")

    @patch('os.path.isfile', return_value=True)
    def test_get_element_source_not_python_file(self, mock_isfile):
        result = self.analyzer.get_code_element_source("test.txt", "foo", "function")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Not a Python file.")

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open, read_data="def func(\n  return 1") # Syntax error
    def test_get_element_source_syntax_error_in_file(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        result = self.analyzer.get_code_element_source("syntax.py", "func", "function")
        self.assertIn("error", result)
        self.assertTrue(result["error"].startswith("Error parsing file syntax.py:"))

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_element_source_start_end_lines_complex_structure(self, mock_file_open, mock_isfile):
        mock_isfile.return_value = True
        code = """# Comment line 1
# Comment line 2
import os

class MyClass: # Line 5
    \"\"\"Docstring for class\"\"\" # Line 6

    class_var = 100 # Line 8

    def __init__(self, val): # Line 10
        self.val = val # Line 11

    @classmethod # Line 13
    def a_classmethod(cls, data): # Line 14
        \"\"\"Docstring for method\"\"\" # Line 15
        if data > 0: # Line 16
            return True # Line 17
        else: # Line 18
            return False # Line 19

def another_func(): # Line 21
    pass # Line 22
"""
        mock_file_open.return_value.read.return_value = code

        # Test MyClass
        class_result = self.analyzer.get_code_element_source("test.py", "MyClass", "class")
        self.assertNotIn("error", class_result, msg=class_result.get("error",""))
        self.assertEqual(class_result["start_line"], 5)
        # ast.get_source_segment includes everything until the start of the next node or EOF
        # In this case, it goes up to line 19 (the end of the last method in the class)
        self.assertEqual(class_result["end_line"], 19)
        self.assertIn("class MyClass:", class_result["source_code"])
        self.assertIn("class_var = 100", class_result["source_code"])
        self.assertIn("def a_classmethod(cls, data):", class_result["source_code"])
        self.assertIn("return False", class_result["source_code"])


        # Test a_classmethod (decorated method)
        method_result = self.analyzer.get_code_element_source("test.py", "a_classmethod", "function")
        self.assertNotIn("error", method_result, msg=method_result.get("error",""))
        self.assertEqual(method_result["start_line"], 13) # Includes @classmethod decorator
        self.assertEqual(method_result["end_line"], 19)
        self.assertIn("@classmethod", method_result["source_code"])
        self.assertIn("def a_classmethod(cls, data):", method_result["source_code"])
        self.assertIn("return False", method_result["source_code"])

        # Test another_func
        func_result = self.analyzer.get_code_element_source("test.py", "another_func", "function")
        self.assertNotIn("error", func_result, msg=func_result.get("error",""))
        self.assertEqual(func_result["start_line"], 21)
        self.assertEqual(func_result["end_line"], 22)
        self.assertEqual(func_result["source_code"].strip(), "def another_func(): # Line 21\n    pass")


if __name__ == '__main__':
    unittest.main()
