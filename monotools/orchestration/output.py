"""Render shared command-line diagnostics without corrupting ANSI output.

Captured tools may emit terminal escape sequences even though their output crosses
a Python exception boundary. This module converts those sequences to Rich-native
styles before a command console renders the diagnostic.
"""

from rich.console import Console
from rich.text import Text


def print_error(console: Console, error: Exception | str) -> None:
    """Print an error while translating embedded ANSI styling into Rich spans."""
    message = Text("Error: ", style="bold red")
    message.append(Text.from_ansi(str(error)))
    console.print(message)
