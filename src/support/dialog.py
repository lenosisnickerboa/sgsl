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
was clicked. choice_dialog_with_toggles() is the same as choice_dialog()
plus a column of independent checkboxes, returning their final states
alongside the clicked button's value.
"""

import sys
from typing import Any, Optional

import ui.widgets as ui

# Set (via default_dialog_master()) around a ConfigItem.set() call whose
# transform may pop up one of this module's dialogs several calls removed
# from any window reference (e.g. confirm_workshop_item(), reached through
# a WORKSHOP_MAPS/WORKSHOP_MAPGROUPS item's transform) -- lets that dialog
# still center on the configuration window it was triggered from, rather
# than always falling back to the application's main window. See
# UiBuilder._apply_edit().
_default_master: Optional[Any] = None


class default_dialog_master:
    """Context manager: makes `master` the default parent window for any
    of this module's dialogs invoked without an explicit `master` of
    their own, for the duration of the `with` block."""

    def __init__(self, master: Optional[Any]):
        self.master = master

    def __enter__(self) -> None:
        global _default_master
        self._previous = _default_master
        _default_master = self.master

    def __exit__(self, *exc_info) -> None:
        global _default_master
        _default_master = self._previous


def _resolve_master(master: Optional[Any]) -> Optional[Any]:
    return master if master is not None else _default_master


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
    message: str,
    title: str = "Confirm",
    ok_text: str = "OK",
    cancel_text: str = "Cancel",
    master: Optional[Any] = None,
) -> bool:
    """Show `message` (may be multi-line) in a modal dialog with OK/
    Cancel buttons, and block until the user dismisses it. Returns
    True if OK was pressed, or False if Cancel was pressed (or the
    dialog was closed via its own close button).

    `master`, same as choice_dialog()'s, is the window the dialog
    centers itself on -- falls back to whatever default_dialog_master()
    last set, then to the application's main window, if omitted."""
    dialog = ui.ConfirmDialog(
        title=title,
        message=message,
        ok_text=ok_text,
        cancel_text=cancel_text,
        master=_resolve_master(master),
    )
    return dialog.show()


def choice_dialog(
    message: str,
    choices: list[tuple[str, str, Any]],
    title: str = "Choose",
    cancel_value: Any = None,
    master: Optional[Any] = None,
) -> Any:
    """Show `message` (may be multi-line) in a modal dialog with one
    button per (label, tooltip, value) tuple in `choices`, left to
    right, and block until the user dismisses it. Returns the clicked
    button's value, or `cancel_value` if the dialog was closed via its
    own close button instead.

    `master`, if given, is the window the dialog centers itself on
    (see ChoiceDialog._center_on_master()) -- e.g. a config window,
    rather than the application's main window, when that's what the
    user is actually looking at. Defaults to the main window, same as
    every other dialog in this module, if omitted."""
    dialog = ui.ChoiceDialog(
        title=title,
        message=message,
        choices=choices,
        cancel_value=cancel_value,
        master=master,
    )
    return dialog.show()


def choice_dialog_with_toggles(
    message: str,
    toggles: list[tuple[str, str, str]],
    choices: list[tuple[str, str, Any]],
    title: str = "Choose",
    cancel_value: Any = None,
    master: Optional[Any] = None,
) -> tuple[Any, dict[str, bool]]:
    """Like choice_dialog(), but with an extra (key, label, tooltip)
    checkbox per entry in `toggles`, shown above the button row --
    unchecked by default, and independent of which button is clicked.
    Returns (choice_value, {key: bool, ...}); the toggle dict always
    reflects the final checked state of every toggle, even if the
    dialog was closed (in which case choice_value is `cancel_value`,
    same as choice_dialog())."""
    dialog = ui.ChoiceDialogWithToggles(
        title=title,
        message=message,
        toggles=toggles,
        choices=choices,
        cancel_value=cancel_value,
        master=master,
    )
    return dialog.show()
