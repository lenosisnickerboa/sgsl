from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ui.widgets import SnapWindow, make_tooltip

# sgsl's own curated shortlist of the 20 most commonly used CS2/
# Source-engine dedicated server admin console commands (no
# authoritative usage-frequency source exists) -- covering match
# control, player admin, and core server settings. Shown as quick-
# insert buttons below the output log; most of these take an argument
# (a map name, a player id, ...) the user still has to type, so a
# click inserts the command rather than sending it immediately.
_QuickCommands = [
    "status",
    "changelevel",
    "map",
    "mp_restartgame",
    "mp_warmup_start",
    "mp_warmup_end",
    "mp_pause_match",
    "mp_unpause_match",
    "kick",
    "kickid",
    "banid",
    "removeid",
    "sv_cheats",
    "sv_password",
    "rcon_password",
    "say",
    "bot_kick",
    "bot_add",
    "sv_gravity",
    "mp_maxrounds",
]

# Quick-command buttons per row -- 20 commands over this many columns.
_QuickCommandColumns = 10


class RconWindow(SnapWindow, tb.Toplevel):
    """An interactive RCON console window: a command entry + Send
    button, and a scrolling read-only log of every command sent and
    its response (or error). `command_callback` is called with the
    typed command text and must return the response text to display,
    or raise to report a failure (its message is shown in the log
    instead, tagged as an error).

    Stays alive for the lifetime of the app; use show()/hide()/
    toggle() to control visibility. See SnapWindow (ui.widgets) for
    the automatic snap-chain behavior."""

    def __init__(
        self,
        master,
        on_close: Callable[[], None],
        command_callback: Callable[[str], str],
        install_dir: Union[str, Path],
        title: str = "RCON",
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("1100x800")

        self.on_close = on_close
        self.command_callback = command_callback
        self.install_dir = Path(install_dir)
        self._init_snap()

        # Command history -- see _on_history_up()/_on_history_down().
        # _history_index is None while not currently navigating (i.e.
        # the entry holds whatever the user is freely typing);
        # otherwise it's an index into _history, and _pending_command
        # holds what was being typed before history navigation started
        # (restored once the user arrows back past the newest entry).
        self._history: list[str] = []
        self._history_index: Optional[int] = None
        self._pending_command: str = ""

        entry_row = tb.Frame(self)
        entry_row.pack(side=BOTTOM, fill=X, padx=5, pady=5)

        self.command_var = tb.StringVar()
        self.entry = tb.Entry(entry_row, textvariable=self.command_var)
        self.entry.pack(side=LEFT, fill=X, expand=YES)
        self.entry.bind("<Return>", self._on_send)
        self.entry.bind("<Up>", self._on_history_up)
        self.entry.bind("<Down>", self._on_history_down)

        send_button = tb.Button(entry_row, text="Send", command=self._on_send)
        send_button.pack(side=LEFT, padx=(5, 0))
        make_tooltip(send_button, text="Send this command over RCON")

        clear_button = tb.Button(entry_row, text="Clear", command=self.clear)
        clear_button.pack(side=LEFT, padx=(5, 0))
        make_tooltip(clear_button, text="Clear the log")

        save_button = tb.Button(entry_row, text="Save", command=self.save_to_file)
        save_button.pack(side=LEFT, padx=(5, 0))
        make_tooltip(save_button, text="Save the current log to a timestamped file")

        # Packed after entry_row (also side=BOTTOM), so it claims the
        # region just above it -- between the output log and the
        # command entry, as intended.
        quick_commands_frame = tb.Frame(self)
        quick_commands_frame.pack(side=BOTTOM, fill=X, padx=5, pady=(0, 5))
        for index, quick_command in enumerate(_QuickCommands):
            row, column = divmod(index, _QuickCommandColumns)
            button = tb.Button(
                quick_commands_frame,
                text=quick_command,
                bootstyle="secondary",
                command=lambda c=quick_command: self._insert_quick_command(c),
            )
            button.grid(row=row, column=column, padx=1, pady=1, sticky="ew")
            make_tooltip(button, text=f'Insert "{quick_command}" into the command entry')
        for column in range(_QuickCommandColumns):
            quick_commands_frame.columnconfigure(column, weight=1)

        self.output = ScrolledText(
            self, padding=5, autohide=False, height=20, vbar=True
        )
        self.output.pack(fill=BOTH, expand=YES, padx=5, pady=(5, 0))
        self.output.text.configure(
            state="normal",
            font=("Consolas", 10),
            background="#111",
            foreground="#ddd",
            insertbackground="#ddd",
        )
        self.output.text.tag_configure("command", foreground="#6bb8ff")
        self.output.text.tag_configure("response", foreground="#ddd")
        self.output.text.tag_configure("error", foreground="#ff6b6b")
        self.output.text.tag_configure("info", foreground="#6bb8ff")

        # Intercept the window's own close (X) button: hide instead of destroy
        self.protocol("WM_DELETE_WINDOW", self.hide)

        # Start hidden — the main app decides when to show it
        self.withdraw()

    def _on_send(self, event=None):
        command = self.command_var.get().strip()
        if not command:
            return
        # Skip a duplicate of the most recently sent command, the same
        # way a shell's history typically does, rather than piling up
        # repeats from someone just hammering the same command.
        if not self._history or self._history[-1] != command:
            self._history.append(command)
        self._history_index = None
        self._pending_command = ""
        self._append(f"> {command}", "command")
        try:
            response = self.command_callback(command)
        except Exception as e:
            self._append(str(e), "error")
        else:
            # Always show *something* for a successful call, even an
            # empty response -- otherwise a command that legitimately
            # has nothing to report looks identical to one that's
            # still hung/never actually got sent.
            self._append(response if response else "(empty response)", "response")
        self.command_var.set("")

    def _on_history_up(self, event=None):
        if not self._history:
            return
        if self._history_index is None:
            # Just starting to navigate -- remember what was being
            # typed so Down can restore it once we arrow back past the
            # newest history entry.
            self._pending_command = self.command_var.get()
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._set_command_text(self._history[self._history_index])

    def _on_history_down(self, event=None):
        if self._history_index is None:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._set_command_text(self._history[self._history_index])
        else:
            # Arrowed past the newest entry -- back to whatever was
            # being typed before history navigation started.
            self._history_index = None
            self._set_command_text(self._pending_command)

    def _set_command_text(self, text: str) -> None:
        self.command_var.set(text)
        self.entry.icursor(END)

    def _insert_quick_command(self, command: str) -> None:
        """Fill the command entry with `command` (plus a trailing
        space, ready for an argument) rather than sending it right
        away -- most quick commands take one (a map name, a player id,
        ...) the user still has to type."""
        self._set_command_text(f"{command} ")
        self.entry.focus_set()

    def _append(self, text: str, tag: str) -> None:
        timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        self.output.text.insert("end", f"[{timestamp}] {text}\n", tag)
        self.output.text.see("end")

    def clear(self):
        self.output.text.delete("1.0", "end")

    def get_content(self) -> str:
        """Return the current log text (no trailing newline)."""
        return self.output.text.get("1.0", "end-1c")

    def save_to_file(self):
        log_dir = self.install_dir / "rcon_output"
        log_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        file_path = log_dir / filename
        file_path.write_text(self.get_content(), encoding="utf-8")
        self._append(f"Saved RCON output to {file_path}", "info")

    def show(self):
        """Reveal the window, joining the snap chain (see
        SnapWindow._join_chain()) and snapping to its right edge, and
        bring it to the front with the command entry focused.
        Reposition of the rest of the chain happens via the
        <Configure> binding from _init_snap()."""
        self._join_chain()
        self._snap_to_anchor()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.entry.focus_set()

    def hide(self):
        """Hide the window without destroying it or losing its log."""
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
