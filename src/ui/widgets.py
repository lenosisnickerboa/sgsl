import tkinter.ttk as tkttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.tableview import Tableview
import ui.helpers as helpers

def Nop():
    pass


class EnableDisableMixin:
    """Adds enable()/disable() to a widget, applied recursively to
    itself and all descendants — so a composite widget (e.g. a
    Labelframe wrapping a Spinbox/Entry/Combobox/Button, or a whole
    window full of them) is fully disabled/enabled regardless of its
    internal structure.

    Only actual ttk controls have a "disabled" state; plain Tk
    Toplevel/Window objects (which have their own unrelated state()
    method, for window-manager state like "withdrawn"/"zoomed") are
    left alone but still recursed into, so e.g. disabling a window
    disables the controls inside it."""

    def disable(self) -> None:
        self._apply_state(self, "disabled")

    def enable(self) -> None:
        self._apply_state(self, "!disabled")

    @staticmethod
    def _apply_state(widget, flag: str) -> None:
        if isinstance(widget, tkttk.Widget):
            widget.state([flag])
        for child in widget.winfo_children():
            EnableDisableMixin._apply_state(child, flag)


class SnapWindow:
    """Mixin giving a Tk Toplevel/Window "snapping": _snap_to_anchor()
    positions this window to the right of an anchor widget, and any
    window registered via add_snap_follower() is kept snapped to this
    one automatically — not just when this window is shown, but any
    time it (or, transitively, its own anchor) is moved or resized, via
    the <Configure> binding set up in _init_snap().

    Windows only move together while actually snapped: dragging a
    follower away breaks it loose (detected by comparing its live
    position against where its anchor would put it), and an anchor
    moving after that no longer drags the detached window back. It
    re-snaps the next time it's explicitly shown/repositioned.

    Call _init_snap() from __init__, after the underlying Tk widget is
    constructed.

    `snap_anchor`, if given, is a zero-arg callable returning the
    widget this window should snap its left edge to the right of
    (defaults to its master). It's re-evaluated on every reposition, so
    it can return different widgets over time — e.g. "the config
    window if it's open, else the main window"."""

    def _init_snap(self, snap_anchor=None):
        self._snap_anchor = snap_anchor
        self._snap_followers = []
        self._is_snapped = False
        self.bind("<Configure>", self._on_snap_configure, add="+")

    def add_snap_follower(self, window) -> None:
        """Register `window` to be kept snapped to this one: repositioned
        whenever this window is shown, moved, or resized, as long as
        `window` is visible AND still actually snapped at the time."""
        self._snap_followers.append(window)

    def reposition(self) -> None:
        """Re-snap position without changing visibility or stealing focus."""
        self._snap_to_anchor()

    def _snap_to_anchor(self) -> None:
        anchor = self._snap_anchor() if self._snap_anchor is not None else self.master
        if anchor is None:
            return
        anchor.update_idletasks()
        x = anchor.winfo_x() + anchor.winfo_width()
        y = anchor.winfo_y()
        self.geometry(f"+{x}+{y}")
        # Set synchronously rather than waiting for the resulting
        # <Configure> event (which Tk may deliver later, or not fire
        # at all if we were already exactly at this position).
        self._is_snapped = True

    def _is_at_anchor_position(self) -> bool:
        anchor = self._snap_anchor() if self._snap_anchor is not None else self.master
        if anchor is None:
            return False
        return (
            self.winfo_x() == anchor.winfo_x() + anchor.winfo_width()
            and self.winfo_y() == anchor.winfo_y()
        )

    def _on_snap_configure(self, event=None) -> None:
        # Recomputed from live geometry (not a "did I cause this"
        # flag) so a direct user drag away from the anchor is detected
        # reliably regardless of event timing/ordering.
        self._is_snapped = self._is_at_anchor_position()
        for follower in self._snap_followers:
            if follower.is_visible() and follower._is_snapped:
                follower.reposition()


class Window(SnapWindow, EnableDisableMixin, ttk.Window):
    def __init__(self, title: str):
        super().__init__(themename="superhero", title=title)
        # Horizontal resize only — vertical layout is fixed.
        self.resizable(True, False)
        self._init_snap()


class TopLevelWindow(EnableDisableMixin, ttk.Toplevel):
    def __init__(self, title: str):
        super().__init__(title=title)


class Dialog(EnableDisableMixin, ttk.Toplevel):
    """A modal message dialog: shows `message` with a single OK
    button. Appears immediately on construction; call show() to block
    the caller until it's dismissed (OK pressed, or closed via the
    window's own close button — treated the same way), then `on_ok`
    (if given) is invoked."""

    def __init__(self, title: str, message: str, on_ok=Nop(), **kwargs):
        super().__init__(title=title, **kwargs)

        self.on_ok = on_ok

        # Fixed size — a message dialog doesn't need to be resized.
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._handle_ok)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=BOTH, expand=YES)

        label = ttk.Label(frame, text=message, wraplength=360, justify=LEFT)
        label.pack(fill=X, pady=(0, 15))

        button = ttk.Button(frame, text="OK", command=self._handle_ok, bootstyle="primary")
        button.pack()
        button.focus_set()

        self._center_on_master()

        # Modal: block interaction with other windows until closed.
        self.transient(self.master)
        self.grab_set()

    def _center_on_master(self):
        master = self.master
        if master is None:
            return
        master.update_idletasks()
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _handle_ok(self):
        self.grab_release()
        self.destroy()
        if self.on_ok is not None:
            self.on_ok()

    def show(self):
        """Block the calling code until the dialog is dismissed."""
        self.wait_window(self)


class TabbedWindow(SnapWindow, EnableDisableMixin, ttk.Toplevel):
    """A tabbed window that stays alive for the lifetime of the app;
    use show()/hide()/toggle() instead of creating/destroying it.

    See SnapWindow for snap_anchor/add_snap_follower()."""

    def __init__(self, master, on_close, title: str, snap_anchor=None, **kwargs):
        super().__init__(title=title, master=master, **kwargs)

        self.on_close = on_close
        self._init_snap(snap_anchor)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        # Intercept the window's own close (X) button: hide instead of destroy
        self.protocol("WM_DELETE_WINDOW", self.hide)

        # Horizontal resize only — vertical layout is fixed; tabs that
        # overflow it get their own scrollbar instead (see ScrollableTab).
        self.resizable(True, False)

        # Start hidden — the main app decides when to show it
        self.withdraw()

    def add_tab(self, tab: "Tab"):
        self.notebook.add(tab.notebook_widget, text=tab.title)

    def show(self):
        """Reveal the window, snapped to the right edge of its anchor
        (see snap_anchor), and bring it to the front. Reposition of
        any visible snap followers happens via the <Configure> binding
        from _init_snap()."""
        self._snap_to_anchor()
        self.deiconify()
        self.lift()
        self.focus_force()

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


class Tab(EnableDisableMixin, ttk.Frame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, padding=5, **kwargs)
        self.title = title
        # What TabbedWindow.add_tab() hands to the Notebook — plain
        # Tabs add themselves; see ScrollableTab for the alternative.
        self.notebook_widget = self


class ScrollableTab(EnableDisableMixin, ttk.scrolled.ScrolledFrame):
    """A notebook tab whose content scrolls vertically once it grows
    past its viewport height (see set_visible_height)."""

    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, padding=5, autohide=True, **kwargs)
        self.title = title
        # ScrolledFrame is itself the content frame; the Notebook must
        # be given .container instead (see the class docstring).
        self.notebook_widget = self.container

    def set_visible_height(self, height: int):
        """Clip the viewport to `height` screen units so content
        beyond it requires scrolling instead of growing the tab."""
        self.container.configure(height=height)


class MainFrame(EnableDisableMixin, ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=5, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)


class StatusLine(EnableDisableMixin, ttk.Frame):
    """A single-line status bar. Pack it before any expand=YES content
    (see MainFrame) so it claims the bottom strip first and stays
    pinned there. Update its text via set_text()."""

    def __init__(self, master, initial_text: str = "", **kwargs):
        super().__init__(master, padding=(5, 2), **kwargs)
        self.separator = ttk.Separator(self, orient=HORIZONTAL)
        self.separator.pack(fill=X, side=TOP, pady=(0, 2))
        self.value = ttk.StringVar(value=initial_text)
        self.label = ttk.Label(self, textvariable=self.value, anchor=W)
        self.label.pack(fill=X, side=LEFT, expand=YES)

    def pack(self):
        super().pack(side=BOTTOM, fill=X)

    def set_text(self, text: str):
        self.value.set(text)


class ScrolledFrame(EnableDisableMixin, ttk.scrolled.ScrolledFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=5, autohide=True, scrollheight=20, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)

class TableView(EnableDisableMixin, ttk.tableview.Tableview):
    def __init__(self, master, columns: list, rows: list, **kwargs):
        super().__init__(master, coldata=columns, rowdata=rows, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)


class EditGroupFrame(EnableDisableMixin, ttk.Labelframe):
    def __init__(self, master, name : str, **kwargs):
        super().__init__(master, text=name, padding=5, **kwargs)

    def pack(self):
        super().pack(fill=X, side=TOP)


class Spacer(EnableDisableMixin, ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=10, **kwargs)

        self.label = ttk.Label(master=master, text="", padding=2)
        self.label.pack(fill=BOTH, side=TOP)

    def pack(self):
        super().pack(fill=X, side=TOP)


class HintedWidget(EnableDisableMixin, ttk.Frame):
    """Base for widgets that show a hint (name) for their core widget.

    If compact is True, the core widget is wrapped in a Labelframe
    with the hint as its title (the old, default layout). If compact
    is False, the core widget is left bare and the hint is placed as
    a plain label to its left instead."""

    def __init__(self, master, name: str, compact: bool = True, **kwargs):
        super().__init__(master, padding=0, **kwargs)
        self.compact = compact
        if compact:
            self.container = ttk.Labelframe(self, text=name, padding=2)
            self.container.pack(side=LEFT, fill=BOTH, expand=YES)
        else:
            self.hint = ttk.Label(self, text=name)
            self.hint.pack(side=LEFT, padx=5)
            self.container = self

    def pack(self, side=LEFT):
        if side == TOP:
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, expand=YES, padx=5, fill=X)


class IntegerSpinbox(HintedWidget):
    def __init__(self, master, name : str, range : list, initial_value : int, tooltip : str, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.spinbox = ttk.Spinbox(master=self.container, from_=[range[0]], to=[range[-1]], command=self.on_event)
        self.spinbox.set(initial_value)
        self.spinbox.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.spinbox.bind("<Return>", self.on_event)
        self.spinbox.bind("<FocusOut>", self.on_event)
        ToolTip(self.spinbox, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self, event=None):
        if self.command is None:
            return
        try:
            value = int(self.spinbox.get())
        except ValueError:
            return
        self.command(value)

    def update(self, value: int):
        self.spinbox.set(value)


class FloatSpinbox(HintedWidget):
    def __init__(self, master, name : str, range : list, initial_value : float, tooltip : str, command = Nop(), compact: bool = True, increment: float = 0.01, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.spinbox = ttk.Spinbox(master=self.container, from_=range[0], to=range[-1], increment=increment, command=self.on_event)
        self.spinbox.set(initial_value)
        self.spinbox.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.spinbox.bind("<Return>", self.on_event)
        self.spinbox.bind("<FocusOut>", self.on_event)
        ToolTip(self.spinbox, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self, event=None):
        if self.command is None:
            return
        try:
            value = float(self.spinbox.get())
        except ValueError:
            return
        self.command(value)

    def update(self, value: float):
        self.spinbox.set(value)


class StringEntry(HintedWidget):
    def __init__(self, master, name : str, initial_value : str, tooltip : str, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.value = ttk.StringVar(value=initial_value)
        self.entry = ttk.Entry(master=self.container, textvariable=self.value)
        self.entry.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.entry.bind("<Return>", self.on_event)
        self.entry.bind("<FocusOut>", self.on_event)
        ToolTip(self.entry, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self, event=None):
        if self.command is not None:
            self.command(self.value.get())

    def update(self, value: str):
        self.value.set(value)


class MaskedStringEntry(HintedWidget):
    """Like StringEntry, but the entered text is shown as asterisks —
    for values like passwords that shouldn't be displayed in the
    clear."""

    def __init__(self, master, name : str, initial_value : str, tooltip : str, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.value = ttk.StringVar(value=initial_value)
        self.entry = ttk.Entry(master=self.container, textvariable=self.value, show="*")
        self.entry.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.entry.bind("<Return>", self.on_event)
        self.entry.bind("<FocusOut>", self.on_event)
        ToolTip(self.entry, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self, event=None):
        if self.command is not None:
            self.command(self.value.get())

    def update(self, value: str):
        self.value.set(value)


class StringCombobox(HintedWidget):
    def __init__(self, master, name : str, values : list, selected, tooltip : str, command = Nop(), readonly=True, compact: bool = True, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.combobox = ttk.Combobox(
            master=self.container,
            values=values,
            exportselection=False,
        )
        self.combobox.set(values[0])
        max_width = max(len(value) for value in values)
        self.combobox.configure(width=max_width+10)
        self.combobox.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.combobox.bind("<<ComboboxSelected>>", self.on_event)

        if readonly:
            self.combobox.configure(state="readonly")
        if isinstance(selected, int):
            self.combobox.current(selected)
        else:
            self.combobox.current(values.index(selected))
        ToolTip(self.combobox, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self, event=None):
        if self.command is not None:
            self.command(self.combobox.get())

    def update(self, value):
        self.combobox.set(value)

class Button(EnableDisableMixin, ttk.Frame):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, padding=2, **kwargs)

        # A button's name is shown on the button itself, so there is no
        # separate hint to reposition; compact is accepted for a
        # consistent constructor signature across widgets.
        self.compact = compact
        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)

    def set_name(self, name: str):
        self.button.configure(text=name)

    def set_tooltip(self, tooltip: str):
        ToolTip(self.button, text=tooltip)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X)

class ExpandingButton(EnableDisableMixin, ttk.Frame):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, padding=2, **kwargs)

        self.compact = compact
        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)

    def set_name(self, name: str):
        self.button.configure(text=name)

    def set_tooltip(self, tooltip: str):
        ToolTip(self.button, text=tooltip)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X, expand=True)

class CheckButton(HintedWidget):
    def __init__(self, master, name : str, tooltip : str, initial_value: bool = False, command = Nop(), compact: bool = True, **kwargs):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.value = ttk.BooleanVar(value=initial_value)
        self.button = ttk.Checkbutton(master=self.container, bootstyle="round-toggle", command=self.on_event, variable=self.value)
        self.button.pack(side=LEFT, padx=5)
        ToolTip(self.button, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def on_event(self):
        if self.command is not None:
            self.command(self.value.get())

    def off(self):
        self.value.set(False)

    def on(self):
        self.value.set(True)

    def toggle(self):
        if self.value.get():
            self.off()
        else:
            self.on()

    def pack(self, side=LEFT):
        if side == TOP:
            ttk.Frame.pack(self, side=TOP, padx=5, pady=2, fill=X)
        else:
            ttk.Frame.pack(self, side=LEFT, padx=5, fill=X)

    def update(self, value: bool):
        self.value.set(value)
