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
    def __init__(self, master, name : str, range : list, initial_value : int, tooltip : str, **kwargs):
        super().__init__(master, text=name, padding=2, **kwargs)

        self.spinbox = ttk.Spinbox(master=self, from_=[range[0]], to=[range[-1]])
        self.spinbox.set(initial_value)
        self.spinbox.pack(side=LEFT, expand=YES, padx=5, fill=X)
        ToolTip(self.spinbox, text=tooltip)
        self.spinbox.pack(fill=BOTH, side=TOP)

    def pack(self):
        super().pack(fill=X, side=TOP)


class StringCombobox(ttk.Labelframe):
    def __init__(self, master, name : str, values : list, selected, tooltip : str, command = Nop(), readonly=True, **kwargs):
        super().__init__(master, text=name, padding=2, **kwargs)

        self.combobox = ttk.Combobox(
            master=self,
            values=values,
            exportselection=False,
        )
        self.combobox.set(values[0])
        max_width = max(len(value) for value in values)
        self.combobox.configure(width=max_width+10)
        self.combobox.pack(side=LEFT, expand=YES, padx=5, fill=X)

        if readonly:
            self.combobox.configure(state="readonly")
        if isinstance(selected, int):
            self.combobox.current(selected)
        else:
            self.combobox.current(values.index(selected))
        ToolTip(self.combobox, text=tooltip)
        self.combobox.pack(fill=BOTH, side=TOP)

    def pack(self):
        super().pack(side=LEFT, expand=YES, padx=5, fill=X)

class Button(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)
        self.button.pack(side=TOP)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X)

class ExpandingButton(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.button = ttk.Button(master=self, text=name, command=command)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)
        self.button.pack(side=TOP)

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X, expand=True)

class CheckButton(ttk.Labelframe):
    def __init__(self, master, name : str, tooltip : str, initial_value: bool = False, command = Nop(), **kwargs):
        super().__init__(master, borderwidth=0, padding=2, **kwargs)

        self.value = ttk.BooleanVar(value=initial_value)    
        self.button = ttk.Checkbutton(master=self, bootstyle="round-toggle", text=name, command=command, variable=self.value)
        self.button.pack(side=LEFT, padx=5, fill=X)
        ToolTip(self.button, text=tooltip)
        self.button.pack(side=TOP)

    def off(self):
        self.value.set(False)

    def on(self):
        self.value.set(True)

    def toggle(self):
        if self.value.get():
            self.off()
        else:
            self.on()

    def pack(self):
        super().pack(side=LEFT, padx=5, fill=X)
