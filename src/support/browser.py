"""
browser.py

Tiny wrapper around webbrowser.open(), so every "open this URL in the
user's default browser" call site (the GitHub button, the update-
available dialog's link, ...) goes through one place.
"""

import webbrowser


def open_url(url: str) -> None:
    webbrowser.open(url)
