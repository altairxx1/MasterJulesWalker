# MasterJulesWalker - Simplified Agentic Coding Shell

## Quick Start (Steps 1-3 & Settings UI)

This section guides you through running the initial minimal terminal UI.

### Prerequisites
- Python 3.8+
- A terminal compatible with `curses` (e.g., most Linux terminals, WSL on Windows).

### Setup and Run
1.  **Clone the repository (if you haven't already):**
    ```bash
    # git clone <repository_url>
    # cd masterjuleswalker
    ```

2.  **Navigate to the project directory:**
    ```bash
    cd masterjuleswalker 
    ```
    (Or whatever your project root folder is named)

3.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
    On Windows (in WSL or if using Command Prompt/PowerShell with Python installed):
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    *   **Note on Chat Functionality (Step 3 onwards):** To use the chat features in the "Main" tab, you'll need to set your OpenRouter API key as an environment variable:
        ```bash
        export OPENROUTER_API_KEY="your-key-here"
        ```
        Refer to the main "Installation & Usage" section for more details on API keys.

5.  Run the application:
    ```bash
    python src/main.py
    ```

6.  Controls:
    - Use **Left/Right Arrow Keys** to switch between tabs.
    - Press **'q'** to quit the application.
    - **Ctrl+C** should also exit gracefully.

---

A barebone, open-source agentic coding assistant that lives in your terminal. Features a dual ASCII UI with interactive buttons and tab system for managing multiple coding contexts.

## Overview

MasterJulesWalker is a simplified agentic coding shell that understands your codebase and helps you code faster through natural language commands. This implementation focuses on core functionality with a clean ASCII-based interface, optimized for WSL and Ubuntu environments.

### Key Features

- **Dual ASCII UI**: Interactive terminal interface with buttons and tab navigation
- **Natural Language Commands**: Chat with your codebase using plain English
- **Project Context**: Automatically understands project structure and files
- **Tab Management**: Handle multiple coding contexts simultaneously 
- **OpenRouter Integration**: Leverages powerful LLMs via OpenRouter API
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MASTERJULESWALKER - Terminal Interface                     │
├─────────────────────────────────────────────────────────────┤
│ [Main] [Files] [Git] [Output] [Settings]        [Help] [⚙] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  > analyze the authentication system                        │
│                                                             │
│  🤖 I found your auth system in src/auth/. It uses JWT     │
│     tokens with Redis for session storage. The main files  │
│     are: auth.js, middleware.js, and models/user.js        │
│                                                             │
│  > fix the type errors in user model                       │
│                                                             │
│  🔧 Found 3 TypeScript errors. Fixing now...               │
│     ✓ Fixed missing return type in getUserById()           │
│     ✓ Added proper interface for UserData                  │
│     ✓ Fixed nullable email field handling                  │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [📁 Explore] [🔍 Search] [✏️ Edit] [🧪 Test] [📤 Commit] │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Status: Ready | Token Usage: 1.2k | Project: my-app        │
└─────────────────────────────────────────────────────────────┘
```

## 5-Step Implementation Plan

### Step 1: Minimal Terminal UI (WSL/Ubuntu Compatible)
**Goal**: Create a basic ASCII interface that works reliably on WSL and Ubuntu

**Implementation**:
- Use Python 3.8+ with `curses` library (pre-installed on Ubuntu/WSL)
- Create simple text-based interface with basic tab navigation
- Implement arrow key navigation and Enter key selection
- Focus on keyboard-only interaction (no mouse dependency)
- Test specifically on WSL2 and Ubuntu 20.04/22.04

**Key Files**:
```
src/
├── main.py          # Entry point and main loop
├── ui.py            # Simple curses-based interface
├── tabs.py          # Basic tab switching (Main, Files, Settings)
└── config.py        # Configuration management
```

**Deliverable**: A working terminal app that shows tabs and accepts basic input

### Step 2: Basic File System Integration
**Goal**: Read project files and display file tree

**Implementation**:
- Implement simple directory traversal with `os.walk()`
- Create basic file tree display in Files tab
- Add `.gitignore` pattern filtering
- Display file contents in a scrollable view
- Handle common file types (Python, JavaScript, JSON, etc.)

**Key Files**:
```
src/
├── files.py         # File system operations
├── tree.py          # Directory tree display
└── viewer.py        # Simple file content viewer
```

**Deliverable**: Browse and view files within the terminal interface

### Step 3: OpenRouter Integration with Gemini
**Goal**: Connect to OpenRouter API using Gemini 2.5 Flash

**Implementation**:
- Create simple HTTP client for OpenRouter API
- Implement basic prompt-response cycle
- Add error handling for network issues
- Use Gemini 2.5 Flash as the default model
- Store API key in environment variable

**Key Files**:
```
src/
├── llm.py           # OpenRouter API client
├── prompts.py       # Basic prompt templates
└── chat.py          # Chat interface logic
```

**Configuration**:
```bash
# WSL/Ubuntu setup
export OPENROUTER_API_KEY="your-api-key-here"
export MJW_MODEL="google/gemini-2.5-flash-preview-05-20"
```

**Deliverable**: Working chat interface that sends messages to Gemini

### Step 4: Basic Command Processing
**Goal**: Handle simple natural language commands about code

**Implementation**:
- Parse basic commands like "analyze this file" or "explain this function"
- Implement file context injection into prompts
- Create simple response formatting
- Add basic code analysis capabilities
- Handle multi-line input for complex queries

**Key Files**:
```
src/
├── commands.py      # Command parsing and execution
├── context.py       # File context management
└── analyzer.py      # Basic code analysis
```

**Deliverable**: Ask questions about your codebase and get responses

### Step 5: Essential Features for Daily Use
**Goal**: Add minimum features needed for practical coding assistance

**Implementation**:
- Save/load conversation history
- Basic search across project files
- Simple file editing with diff preview
- Exit/quit functionality
- Error logging and basic troubleshooting
- Performance optimization for large projects

**Key Files**:
```
src/
├── history.py       # Session persistence
├── search.py        # File content search
├── editor.py        # Basic file editing
└── utils.py         # Logging and error handling
```

**Deliverable**: A functional coding assistant for daily development work

## Installation & Usage

### Prerequisites (WSL/Ubuntu)
- Python 3.8+ (usually pre-installed)
- Git
- OpenRouter API account
- Terminal with UTF-8 support

### WSL/Ubuntu Setup
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python development tools (if needed)
sudo apt install python3-dev python3-pip python3-venv

# Clone the repository
git clone https://github.com/yourusername/masterjuleswalker.git
cd masterjuleswalker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up your API key
export OPENROUTER_API_KEY="your-key-here"
export MJW_MODEL="google/gemini-2.5-flash-preview-05-20"

# Add to ~/.bashrc for persistence
echo 'export OPENROUTER_API_KEY="your-key-here"' >> ~/.bashrc
echo 'export MJW_MODEL="google/gemini-2.5-flash-preview-05-20"' >> ~/.bashrc

# Navigate to your project and start
cd /path/to/your/project
python -m masterjuleswalker

# Or specify a project path
python -m masterjuleswalker --project /path/to/project
```

### Basic Commands
```bash
# Natural language commands
> explain how the database connection works
> fix the linting errors in src/utils
> create unit tests for the user service
> help me refactor this component to use hooks

# Slash commands (shortcuts)
/analyze         # Analyze current project structure
/test           # Run project tests
/commit         # Create commit with AI-generated message
/search <term>  # Search across codebase
/clear          # Clear conversation history
```

### Tab Navigation
- **Main**: Primary chat interface
- **Files**: Basic file browser. Use Arrow Up/Down to select files/directories. Press Enter on a file to view its content. In the viewer, use Up/Down/PageUp/PageDown to scroll and 'b' to go back to the tree.
- **Git**: Version control operations
- **Output**: Command execution results
- **Settings**: Configure MasterJulesWalker. Currently supports setting your OpenRouter API Key and preferred LLM Model Name. Changes are saved to `.mjw_config.json` in the project root.

### Keyboard Shortcuts
- `Tab` / `Shift+Tab`: Navigate between UI elements
- `Ctrl+T`: Switch between tabs
- `Ctrl+C`: Cancel current operation
- `Ctrl+D` / `Esc`: Exit application
- `F1`: Show help

## Configuration

MasterJulesWalker uses a combination of an application-managed JSON file (for settings configured via the UI) and environment variables.

*(The `.masterjuleswalker.json` file mentioned below, intended for user-defined settings like themes or ignore patterns, is part of a future plan and is **not** currently implemented. The settings described within it are illustrative of what such a file might contain.)*

Create `.masterjuleswalker.json` in your project root:
```json
{
  "model": "google/gemini-2.5-flash-preview-05-20",
  "max_tokens": 4000,
  "temperature": 0.1,
  "ignore_patterns": [".env", "node_modules", ".git", "__pycache__"],
  "auto_save": true,
  "theme": "dark"
}
```

### Environment Variables
```bash
# Required
export OPENROUTER_API_KEY="your-openrouter-api-key"

# Optional (defaults shown)
export MJW_MODEL="google/gemini-2.5-flash-preview-05-20"
export MJW_MAX_TOKENS="4000"
export MJW_TEMPERATURE="0.1"
```

### Application-Managed Settings (`.mjw_config.json`)

MasterJulesWalker also saves certain settings, like your OpenRouter API Key and preferred Model Name, directly via the "Settings" tab within the application. These are stored in a file named `.mjw_config.json` in the root of the project directory.

**Priority**: Settings from `.mjw_config.json` (managed via the Settings tab) generally take precedence over environment variables if both are set for the same item (e.g. API key).

**Git Ignore**: The `.mjw_config.json` file is included in this project's `.gitignore` file to prevent accidental commits of your local settings and API keys. If you integrate MasterJulesWalker into a larger project, consider adding `.mjw_config.json` to your project's main `.gitignore` file as well.

## Development Roadmap

### Minimum Viable Product (MVP)
- [x] **Step 1**: Basic terminal UI with tabs (Week 1)
- [ ] **Step 2**: File system integration and browsing (Week 1-2)
- [ ] **Step 3**: OpenRouter + Gemini integration (Week 2)
- [ ] **Step 4**: Basic command processing (Week 3)
- [ ] **Step 5**: Essential daily-use features (Week 3-4)

### Post-MVP Enhancements
- [ ] Advanced git integration
- [ ] Plugin system
- [ ] Multiple model support
- [ ] Enhanced UI with mouse support
- [ ] Performance optimizations
- [ ] Comprehensive testing suite

## Technology Stack

- **UI Framework**: Python `curses` (built-in on Ubuntu/WSL)
- **LLM Provider**: OpenRouter API with Gemini 2.5 Flash
- **File Processing**: `pathlib`, `os` (built-in Python modules)
- **Configuration**: JSON with environment variable overrides
- **Session Storage**: Simple JSON files (no database dependency)
- **Target Platform**: WSL2, Ubuntu 20.04+, Debian-based systems

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Inspired by Anthropic's Claude Code, this project aims to provide an open-source alternative focused on simplicity and effectiveness.

