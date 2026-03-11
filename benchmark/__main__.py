"""
Entry point for running benchmark as a module.

Usage:
    python -m benchmark run
    python -m benchmark analyze <results_file>
    python -m benchmark info
"""

from .cli import cli

if __name__ == "__main__":
    cli()
