"""PyInstaller entry point for the overlay (`codebuddy-overlay`)."""

import sys

from codebuddy_overlay.app import main

if __name__ == "__main__":
    sys.exit(main())
