import ui.widgets as ui
import server.detect as detect
import server.name as name
#import configs.installed_servers as installed_servers

#def OnInstalledServers():
#    installed_servers_config.open_once()

def on_install_game_server(name: str):
    print(f"Installing game server for {name}...")

def install_game():
    game_frame = ui.EditGroupFrame(master=main_frame, name="No game server detected")
    game_frame.pack()

    selected_game = ui.StringCombobox(master=game_frame, name="Select a game server to install", values=name.get_all_long_names(), selected=name.get_all_long_names()[0], tooltip="Select a game server to install")
    selected_game.pack()

    install_server = ui.ExpandingButton(game_frame, name="Install game server", tooltip="Install selected game server", command=lambda: on_install_game_server(selected_game.combobox.get()))
    install_server.pack()

    spacer_at_end = ui.Spacer(master=main_frame)
    spacer_at_end.pack()

def detected_game(name: str):
    game_frame = ui.EditGroupFrame(master=main_frame, name=name)
    game_frame.pack()

    edit_configuration = ui.Button(master=game_frame, name="Config", tooltip="Edit configuration")
    edit_configuration.pack()

    # TODO: detect server status and change button name to "Stop" if server is running
    start_stop_server = ui.Button(master=game_frame, name="Start", tooltip="Start server")
    start_stop_server.pack()

    # -- spacer

    spacer_between_game_and_shortcut_frame = ui.Spacer(master=main_frame)
    spacer_between_game_and_shortcut_frame.pack()

    # -- shortcut frame

    shortcut_frame = ui.EditGroupFrame(master=main_frame, name="Shortcuts")
    shortcut_frame.pack()

    game_mode = ui.StringCombobox(master=shortcut_frame, name="Game mode", values=(r"Deathmatch", r"Gungame", r"Casual"), selected=2, tooltip="Selected game mode")
    game_mode.pack()

    map_group = ui.StringCombobox(master=shortcut_frame, name="Map group", values=(r"Mapgroup-1", r"Mapgroup-2", r"Mapgroup-3"), selected=1, tooltip="Selected map group")
    map_group.pack()

    map = ui.StringCombobox(master=shortcut_frame, name="Map", values=(r"Map-1", r"Map-2", r"Map-3"), selected=r"Map-3", tooltip="Selected map within selected game mode")
    map.pack()

    player_count = ui.IntegerSpinbox(master=shortcut_frame, name="Player count", range=(1,64), initial_value=5, tooltip="Number of players on server")
    player_count.pack()

    spacer_at_end = ui.Spacer(master=main_frame)
    spacer_at_end.pack()

# main

root = ui.Window(title="sgsl 0.1")

#installed_servers_config = installed_servers.ConfigPage()

main_frame = ui.MainFrame(master=root)
main_frame.pack()

detected_game = detect.detect()

if detected_game == "":
    install_game()
elif name.is_valid_short_name(detected_game):
    detected_game(name.long_name(detected_game))
else:
    exit(1)

root.mainloop()

#installed_servers_config.close()