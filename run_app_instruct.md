# Running MasterJulesWalker

This guide provides instructions on how to set up and run the MasterJulesWalker application.

## Prerequisites

*   Python (version 3.9 or higher recommended).
*   `pip` (Python package installer).
*   `git` (for cloning the repository).
*   (For WSL users) A working WSL setup with a Linux distribution installed.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/masterjuleswalker.git
    cd masterjuleswalker
    ```

2.  **Create and Activate a Virtual Environment (Recommended):**
    *   **Linux/macOS/WSL:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **Windows (Command Prompt):**
        ```bash
        python -m venv venv
        venv\Scripts\activate.bat
        ```
    *   **Windows (PowerShell):**
        ```bash
        python -m venv venv
        venv\Scripts\Activate.ps1
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

Once the installation is complete, you can run the application using:

```bash
python src/main.py
```

## Basic Usage

*   **Interface Overview:** The application features several tabs:
    *   **Main/Chat:** Interact with the LLM, view responses, and review code suggestions.
    *   **Files:** Browse your project files, add files to the LLM's context, and filter the tree view.
    *   **Commands:** Execute predefined and custom shell commands.
    *   **Analysis:** View results from code analysis tasks. (Note: This tab might be part of "Files" or context-dependent based on UI evolution).
    *   **Snippets:** Manage and use reusable code snippets.
    *   **Settings:** Configure application settings.

*   **Initial Setup:**
    *   **API Keys:** The application uses an LLM (e.g., via OpenRouter). Ensure your API keys are set. This is typically done by setting the `OPENROUTER_API_KEY` environment variable. You can also configure it in the "Settings" tab of the application or by creating a `.mjw_config.json` file in the project root with your key:
        ```json
        {
            "openrouter_api_key": "your_openrouter_api_key_here"
        }
        ```
    *   **Semantic Index:** For project-wide semantic search, build the index using the `build_semantic_index` command in the command palette (usually accessed by typing `:` in the chat input, then the command, or via Ctrl+P). This will process your project files and create a local index.

*   **Key Commands/Features:**
    *   **Chatting:** Type your queries or instructions in the input box in the "Main" tab and press Enter.
    *   **File Tree Filtering:** In the "Files" tab, press `/` to enter filter mode. Type your filter term and press Enter to apply, or ESC to clear.
    *   **Semantic Search:** Use the `semantic_search your query here` command in the command palette (Ctrl+P).
    *   **Reviewing Code Suggestions:**
        1.  After the LLM provides a code suggestion in the chat, use the command `review_code_suggestion <filepath>` (e.g., `review_code_suggestion src/my_module.py`) in the command palette.
        2.  The diff will be displayed in the "Main" tab.
        3.  Use commands `accept_suggestion` to apply the changes (a `.bak` file of the original will be created) or `reject_suggestion` to discard them, entered via the command palette.
    *   **Command Palette:** Access various application commands by pressing `Ctrl+P` (or typing `:` in the chat input, depending on UI focus), then typing the command name (e.g., `build_semantic_index`, `exit`).

*   **Exiting the Application:** Use the `exit` command in the command palette (Ctrl+P, then type `exit`). If the UI becomes unresponsive, Ctrl+C in the terminal where the application is running will force it to close.

## WSL (Windows Subsystem for Linux) Users

*   The application is expected to run well on WSL.
*   Ensure that Python 3.9+ and pip are installed within your WSL distribution.
*   Follow the standard Linux installation steps provided above.
*   The `curses` library, used for the terminal interface, is typically available by default on most Linux distributions. If you encounter issues related to `curses` (e.g., "No module named '_curses'" or display errors), you might need to install its development libraries. For Debian/Ubuntu-based distributions, this often helps:
    ```bash
    sudo apt update
    sudo apt install libncursesw5-dev python3-dev
    ```
*   **Accessing Project Files:** Your project files can be located within the WSL filesystem (e.g., `/home/youruser/masterjuleswalker`) or on the Windows filesystem (e.g., `/mnt/c/Users/youruser/projects/masterjuleswalker`). Both are accessible from within WSL.

## Troubleshooting

*   **`sentence-transformers` Model Download:** The first time you use features like semantic search or the `build_semantic_index` command, the application will download necessary model files from Hugging Face. This requires an active internet connection and can take a few minutes depending on the model size and your internet speed.
*   **API Key Errors:** If you see errors related to API authentication, ensure your LLM API keys are correctly configured as per the "Initial Setup" section. Check environment variables or the in-app Settings tab.
*   **`curses` Errors:** Refer to the WSL section for `curses` related troubleshooting, which can also apply to other minimal Linux environments. If `curses` issues persist, ensure your terminal emulator (e.g., Windows Terminal, GNOME Terminal) is correctly configured (e.g., `TERM` environment variable set to something like `xterm-256color`).

```
