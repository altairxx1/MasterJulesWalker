import curses
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
    try:
        # curses.wrapper handles initialization, cleanup, and exception handling for curses applications
        curses.wrapper(main)
        print("MasterJulesWalker exited gracefully.")
    except curses.error as e:
        print(f"A curses error occurred: {e}")
        print("Please ensure your terminal supports curses and is adequately sized.")
        print("On Windows, use WSL or a compatible terminal like Windows Terminal.")
    except KeyboardInterrupt:
        print("Application interrupted by user (Ctrl+C). Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
