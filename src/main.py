import curses
import sys # Added for sys.exit
import os  # Added for os.isatty and os.environ
import logging
import logging.handlers

from .ui import TerminalUI # Assuming ui.py is in the same directory
from .config import load_config # Assuming config.py is in the same directory
from src.config import load_config as load_app_config # For pre-curses check

LOG_FILENAME = "masterjuleswalker.log"

# Configure logging
logger = logging.getLogger("MasterJulesWalker")
logger.setLevel(logging.DEBUG) # Or logging.INFO
# Rotating file handler
handler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME, maxBytes=1024*1024, backupCount=5
)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

def main(stdscr, app_logger): # Modified to accept logger
    """
    Main function to be passed to curses.wrapper.
    Initializes and runs the TerminalUI.
    """
    app_logger.debug("main(stdscr, app_logger) called.")
    # stdscr is the curses window object, automatically provided by curses.wrapper
    
    # Load configuration (optional at this stage for basic UI, but good practice)
    # app_config = load_config() 
    # You can pass app_config to TerminalUI if needed: ui = TerminalUI(stdscr, app_config)

    ui = TerminalUI(stdscr, app_logger) # Pass logger to TerminalUI
    ui.run_loop()

if __name__ == "__main__":
    logger.info("Application starting...")
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

    initial_config = load_app_config()
    if not initial_config.get("openrouter_api_key"):
        print("--- MasterJulesWalker Pre-launch Notice ---")
        print("OpenRouter API key is not configured. AI features may not work correctly.")
        print("You can set the API key in the 'Settings' tab within the application,")
        print("or by setting the OPENROUTER_API_KEY environment variable.")
        print("-------------------------------------------")
        # Adding a small delay so the user has a chance to see it,
        # as curses.wrapper might clear the screen quickly.
        try:
            import time
            time.sleep(2) # Sleep for 2 seconds
        except ImportError:
            pass # time module should ideally always be available

    try:
        # curses.wrapper handles initialization, cleanup, and exception handling for curses applications
        curses.wrapper(main, logger) # Pass logger to main via wrapper
        logger.info("Application exited gracefully after curses.wrapper.")
        # If wrapper exits normally, it means main function completed.
    except curses.error as e:
        logger.exception("Curses error during TUI initialization:")
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
        logger.info("Application shutting down due to curses error.")
        sys.exit(1) # Exit with a non-zero status to indicate failure
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (Ctrl+C).")
        # print("Application interrupted by user (Ctrl+C). Exiting.") # This might not be seen
        logger.info("Application shutting down due to KeyboardInterrupt.")
        sys.exit(0) # Normal exit for Ctrl+C
    except Exception as e:
        logger.exception("An unexpected error occurred at the top level:")
        print(f"An unexpected error occurred: {e}")
        # Consider logging the full traceback here for debugging
        # import traceback
        # traceback.print_exc()
        logger.info("Application shutting down due to an unexpected error.")
        sys.exit(1) # Exit with a non-zero status for other unexpected errors
    finally:
        logger.info("Application final shutdown sequence (if not already exited).")
