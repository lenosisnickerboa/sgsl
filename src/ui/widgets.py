import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.tableview import Tableview
import ui.helpers as helpers

def Nop():
    pass

class Window(ttk.Window):
    def __init__(self, title: str):
        super().__init__(themename="superhero", title=title)
        # Horizontal resize only — vertical layout is fixed.
        self.resizable(True, False)


class TopLevelWindow(ttk.Toplevel):
    def __init__(self, title: str):
        super().__init__(title=title)


class TabbedWindow(ttk.Toplevel):
    """A tabbed window that stays alive for the lifetime of the app;
    use show()/hide()/toggle() instead of creating/destroying it."""

    def __init__(self, master, on_close, title: str, **kwargs):
        super().__init__(title=title, master=master, **kwargs)

        self.on_close = on_close
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
        """Reveal the window and bring it to the front."""
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


class Tab(ttk.Frame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, padding=5, **kwargs)
        self.title = title
        # What TabbedWindow.add_tab() hands to the Notebook — plain
        # Tabs add themselves; see ScrollableTab for the alternative.
        self.notebook_widget = self


class ScrollableTab(ttk.scrolled.ScrolledFrame):
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


class MainFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=5, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)


class ScrolledFrame(ttk.scrolled.ScrolledFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=5, autohide=True, scrollheight=20, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)

class TableView(ttk.tableview.Tableview):
    def __init__(self, master, columns: list, rows: list, **kwargs):
        super().__init__(master, coldata=columns, rowdata=rows, **kwargs)

    def pack(self):
        super().pack(side=LEFT, fill=BOTH, expand=YES)


class EditGroupFrame(ttk.Labelframe):
    def __init__(self, master, name : str, **kwargs):
        super().__init__(master, text=name, padding=5, **kwargs)

    def pack(self):
        super().pack(fill=X, side=TOP)


class Spacer(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=10, **kwargs)

        self.label = ttk.Label(master=master, text="", padding=2)
        self.label.pack(fill=BOTH, side=TOP)

    def pack(self):
        super().pack(fill=X, side=TOP)


class HintedWidget(ttk.Frame):
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

class Button(ttk.Frame):
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

class ExpandingButton(ttk.Frame):
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
