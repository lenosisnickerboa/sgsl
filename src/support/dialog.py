"""
dialog.py

Small blocking helper dialogs built on ui.widgets.Dialog: ok_dialog()
shows a message with an OK button and waits for it to be dismissed;
ok_dialog_exit() does the same and then closes the application.
"""

import sys

import ui.widgets as ui


def ok_dialog(message: str, title: str = "Message") -> None:
    """Show `message` in a modal dialog with an OK button, and block
    until the user dismisses it."""
    dialog = ui.Dialog(title=title, message=message)
    dialog.show()


def ok_dialog_exit(message: str, title: str = "Message") -> None:
    """Show `message` in a modal dialog with an OK button, noting that
    the application will close, block until the user dismisses it,
    then close the application."""
    ok_dialog(f"{message}\n\nThe application will now exit.", title)
    sys.exit(0)
