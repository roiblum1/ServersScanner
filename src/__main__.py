"""
Main entry point for running the src package directly.

This allows running the web UI with:
    python src/web_ui.py
    python -m src.web_ui

Both will work correctly.
"""

import sys
from pathlib import Path

# Add parent directory to Python path
# This ensures imports work when running as a script
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import and run the main function
from src.web_ui import main

if __name__ == "__main__":
    main()
