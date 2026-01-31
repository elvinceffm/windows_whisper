"""
Entry point for the Dictate for Windows application.

Run with: python -m dictate
Or: dictate (if installed as package)
"""

import sys


def main() -> int:
    """Main entry point."""
    from .app import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
