import curses
import sys # Added for sys.exit
import os  # Added for os.isatty and os.environ

from .ui import TerminalUI # Assuming ui.py is in the same directory
from .config import load_config # Assuming config.py is in the same directory

def main(stdscr):
    """
    Main function to be passed to curses.wrapper.
    Initializes and runs the TerminalUI.
    """
    # stdscr is the curses window object, automatically provided by curses.wrapper
    
    # Load configuration (optional at this stage for basic UI, but good practice)
    # app_config = load_config() 
    # You can pass app_config to TerminalUI if needed: ui = TerminalUI(stdscr, app_config)

    ui = TerminalUI(stdscr)
    ui.run_loop()

if __name__ == "__main__":
    # Basic terminal capability check (optional enhancement)
    if not os.isatty(sys.stdout.fileno()):
        print("Warning: stdout is not a TTY. The TUI might not work as expected.")
        # Depending on strictness, could exit here:
        # print("Please run in a valid terminal.")
        # sys.exit(1)

    term = os.environ.get("TERM", "unknown")
    if term == "dumb":
        print("Warning: Your terminal type is reported as 'dumb'.")
        print("The TUI requires more advanced terminal capabilities.")
        # Consider exiting if term is 'dumb'
        # sys.exit(1)

    try:
        # curses.wrapper handles initialization, cleanup, and exception handling for curses applications
        curses.wrapper(main)
        # If wrapper exits normally, it means main function completed.
        # The print below might not be visible if curses clears the screen on exit.
        # print("MasterJulesWalker exited gracefully.")
    except curses.error as e:
        print("-------------------------------------------------------------")
        print("ERROR: Terminal User Interface (TUI) Initialization Failed!")
        print("-------------------------------------------------------------")
        print(f"A 'curses' library error occurred: {e}")
        print("\nThis usually means your terminal environment is not fully compatible.")
        print("Suggestions:")
        print("  - Ensure you are running this in a standard terminal or console window.")
        print("  - If on Windows, try using Windows Terminal or WSL (Windows Subsystem for Linux).")
        print("  - Check your TERM environment variable (e.g., should be 'xterm-256color', 'vt100', etc.).")
        print("    Avoid using 'dumb' terminals or very basic shells.")
        print("  - Ensure your terminal window is not too small.")
        print("  - If using `screen` or `tmux`, ensure they are configured correctly.")
        print("-------------------------------------------------------------")
        sys.exit(1) # Exit with a non-zero status to indicate failure
    except KeyboardInterrupt:
        # print("Application interrupted by user (Ctrl+C). Exiting.") # This might not be seen
        sys.exit(0) # Normal exit for Ctrl+C
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Consider logging the full traceback here for debugging
        # import traceback
        # traceback.print_exc()
        sys.exit(1) # Exit with a non-zero status for other unexpected errors
