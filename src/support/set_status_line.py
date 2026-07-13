"""
set_status_line.py

A small helper for updating the app's status bar (see
ui.widgets.StatusLine) from anywhere without passing the widget
around. init_status_line() registers the widget once during app
setup; set_status_line() updates its text from then on;
restore_status_line() resets it back to "Ready".
"""

from typing import Optional

_status_line = None  # type: Optional["ui.widgets.StatusLine"]


def init_status_line(status_line) -> None:
    """Register the StatusLine widget that set_status_line() updates.
    Call once during app setup, after the widget is created."""
    global _status_line
    _status_line = status_line


def set_status_line(text: str) -> None:
    """Update the status bar text. No-op if init_status_line() hasn't
    been called yet."""
    if _status_line is not None:
        _status_line.set_text(text)


def restore_status_line() -> None:
    """Reset the status bar text back to "Ready"."""
    set_status_line("Ready")
