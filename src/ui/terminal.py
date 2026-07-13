import tkinter as tk
from typing import Callable
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from datetime import datetime

class TerminalWindow(tb.Toplevel):
    """A terminal-style output window. No process attached — just a text
    display you can append lines to on demand via add_line().

    Stays alive for the lifetime of the app; use show()/hide() to toggle
    visibility instead of creating/destroying it.
    """

    def __init__(self, master, on_close: Callable[[], None], title="Terminal", snap_anchor=None):
        super().__init__(master)
        self.title(title)
        self.geometry("1024x768")

        self.on_close = on_close
        self._snap_anchor = snap_anchor
        self._snap_followers = []
        self.output = ScrolledText(self, padding=5, autohide=False, height=20, vbar=True)
        self.output.pack(fill=BOTH, expand=YES, padx=1, pady=1)
        self.output.text.configure(
            state="normal",
            font=("Consolas", 10),
            background="#111",
            foreground="#ddd",
            insertbackground="#ddd",
        )

        self.output.text.tag_configure("normal", foreground="#ddd")
        self.output.text.tag_configure("error", foreground="#ff6b6b")
        self.output.text.tag_configure("success", foreground="#6bff8f")
        self.output.text.tag_configure("info", foreground="#6bb8ff")

        # Intercept the window's own close (X) button: hide instead of destroy
        self.protocol("WM_DELETE_WINDOW", self.hide)

        # Start hidden — the main app decides when to show it
        self.withdraw()

    def add_line(self, text, tag="normal"):
        """Append a timestamped line of text. Safe to call from any thread."""
        timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        full_text = f"[{timestamp}] {text}"
        self.after(0, self._append, full_text, tag)

    def _append(self, text, tag):
        self.output.text.insert("end", text + "\n", tag)
        self.output.text.see("end")

    def clear(self):
        self.after(0, lambda: self.output.text.delete("1.0", "end"))

    def add_snap_follower(self, window) -> None:
        """Register `window` to be repositioned (via its reposition())
        whenever this window is shown, if `window` is visible at the
        time."""
        self._snap_followers.append(window)

    def show(self):
        """Reveal the window, snapped to the right edge of its anchor
        (see snap_anchor), bring it to the front, and reposition any
        visible snap followers to keep them snapped to it."""
        self._snap_to_anchor()
        self.deiconify()
        self.lift()
        self.focus_force()
        for follower in self._snap_followers:
            if follower.is_visible():
                follower.reposition()

    def reposition(self):
        """Re-snap position without changing visibility or stealing focus."""
        self._snap_to_anchor()

    def _snap_to_anchor(self):
        anchor = self._snap_anchor() if self._snap_anchor is not None else self.master
        anchor.update_idletasks()
        x = anchor.winfo_x() + anchor.winfo_width()
        y = anchor.winfo_y()
        self.geometry(f"+{x}+{y}")

    def hide(self):
        """Hide the window without destroying it or losing its contents."""
        self.withdraw()
        self.on_close()

    def toggle(self):
        if self.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def is_visible(self):
        return self.state() != "withdrawn"