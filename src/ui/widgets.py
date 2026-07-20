from typing import Optional

import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as tkttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.tableview import Tableview
import ui.helpers as helpers
from app.resources import resource_path


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

    def set_read_only(self, read_only: bool) -> None:
        """Make this widget display-only, with no way to edit its
        value. The default is the same as disable()/enable(); widgets
        that need to stay partially interactive while read-only (e.g.
        ArrayEditor, whose list should stay scrollable) override this."""
        if read_only:
            self.disable()
        else:
            self.enable()

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

    While loose, dragging it close to another SnapWindow's right edge
    (within _DragSnapThreshold pixels on both axes) snaps it flush
    against that edge and adopts that window as its new anchor going
    forward — the same "drag it away, it stays put; move the anchor,
    it follows" relationship as the app's built-in anchor chain, just
    established ad hoc instead of at construction time. See
    _try_drag_snap().

    Call _init_snap() from __init__, after the underlying Tk widget is
    constructed.

    `snap_anchor`, if given, is a zero-arg callable returning the
    widget this window should snap its left edge to the right of
    (defaults to its master). It's re-evaluated on every reposition, so
    it can return different widgets over time — e.g. "the config
    window if it's open, else the main window".

    `enabled` is a class-level, app-wide on/off switch (not per-
    instance): set SnapWindow.enabled = False to turn snapping off
    everywhere — windows stay wherever they are/get placed and no
    longer reposition or drag each other."""

    enabled = True

    # Dragging a loose window's left edge within this many pixels of
    # another SnapWindow's right edge (on both x and y) triggers an
    # ad-hoc snap — see _try_drag_snap().
    _DragSnapThreshold = 20

    # Every live SnapWindow instance, used by _try_drag_snap() to find
    # a candidate to snap to; added in _init_snap(), dropped again in
    # _on_snap_destroy() once the underlying widget is destroyed.
    _all_windows: list = []

    def _init_snap(self, snap_anchor=None):
        self._snap_anchor = snap_anchor
        self._snap_followers = []
        self._is_snapped = False
        self._current_anchor = None
        SnapWindow._all_windows.append(self)
        self.bind("<Configure>", self._on_snap_configure, add="+")
        self.bind("<Destroy>", self._on_snap_destroy, add="+")

    def _on_snap_destroy(self, event=None) -> None:
        if self in SnapWindow._all_windows:
            SnapWindow._all_windows.remove(self)

    def is_visible(self) -> bool:
        """Default for windows that don't already have their own
        (e.g. the app's single root Window, which is never withdrawn)."""
        return self.state() != "withdrawn"

    def add_snap_follower(self, window) -> None:
        """Register `window` to be kept snapped to this one: repositioned
        whenever this window is shown, moved, or resized, as long as
        `window` is visible AND still actually snapped at the time."""
        self._snap_followers.append(window)

    def reposition(self) -> None:
        """Re-snap position without changing visibility or stealing focus."""
        self._snap_to_anchor()

    def _snap_to_anchor(self) -> None:
        if not SnapWindow.enabled:
            return
        anchor = self._snap_anchor() if self._snap_anchor is not None else self.master
        if anchor is None:
            return
        # update_idletasks() alone isn't enough for an anchor that was
        # just deiconified for the first time: its final decorated size
        # isn't known until the window manager actually maps it, which
        # only a full update() (processing that Map/Configure event,
        # not just idle tasks) guarantees — otherwise winfo_width() can
        # still read a stale/default value (e.g. 1px), landing this
        # window right on top of the anchor instead of beside it.
        anchor.update()
        x = anchor.winfo_x() + anchor.winfo_width()
        y = anchor.winfo_y()
        self.geometry(f"+{x}+{y}")
        # Set synchronously rather than waiting for the resulting
        # <Configure> event (which Tk may deliver later, or not fire
        # at all if we were already exactly at this position).
        self._is_snapped = True
        self._current_anchor = anchor

    def _is_at_anchor_position(self) -> bool:
        anchor = self._snap_anchor() if self._snap_anchor is not None else self.master
        if anchor is None:
            return False
        return (
            self.winfo_x() == anchor.winfo_x() + anchor.winfo_width()
            and self.winfo_y() == anchor.winfo_y()
        )

    def _try_drag_snap(self) -> None:
        """Called while this window is loose (not snapped to its
        configured anchor). If it's now close to another window's
        right edge, snap flush against it and make that window this
        one's new anchor from now on, detaching from whatever anchor
        it had before."""
        x, y = self.winfo_x(), self.winfo_y()
        for other in SnapWindow._all_windows:
            if other is self or other in self._snap_followers:
                continue
            if not other.is_visible():
                continue
            other_right_edge = other.winfo_x() + other.winfo_width()
            if (
                abs(x - other_right_edge) <= self._DragSnapThreshold
                and abs(y - other.winfo_y()) <= self._DragSnapThreshold
            ):
                if (
                    self._current_anchor is not None
                    and self in self._current_anchor._snap_followers
                ):
                    self._current_anchor._snap_followers.remove(self)
                self._snap_anchor = lambda anchor=other: anchor
                other.add_snap_follower(self)
                self._snap_to_anchor()
                return

    def _on_snap_configure(self, event=None) -> None:
        if not SnapWindow.enabled:
            return
        # Recomputed from live geometry (not a "did I cause this"
        # flag) so a direct user drag away from the anchor is detected
        # reliably regardless of event timing/ordering.
        self._is_snapped = self._is_at_anchor_position()
        # Only a *visible* window can plausibly be the target of a user
        # drag — without this guard, the geometry churn a window goes
        # through while still withdrawn (initial construction, widgets
        # being packed, its very first _snap_to_anchor() before
        # deiconify()) can spuriously land it within the threshold of
        # some other window and permanently hijack its snap_anchor
        # before it's ever actually shown.
        if not self._is_snapped and self.is_visible():
            self._try_drag_snap()
        self.notify_snap_followers()

    def notify_snap_followers(self) -> None:
        """Re-snap every visible, still-actually-snapped follower.
        <Configure> covers this automatically while this window is
        moved/resized, but withdraw() fires no <Configure> at all — so
        subclasses must call this explicitly after hiding themselves,
        or a follower dynamically anchored to "me, if visible, else
        something else" would never learn it should fall back."""
        for follower in self._snap_followers:
            if follower.is_visible() and follower._is_snapped:
                follower.reposition()


class Window(SnapWindow, EnableDisableMixin, ttk.Window):
    def __init__(self, title: str):
        super().__init__(themename="superhero", title=title)
        # Horizontal resize only — vertical layout is fixed.
        self.resizable(True, False)
        self._init_snap()

        # No -default here: ttkbootstrap's own __init__ above already
        # gave this window an icon via iconphoto(), so iconbitmap()
        # must be called plainly to actually override it -- -default
        # only supplies a fallback for windows that don't have an icon
        # yet, which this one, at this point, already does. Swap
        # app/assets/icon.ico to customize.
        icon_path = resource_path("app/assets/icon.ico")
        try:
            self.iconbitmap(str(icon_path))
        except tk.TclError as e:
            print(f"Could not load application icon from {icon_path}: {e}")

    def center_on_screen(self):
        """Center the window on the screen. Call once all of the
        window's contents have been added — winfo_width()/height()
        need the real final size to center correctly, not whatever
        placeholder size exists right after construction."""
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


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

        button = ttk.Button(
            frame, text="OK", command=self._handle_ok, bootstyle="primary"
        )
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


class EditStringDialog(EnableDisableMixin, ttk.Toplevel):
    """A modal dialog for editing a single string: shows `title`, an
    Entry pre-filled with `value`, and OK/Cancel buttons. Appears
    immediately on construction; call show() to block the caller until
    it's dismissed, returning the edited string if OK was pressed, or
    None if Cancel was pressed (or the window closed via its own close
    button, treated the same as Cancel)."""

    def __init__(self, title: str, value: str, **kwargs):
        super().__init__(title=title, **kwargs)

        self._result: Optional[str] = None

        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._handle_cancel)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=BOTH, expand=YES)

        self.value_var = ttk.StringVar(value=value)
        entry = ttk.Entry(frame, textvariable=self.value_var)
        # Entry's `width` is in units of its font's "0" character, not
        # raw character count — with the proportional font used here,
        # len(value) undercounts and clips the text, so measure actual
        # pixel width instead.
        entry_font = tkfont.nametofont(str(entry.cget("font")))
        char_width = entry_font.measure("0")
        text_width = -(-entry_font.measure(value) // char_width)  # ceil div
        entry.configure(width=min(max(text_width, 1), 200))
        entry.pack(fill=X, pady=(0, 15))
        entry.bind("<Return>", lambda _event: self._handle_ok())
        entry.icursor(END)
        entry.focus_set()

        button_row = ttk.Frame(frame)
        button_row.pack()

        ok_button = ttk.Button(
            button_row, text="OK", command=self._handle_ok, bootstyle="primary"
        )
        ok_button.pack(side=LEFT, padx=(0, 5))

        cancel_button = ttk.Button(
            button_row, text="Cancel", command=self._handle_cancel
        )
        cancel_button.pack(side=LEFT)

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
        self._result = self.value_var.get()
        self.grab_release()
        self.destroy()

    def _handle_cancel(self):
        self._result = None
        self.grab_release()
        self.destroy()

    def show(self) -> Optional[str]:
        """Block the calling code until the dialog is dismissed, then
        return the edited string (OK) or None (Cancel/closed)."""
        self.wait_window(self)
        return self._result


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
        # withdraw() fires no <Configure>, so a follower dynamically
        # anchored to "me, if visible, else something else" (e.g. the
        # terminal window falling back to the main window once this
        # config window closes) would otherwise never reposition.
        self.notify_snap_followers()
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


class Frame(EnableDisableMixin, ttk.Frame):
    """A plain, unstyled container frame with no layout opinion of its
    own — useful for grouping a handful of widgets so they can be
    packed/anchored together as a single unit (e.g. right-aligning a
    row of buttons within a wider frame)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

    def pack(self, side=LEFT):
        super().pack(side=side)


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
    def __init__(self, master, name: str, **kwargs):
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
            # The hint label sits in its own fixed-size wrapper frame
            # rather than relying on ttk.Label's own `width` option:
            # that's measured in units of the "0" glyph's pixel width,
            # not the actual text's, and can badly underestimate the
            # space real text needs (clipping it) — see
            # set_hint_width(), which sizes this frame in real pixels
            # instead, measured the same way winfo_width() is.
            self.hint_frame = ttk.Frame(self)
            self.hint = ttk.Label(self.hint_frame, text=name, anchor=W)
            self.hint.pack(fill=BOTH, expand=YES)
            # Force Tk to actually compute the label's natural size
            # before freezing hint_frame at it — pack_propagate(False)
            # freezes whatever the *currently computed* request is,
            # which without this is still an unset placeholder (Tk
            # only computes it lazily), collapsing the frame to ~0.
            self.hint_frame.update_idletasks()
            self._hint_natural_height = self.hint_frame.winfo_reqheight()
            self.hint_frame.pack_propagate(False)
            self.hint_frame.pack(side=LEFT, padx=5)
            self.container = self

    def set_hint_width(self, pixel_width: int) -> None:
        """Fix the hint label's column to `pixel_width` screen units,
        e.g. so a UI builder can align several widgets' hints to the
        same width without clipping any of their text. No-op for
        compact widgets, which have no separate hint label.

        Also re-asserts height explicitly: once pack_propagate(False)
        is set, configuring only `width` makes Tk stop treating the
        untouched `height` as "auto" too, collapsing it toward zero —
        so it has to be pinned every time width is."""
        if hasattr(self, "hint_frame"):
            self.hint_frame.configure(width=pixel_width, height=self._hint_natural_height)

    def pack(self, side=LEFT):
        if side == TOP:
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, expand=YES, padx=5, fill=X)


class IntegerSpinbox(HintedWidget):
    def __init__(
        self,
        master,
        name: str,
        range: list,
        initial_value: int,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.spinbox = ttk.Spinbox(
            master=self.container,
            from_=[range[0]],
            to=[range[-1]],
            command=self.on_event,
        )
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
    def __init__(
        self,
        master,
        name: str,
        range: list,
        initial_value: float,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        increment: float = 0.01,
        **kwargs,
    ):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.spinbox = ttk.Spinbox(
            master=self.container,
            from_=range[0],
            to=range[-1],
            increment=increment,
            command=self.on_event,
        )
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
    def __init__(
        self,
        master,
        name: str,
        initial_value: str,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
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

    def __init__(
        self,
        master,
        name: str,
        initial_value: str,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
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
    def __init__(
        self,
        master,
        name: str,
        values: list,
        selected,
        tooltip: str,
        command=Nop(),
        readonly=True,
        compact: bool = True,
        **kwargs,
    ):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.combobox = ttk.Combobox(
            master=self.container,
            values=values,
            exportselection=False,
        )
        self.combobox.set(values[0])
        max_width = max(len(value) for value in values)
        self.combobox.configure(width=max_width + 10)
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

    def set_values(self, values: list) -> None:
        """Refresh the dropdown's choices — e.g. when another config
        item defines this one's allowed set, like a list of available
        maps. If the current selection is no longer among `values`,
        falls back to the first of the new values."""
        self.combobox.configure(values=values)
        if values and self.combobox.get() not in values:
            self.combobox.set(values[0])


class ArrayEditor(HintedWidget):
    """Edits a list of scalar values (a TOML array config item): the
    current items sit in a listbox, with an entry + Add button to
    append new ones and a Remove button to delete the selected one.
    `item_type` (a plain Python type, e.g. str/int/float) is used to
    parse text typed into the Add entry — see ConfigItem.item_type."""

    def __init__(
        self,
        master,
        name: str,
        initial_value: list,
        tooltip: str,
        command=Nop(),
        item_type=str,
        compact: bool = True,
        **kwargs,
    ):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.item_type = item_type

        listbox_row = ttk.Frame(self.container)
        listbox_row.pack(side=TOP, fill=BOTH, expand=YES, padx=5, pady=(2, 0))

        self.listbox = tk.Listbox(listbox_row, height=5, exportselection=False)
        self.listbox.pack(side=LEFT, fill=BOTH, expand=YES)
        for value in initial_value:
            self.listbox.insert(END, str(value))

        self.scrollbar = ttk.Scrollbar(
            listbox_row, orient=VERTICAL, command=self.listbox.yview
        )
        self.scrollbar.pack(side=LEFT, fill=Y)
        self.listbox.configure(yscrollcommand=self.scrollbar.set)

        entry_row = ttk.Frame(self.container)
        entry_row.pack(side=TOP, fill=X, padx=5, pady=2)

        self.new_value = ttk.StringVar()
        self.entry = ttk.Entry(entry_row, textvariable=self.new_value)
        self.entry.pack(side=LEFT, fill=X, expand=YES)
        self.entry.bind("<Return>", self._on_add)

        self.add_button = ttk.Button(entry_row, text="Add", command=self._on_add)
        self.add_button.pack(side=LEFT, padx=(5, 0))

        self.remove_button = ttk.Button(
            entry_row, text="Remove", command=self._on_remove
        )
        self.remove_button.pack(side=LEFT, padx=(5, 0))

        ToolTip(self.listbox, text=tooltip)
        if not compact:
            ToolTip(self.hint, text=tooltip)

    def _on_add(self, event=None):
        text = self.new_value.get().strip()
        if not text:
            return
        try:
            value = self.item_type(text)
        except (TypeError, ValueError):
            return
        self.listbox.insert(END, str(value))
        self.new_value.set("")
        self._notify()

    def _on_remove(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        self.listbox.delete(selection[0])
        self._notify()

    def _notify(self):
        if self.command is not None:
            self.command(self.values())

    def values(self) -> list:
        return [self.item_type(v) for v in self.listbox.get(0, END)]

    def update(self, value: list):
        self.listbox.delete(0, END)
        for v in value:
            self.listbox.insert(END, str(v))

    def set_read_only(self, read_only: bool) -> None:
        # The listbox/scrollbar stay enabled so the list is still
        # scrollable — only the controls that add/remove items are
        # disabled.
        flag = "disabled" if read_only else "!disabled"
        self._apply_state(self.entry, flag)
        self._apply_state(self.add_button, flag)
        self._apply_state(self.remove_button, flag)


class Button(EnableDisableMixin, ttk.Frame):
    def __init__(
        self,
        master,
        name: str,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
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
    def __init__(
        self,
        master,
        name: str,
        tooltip: str,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
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
    def __init__(
        self,
        master,
        name: str,
        tooltip: str,
        initial_value: bool = False,
        command=Nop(),
        compact: bool = True,
        **kwargs,
    ):
        super().__init__(master, name=name, compact=compact, **kwargs)

        self.command = command
        self.value = ttk.BooleanVar(value=initial_value)
        self.button = ttk.Checkbutton(
            master=self.container,
            bootstyle="round-toggle",
            command=self.on_event,
            variable=self.value,
        )
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
