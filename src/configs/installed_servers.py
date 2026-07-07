import ui.widgets as ui

class ConfigPage:
    def __init__(self):
        self.opened=False
        self.w=None

    def open_once(self):
        if not self.opened:
            self.opened=True
            self.w = ui.TopLevelWindow(title="Installed servers")

            self.server_list = ui.TableView(self.w, columns=("Name", "Location", "Type"), rows=(("Server-1", "c:\windows\server-1", "client"),("Server-2", "c:\windows\server-2", "steamcmd"),("Server-3", "c:\windows\server-3", "client")))
            self.server_list.pack()

            self.w.mainloop()
            self.opened=False
        else:
            self.close()

    def add_data(self, line: list):
            self.server_list.insert_row(line)

    def close(self):
        if self.opened:
            self.opened=False
            self.w.destroy()
