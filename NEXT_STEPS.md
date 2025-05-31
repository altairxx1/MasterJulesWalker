# Next Steps for MasterJulesWalker

This document outlines potential features and enhancements for future development of the MasterJulesWalker application. These are based on identified areas for improvement and new capabilities that could enhance user experience and functionality.

## Implemented Features

1.  **AI-Powered Test Generation:** *(Implemented)*
    *   **Description:** Allow users to select a function or class (e.g., via the "Files" tab after analysis) and request the LLM to generate unit test cases (e.g., Python's `unittest` or `pytest` format).
    *   **Benefit:** Speeds up the development cycle by automating initial test creation and encourages more comprehensive test coverage.

2.  **Context-Aware Command Suggestions:** *(Implemented)*
    *   **Description:** The LLM proactively suggests relevant pre-defined or custom commands based on the files currently in context, recent chat topics, or analysis results. Suggestions appear in the "Commands" tab.
    *   **Benefit:** Improves discoverability and utility of the "Commands" feature, making workflows more efficient by anticipating user needs.

3.  **Integrated Snippet Management:** *(Implemented)*
    *   **Description:** A dedicated "Snippets" tab allowing users to save, categorize, search, and quickly insert reusable code snippets.
    *   **Benefit:** Boosts productivity by providing quick access to frequently used code fragments and reducing repetitive typing.

4.  **LLM-Assisted Refactoring Tools:** *(Implemented)*
    *   **Description:** After code analysis, users can select a code block (function, method, or segment) and request the LLM to suggest specific refactorings (e.g., "extract variable," "simplify conditional," "convert to list comprehension," "identify anti-patterns"). Diff views could show proposed changes.
    *   **Benefit:** Helps improve code quality, maintainability, and adherence to best practices, while also serving as a learning tool.

## Proposed Features (Top 20 - Remaining)

1.  **Project-Wide Semantic Search:**
    *   **Description:** Implement a project-level search bar (e.g., accessible via a hotkey) that uses LLM embeddings or semantic understanding to find relevant files, classes, functions, or even conceptual information, going beyond simple keyword matching.
    *   **Benefit:** Enables more intuitive and powerful code navigation and information retrieval, especially in large or unfamiliar codebases.

2.  **Enhanced Session Snapshots & Workspace Management:**
    *   **Description:** Allow users to save the entire application state as a named "snapshot" or "workspace"—including chat history, open files in context, selected tabs, UI layout preferences, and potentially cursor positions or last viewed lines.
    *   **Benefit:** Facilitates seamless context switching between different tasks, projects, or debugging sessions, improving workflow continuity. (Extends "Persistent Chat History").

3.  **Visual Code Dependency Explorer:**
    *   **Description:** A new tab that generates and displays a navigable, graphical map of dependencies between files, classes, and functions within the current context or a user-defined scope of the project.
    *   **Benefit:** Provides a clearer understanding of codebase architecture and relationships, making it easier to trace data flow and impact of changes.

4.  **Flexible Multi-LLM Configuration & Switching:**
    *   **Description:** Expand the "Settings" tab to allow users to configure multiple LLM providers and models (e.g., different OpenAI models, Anthropic Claude, local LLMs if supported). Allow easy switching between configured models, perhaps even per chat session.
    *   **Benefit:** Offers users greater flexibility to choose the most suitable or cost-effective LLM for their current task or project. (Extends "Advanced Configuration Options").

5.  **Automated Draft Documentation Generation:**
    *   **Description:** Users can select a Python file, class, or function and trigger the LLM to generate draft documentation, such as docstrings in a standard format (e.g., reStructuredText, Google style) or a summary for a README.
    *   **Benefit:** Kickstarts the often-neglected documentation process, saving time and ensuring a baseline level of code documentation.

6.  **Interactive Walkthroughs & Onboarding (AI-Guided):**
    *   **Description:** For new users, or when exploring new features, provide an AI-guided interactive walkthrough of the TUI's capabilities. The LLM could explain UI elements or suggest next steps based on user actions.
    *   **Benefit:** Improves user onboarding, feature discovery, and overall usability of the application, especially as more complex features are added.

7.  **Enhanced File Context in Chat:**
    *   **Description:** Allow users to directly reference files within chat prompts (e.g., `@include path/to/file.py explain class X`). The LLM could also suggest adding relevant files from the project to the context based on the conversation. *(Partially implemented with `@include` directive)*
    *   **Benefit:** More focused and efficient interaction with the LLM regarding specific code.

8.  **Interactive Code Modification (Diff Application):**
    *   **Description:** When the LLM suggests code changes, display a diff view within the TUI. Provide an option for the user to review and apply these changes directly to the local file.
    *   **Benefit:** Streamlines the process of iterating on code with AI assistance.

9.  **User-Defined Commands:**
    *   **Description:** Allow users to define their own custom shell commands and scripts that can be executed from the "Commands" tab. This could be managed via a configuration file.
    *   **Benefit:** Extends the utility of the Commands tab to user-specific workflows.

10. **Smarter Context Chunking/Retrieval for Large Files:**
    *   **Description:** For very large files added to context, implement a strategy to send only the most relevant chunks to the LLM (e.g., based on user query, selected symbols, or embedding-based retrieval) instead of the entire file content.
    *   **Benefit:** Improves performance, reduces token usage, and allows working with larger codebases.

11. **Search and Filtering in File Tree:**
    *   **Description:** Add a search/filter capability to the "Files" tab to quickly find files or directories by name in large projects.
    *   **Benefit:** Improves navigation efficiency in complex projects.

12. **Persistent Chat History:**
    *   **Description:** Save chat history (per project or globally) across application sessions, allowing users to resume previous conversations.
    *   **Benefit:** Enhances continuity and allows users to refer back to previous interactions.

13. **Git Integration - Staging and Committing:**
    *   **Description:** Extend Git functionalities beyond viewing status/diff. Allow users to stage specific files or hunks and create commits, potentially with AI-assisted commit messages.
    *   **Benefit:** Integrates more of the development workflow directly into the TUI.

14. **Multi-File Code Analysis & Symbol Navigation:**
    *   **Description:** Enhance the code analyzer to understand relationships between Python files (e.g., follow imports). Potentially add functionality to jump to definitions of symbols (functions, classes) across files.
    *   **Benefit:** Provides deeper code understanding and navigation capabilities.

15. **Advanced Configuration Options:**
    *   **Description:** Expand the "Settings" tab to include more granular control over LLM parameters (e.g., temperature per chat, top_p), UI appearance (colors), and keybindings.
    *   **Benefit:** Allows users to tailor the application more closely to their preferences.

16. **Plugin System for Extensibility:**
    *   **Description:** Design a basic plugin architecture that would allow the community or individual users to develop and integrate new features or tools (e.g., new analyzers for different languages, specialized command sets).
    *   **Benefit:** Future-proofs the application and allows for community-driven expansion.

## Considerations

The priority and implementation details of these features would require further discussion and planning. User feedback should also play a significant role in determining which features are most valuable.
