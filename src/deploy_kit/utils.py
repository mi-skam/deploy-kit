"""Logging utilities using rich"""

from typing import TypeGuard
from rich.console import Console

console = Console()
console_err = Console(stderr=True)


class Logger:
    """Simple logger with colored output"""

    def info(self, msg: str):
        console.print(f"[blue][INFO][/blue] {msg}")

    def success(self, msg: str):
        console.print(f"[green][SUCCESS][/green] {msg}")

    def warn(self, msg: str):
        console.print(f"[yellow][WARN][/yellow] {msg}")

    def error(self, msg: str):
        console_err.print(f"[red][ERROR][/red] {msg}")


# Global logger instance
logger = Logger()


def is_non_empty_str(value: str | None) -> TypeGuard[str]:
    """Type guard that checks if value is a non-empty string.

    Args:
        value: The value to check

    Returns:
        True if value is a non-None, non-empty string

    Usage:
        if not is_non_empty_str(var):
            raise ValueError("var must be a string")
        # var is now typed as str (not str | None)
    """
    return value is not None and value != ""
