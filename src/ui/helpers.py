import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip


class EditItemFrame(ttk.LabelFrame):
    def __init__(self, master, name : str, **kwargs):
        super().__init__(master, text=name, padding=10, **kwargs)

        self.labelframe = ttk.LabelFrame(master=master, text=name, padding=10)

    def pack(self):
        self.frame.pack(fill=X, side=TOP)