from pathlib import Path
from typing import Callable, Optional, Union
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from datetime import datetime
from ui.widgets import SnapWindow, make_tooltip


class TerminalWindow(SnapWindow, tb.Toplevel):
    """A terminal-style output window. No process attached — just a text
    display you can append lines to on demand via add_line().

    Stays alive for the lifetime of the app; use show()/hide() to toggle
    visibility instead of creating/destroying it.

    See SnapWindow (ui.widgets) for the automatic snap-chain behavior.
    """

    def __init__(
        self,
        master,
        on_close: Callable[[], None],
        install_dir: Union[str, Path],
        title="Terminal",
        max_lines: int = 0,
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("1024x768")

        self.on_close = on_close
        self.install_dir = Path(install_dir)
        # 0 means "no limit" — the log is left to grow unbounded.
        self.max_lines = max_lines
        self._listeners: list[Callable[[str], object]] = []
        self._init_snap()

        button_row = tb.Frame(self)
        button_row.pack(fill=X, padx=1, pady=(1, 0))

        save_button = tb.Button(button_row, text="Save", command=self.save_to_file)
        save_button.pack(side=LEFT, padx=(0, 5))
        make_tooltip(save_button, text="Save the current log to a timestamped file")

        clear_button = tb.Button(button_row, text="Clear", command=self.clear)
        clear_button.pack(side=LEFT)
        make_tooltip(clear_button, text="Clear the log")

        self.output = ScrolledText(
            self, padding=5, autohide=False, height=20, vbar=True
        )
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

    def register_listener(self, callback: Callable[[str], object]) -> None:
        """Register a callback to be invoked with the raw text of every
        line passed to add_line(). The callback's return value is not
        used by the terminal itself; it exists so callers can share a
        common signature, e.g. one that reports back an interpretation
        of the line (see game.Game.interpret_terminal_line)."""
        self._listeners.append(callback)

    def add_line(self, text, tag="normal"):
        """Append a timestamped line of text. Safe to call from any thread."""
        for listener in self._listeners:
            listener(text)
        timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        full_text = f"[{timestamp}] {text}"
        self.after(0, self._append, full_text, tag)

    def _append(self, text, tag):
        self.output.text.insert("end", text + "\n", tag)
        self._trim_to_max_lines()
        self.output.text.see("end")

    def _trim_to_max_lines(self):
        if self.max_lines <= 0:
            return
        # The Text widget always has a trailing phantom empty line past
        # the last "\n", which "end-1c"'s line number includes — don't
        # count it as one of the log's actual lines.
        line_count = int(self.output.text.index("end-1c").split(".")[0]) - 1
        excess = line_count - self.max_lines
        if excess > 0:
            self.output.text.delete("1.0", f"{excess + 1}.0")

    def clear(self):
        self.after(0, lambda: self.output.text.delete("1.0", "end"))

    def get_content(self) -> str:
        """Return the current log text (no trailing newline)."""
        return self.output.text.get("1.0", "end-1c")

    def save_to_file(self):
        log_dir = self.install_dir / "terminal_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        file_path = log_dir / filename
        file_path.write_text(self.get_content(), encoding="utf-8")
        self.add_line(f"Saved terminal log to {file_path}", tag="info")

    def show(self):
        """Reveal the window, joining the snap chain (see
        SnapWindow._join_chain()) and snapping to its right edge, and
        bring it to the front. Reposition of the rest of the chain
        happens via the <Configure> binding from _init_snap()."""
        self._join_chain()
        self._snap_to_anchor()
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self):
        """Hide the window without destroying it or losing its contents."""
        self.withdraw()
        # withdraw() fires no <Configure>, so leaving the chain (and
        # reconnecting whatever was chained after this window) has to
        # happen explicitly here rather than relying on that binding.
        self._leave_chain()
        self.on_close()

    def toggle(self):
        if self.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def is_visible(self):
        return self.state() != "withdrawn"
