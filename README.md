# MasterJulesWalker: AI-Assisted TUI Development Tool

MasterJulesWalker is a Terminal User Interface (TUI) application designed to assist developers by integrating AI capabilities directly into their workflow. It provides features like AI-powered chat, code analysis, test generation, command suggestions, and snippet management, all within a convenient TUI environment.

## Core Features

MasterJulesWalker offers a suite of tools to enhance productivity:

*   **AI Chat:** Interact with a Large Language Model (LLM) directly within the "Main" tab for coding assistance, questions, and brainstorming. Supports including file context in prompts using `@include path/to/file.py`.
*   **File System Navigation:** Browse your project's file tree in the "Files" tab. View file content and add files to the AI's context for more relevant interactions.
*   **Code Analysis:** Analyze Python files to get a structured overview of classes and functions. This analysis can then be used as context for other AI features.
*   **Command Execution:** List and run predefined project-specific or general-purpose commands from the "Commands" tab.
*   **Application Settings:** Configure your OpenRouter API key and preferred LLM model through the "Settings" tab.
*   **AI-Powered Test Generation:** Automatically generate unit tests for your Python code.
*   **Context-Aware Command Suggestions:** Receive intelligent suggestions for commands based on your current working context.
*   **Integrated Snippet Management:** Save, manage, and reuse useful code snippets.

### AI-Powered Test Generation

*   **Purpose:** Streamline the development process by automatically generating boilerplate and initial test cases for Python functions and classes.
*   **Usage:**
    1.  Navigate to the **"Files"** tab using Left/Right arrow keys.
    2.  Select a Python file (`.py`) from the file tree using UP/DOWN arrow keys.
    3.  Press **'a'** to analyze the selected file. The view will switch to the "Analyzer Mode".
    4.  In the Analyzer view, use UP/DOWN arrow keys to highlight a specific function or class from the analysis report.
    5.  Press **'t'** to trigger test generation for the selected item.
    6.  The application will fetch generated tests from the LLM and display them in a new "Test Viewer" mode.
    7.  Scroll through the generated tests using UP/DOWN/PAGE UP/PAGE DOWN keys.
    8.  Press **'b'** to return from the Test Viewer to the Analyzer view.

### Context-Aware Command Suggestions

*   **Purpose:** Get dynamic recommendations for commands that might be relevant to your current task, based on factors like files in context, recent chat interactions, and active code analysis.
*   **Usage:**
    1.  Navigate to the **"Commands"** tab.
    2.  Upon entering the tab, suggestions are automatically fetched based on your current context.
    3.  Suggested commands are marked with `[*] ` in the command list.
    4.  Use UP/DOWN arrow keys to select a command and [Enter] to execute it.
    5.  Press **F5** to manually refresh the command suggestions at any time while in the "Commands" tab.

### Integrated Snippet Management

*   **Purpose:** Efficiently save, find, and reuse frequently used code snippets, reducing repetitive typing and improving consistency.
*   **Usage:**
    1.  Navigate to the **"Snippets"** tab.
    2.  A list of your saved snippets will be displayed. Use UP/DOWN arrow keys to navigate this list.
    3.  **View Snippet:** Select a snippet and press **[Enter]**. The content of the snippet will be displayed. Press **'b'** to return to the snippet list.
    4.  **Add New Snippet:** Press **'a'**. This opens a form to input the snippet's details:
        *   **Name:** A descriptive name for your snippet.
        *   **Language:** The programming language of the snippet (e.g., "python", "javascript").
        *   **Category:** A user-defined category for organization.
        *   **Tags:** Comma-separated tags for easier searching (e.g., "api, fetch, example").
        *   **Content:** The actual code or text of the snippet. Pressing [Enter] in this field creates a newline.
        *   Use **Tab** and **Shift+Tab** to navigate between form fields.
        *   Type directly into the fields.
        *   Navigate to "Save" and press **[Enter]** to save the snippet.
        *   Navigate to "Cancel" or press **[Esc]** to discard the new snippet.
    5.  **Edit Snippet:** Select a snippet from the list and press **'e'**. This opens the same form, pre-filled with the snippet's data, allowing you to make changes and save.
    6.  **Delete Snippet:** Select a snippet and press **'d'**. A confirmation message will appear. Press **'d'** again to confirm the deletion. Any other key will cancel the deletion.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/masterjuleswalker.git # Replace with actual URL
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd masterjuleswalker
    ```
3.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```
    *(Ensure `requirements.txt` includes `requests` and any other necessary packages like `openai` or specific LLM client libraries if not using a generic OpenRouter client via `requests` only).*

## Configuration

MasterJulesWalker requires an API key for features powered by Large Language Models (LLMs), such as AI Chat, Test Generation, and Command Suggestions. It uses OpenRouter.ai to interface with various LLM providers.

*   **API Key:**
    *   The OpenRouter API key can be set via the **"Settings"** tab within the application.
    *   Alternatively, you can set the `OPENROUTER_API_KEY` environment variable before launching the application.
*   **LLM Model:**
    *   The LLM model can also be configured in the **"Settings"** tab.
    *   The default model is `google/gemini-flash-1.5-latest`. You can change this to any model compatible with the OpenRouter API that you have access to.

Snippets are saved locally in a `snippets.json` file in the application's root directory by default.

## Basic Usage

1.  **Start the application:**
    From the root directory of the project (`masterjuleswalker`), run:
    ```bash
    python -m src.main
    ```
2.  **Navigating Tabs:**
    *   Use the **Left Arrow (`<-`)** and **Right Arrow (`->`)** keys to switch between the main tabs (Main, Files, Commands, Snippets, Settings).
3.  **Exiting the Application:**
    *   Press **'q'** or **Ctrl+C** to quit the application.

## Contributing

Contributions are welcome! If you have suggestions for improvements, new features, or find any bugs, please feel free to open an issue or submit a pull request on the project's repository.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
(Assuming a `LICENSE` file exists. If not, one should be added, typically containing the MIT License text).
