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


if __name__ == '__main__':
    unittest.main()
