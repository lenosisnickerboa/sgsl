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

        # Start hidden — the main app decides when to show it
        self.withdraw()

    def add_tab(self, tab: "Tab"):
        self.notebook.add(tab, text=tab.title)

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


class IntegerSpinbox(ttk.Labelframe):
    def __init__(self, master, name : str, range : list, initial_value : int, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, text=name, padding=2, **kwargs)

        self.command = command
        self.spinbox = ttk.Spinbox(master=self, from_=[range[0]], to=[range[-1]], command=self.on_event)
        self.spinbox.set(initial_value)
        self.spinbox.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.spinbox.bind("<Return>", self.on_event)
        self.spinbox.bind("<FocusOut>", self.on_event)
        ToolTip(self.spinbox, text=tooltip)
        self.spinbox.pack(fill=BOTH, side=TOP)

    def on_event(self, event=None):
        if self.command is None:
            return
        try:
            value = int(self.spinbox.get())
        except ValueError:
            return
        self.command(value)

    def pack(self, side=LEFT):
        if side == TOP:
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, expand=YES, padx=5, fill=X)

    def update(self, value: int):
        self.spinbox.set(value)


class StringEntry(ttk.Labelframe):
    def __init__(self, master, name : str, initial_value : str, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, text=name, padding=2, **kwargs)

        self.command = command
        self.value = ttk.StringVar(value=initial_value)
        self.entry = ttk.Entry(master=self, textvariable=self.value)
        self.entry.pack(side=LEFT, expand=YES, padx=5, fill=X)
        self.entry.bind("<Return>", self.on_event)
        self.entry.bind("<FocusOut>", self.on_event)
        ToolTip(self.entry, text=tooltip)

    def on_event(self, event=None):
        if self.command is not None:
            self.command(self.value.get())

    def pack(self, side=LEFT):
        if side == TOP:
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, expand=YES, padx=5, fill=X)

    def update(self, value: str):
        self.value.set(value)


class StringCombobox(ttk.Labelframe):
    def __init__(self, master, name : str, values : list, selected, tooltip : str, command = Nop(), readonly=True, **kwargs):
        super().__init__(master, text=name, padding=2, **kwargs)

        self.command = command
        self.combobox = ttk.Combobox(
            master=self,
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
        self.combobox.pack(fill=BOTH, side=TOP)

    def on_event(self, event=None):
        if self.command is not None:
            self.command(self.combobox.get())

    def pack(self, side=LEFT):
        if side == TOP:
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, expand=YES, padx=5, fill=X)

    def update(self, value):
        self.combobox.set(value)

class Button(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)
        self.button.pack(side=TOP)

    def set_name(self, name: str):
        self.button.configure(text=name)

    def set_tooltip(self, tooltip: str):
        ToolTip(self.button, text=tooltip)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X)

class ExpandingButton(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)
        self.button.pack(side=TOP)

    def set_name(self, name: str):
        self.button.configure(text=name)

    def set_tooltip(self, tooltip: str):
        ToolTip(self.button, text=tooltip)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X, expand=True)

class CheckButton(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, initial_value: bool = False, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.command = command
        self.value = ttk.BooleanVar(value=initial_value)
        self.label = ttk.Label(master=self, text=name)
        self.label.pack(side=LEFT, padx=5)
        self.button = ttk.Checkbutton(master=self, bootstyle="round-toggle", command=self.on_event, variable=self.value)
        self.button.pack(side=LEFT, padx=5)
        ToolTip(self.label, text=tooltip)
        ToolTip(self.button, text=tooltip)

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
            super().pack(side=TOP, padx=5, pady=2, fill=X)
        else:
            super().pack(side=LEFT, padx=5, fill=X)

    def update(self, value: bool):
        self.value.set(value)
