"""Logging utilities using rich"""
from rich.console import Console
import sys

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
