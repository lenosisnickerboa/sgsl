"""
dialog.py

Small blocking helper dialogs built on ui.widgets.Dialog: ok_dialog()
shows a message with an OK button and waits for it to be dismissed;
ok_dialog_exit() does the same and then closes the application.
link_dialog() is the same as ok_dialog() but with an extra clickable
link that opens in the default web browser.
edit_string_dialog_box() shows an editable string with OK/Cancel
buttons and returns the edited value or None.
confirm_dialog() shows a message with OK/Cancel buttons and returns
whether OK was pressed. choice_dialog() shows a message with an
arbitrary row of custom-labeled buttons and returns which one's value
was clicked.
"""

import sys
from typing import Any, Optional

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


def confirm_dialog(
    message: str, title: str = "Confirm", ok_text: str = "OK", cancel_text: str = "Cancel"
) -> bool:
    """Show `message` (may be multi-line) in a modal dialog with OK/
    Cancel buttons, and block until the user dismisses it. Returns
    True if OK was pressed, or False if Cancel was pressed (or the
    dialog was closed via its own close button)."""
    dialog = ui.ConfirmDialog(
        title=title, message=message, ok_text=ok_text, cancel_text=cancel_text
    )
    return dialog.show()


def choice_dialog(
    message: str,
    choices: list[tuple[str, str, Any]],
    title: str = "Choose",
    cancel_value: Any = None,
) -> Any:
    """Show `message` (may be multi-line) in a modal dialog with one
    button per (label, tooltip, value) tuple in `choices`, left to
    right, and block until the user dismisses it. Returns the clicked
    button's value, or `cancel_value` if the dialog was closed via its
    own close button instead."""
    dialog = ui.ChoiceDialog(
        title=title, message=message, choices=choices, cancel_value=cancel_value
    )
    return dialog.show()
