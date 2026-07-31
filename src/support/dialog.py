"""
dialog.py

Small blocking helper dialogs built on ui.widgets.Dialog: ok_dialog()
shows a message with an OK button and waits for it to be dismissed;
ok_dialog_exit() does the same and then closes the application.
link_dialog() is the same as ok_dialog() but with an extra clickable
link that opens in the default web browser.
edit_string_dialog_box() shows an editable string with OK/Cancel
buttons and returns the edited value or None.
"""

import sys
from typing import Optional

import ui.widgets as ui


def ok_dialog(message: str, title: str = "Message") -> None:
    """Show `message` in a modal dialog with an OK button, and block
    until the user dismisses it."""
    dialog = ui.Dialog(title=title, message=message)
    dialog.show()


def link_dialog(
    message: str, link_text: str, link_url: str, title: str = "Message"
) -> None:
    """Show `message` plus a clickable link (opens link_url in the
    default web browser when clicked) in a modal dialog with an OK
    button, and block until the user dismisses it."""
    dialog = ui.LinkDialog(
        title=title, message=message, link_text=link_text, link_url=link_url
    )
    dialog.show()


def ok_dialog_exit(message: str, title: str = "Message") -> None:
    """Show `message` in a modal dialog with an OK button, noting that
    the application will close, block until the user dismisses it,
    then close the application."""
    ok_dialog(f"{message}\n\nThe application will now exit.", title)
    sys.exit(0)


def edit_string_dialog_box(title: str, value: str) -> Optional[str]:
    """Show `value` in a modal, editable text field titled `title` with
    OK/Cancel buttons, and block until the user dismisses it. Returns
    the edited string if OK was pressed, or None if Cancel was pressed
    (or the dialog was closed via its own close button)."""
    dialog = ui.EditStringDialog(title=title, value=value)
    return dialog.show()
