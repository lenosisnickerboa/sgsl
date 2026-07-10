import os
import sys
from pathlib import Path
from config.config_item import ConfigItem, ConfigType
from config.toml_config import Config, TomlConfigParser
from app.version import VERSION
import ui.widgets as ui
import ui.terminal as terminal
from game.game import Game
from game.game_factory import GameFactory
from app.config_index import ConfigIndex

g_main_frame = None
g_terminal_window = None
g_terminal_is_open = False
g_terminal_open_close = None
g_start_stop_server = None
g_config_default = None
g_app_config = None

def build_app_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.TERMINAL_ENABLED: ConfigItem(
            name="terminal_enable",
            visible_name="Enable terminal",
            type=ConfigType.BOOLEAN,
            value=False,
        ),
    }

def get_server_binary_path(dir: str) -> str:
    return str(game.cs2.runner.get(dir))

def is_terminal_open() -> bool:
    global g_terminal_is_open
    return g_terminal_is_open

def print_to_terminal(line: str):
    g_terminal_window.add_line(f"{line}")

def on_install_game_server(name: str):
    print_to_terminal(f"Installing game server for {name}...")
    game = GameFactory.create_from_name(name, current_dir, terminal_printer)
    if game:
        game.install()

def install_game_server(dir: str, name: str):
    print_to_terminal(f"Installing game server for {name} in directory {dir}...")

def on_start_stop_game_server(game: Game):
    global g_start_stop_server

    if not game.is_running():
        game.run()
        g_start_stop_server.set_name(name="Stop")
        g_start_stop_server.set_tooltip(tooltip="Stop server")
    else:
        game.stop()
        g_start_stop_server.set_name(name="Start")
        g_start_stop_server.set_tooltip(tooltip="Start server")

def on_toggle_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = not g_terminal_is_open
    g_terminal_window.toggle()

def setup_install_game(dir: str):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name="No game server detected")
    game_frame.pack()

    all_games = GameFactory.games()
    selected_game = ui.StringCombobox(master=game_frame, name="Select a game server to install", values=all_games, selected=all_games[0], tooltip="Select a game server to install")
    selected_game.pack()

    install_server = ui.ExpandingButton(game_frame, name="Install game server", tooltip="Install selected game server", command=lambda: on_install_game_server(selected_game.combobox.get()))
    install_server.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda: on_toggle_terminal_window())
    g_terminal_open_close.pack()

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def setup_detected_game_server(game: Game):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name=game.get_long_name())
    game_frame.pack()

    edit_configuration = ui.Button(master=game_frame, name="Configure", tooltip="Edit game server configuration")
    edit_configuration.pack()

    global g_start_stop_server
    if game.is_running():
        g_start_stop_server = ui.Button(master=game_frame, name="Stop", tooltip="Stop server", command=lambda: on_start_stop_game_server(game))
    else:
        g_start_stop_server = ui.Button(master=game_frame, name="Start", tooltip="Start server", command=lambda: on_start_stop_game_server(game))
    g_start_stop_server.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda: on_toggle_terminal_window())
    g_terminal_open_close.pack()

    # -- spacer

    spacer_between_game_and_shortcut_frame = ui.Spacer(master=g_main_frame)
    spacer_between_game_and_shortcut_frame.pack()

    # -- shortcut frame

    shortcut_frame = ui.EditGroupFrame(master=g_main_frame, name="Shortcuts")
    shortcut_frame.pack()

    game_mode = ui.StringCombobox(master=shortcut_frame, name="Game mode", values=(r"Deathmatch", r"Gungame", r"Casual"), selected=2, tooltip="Selected game mode")
    game_mode.pack()

#    map_group = ui.StringCombobox(master=shortcut_frame, name="Map group", values=(r"Mapgroup-1", r"Mapgroup-2", r"Mapgroup-3"), selected=1, tooltip="Selected map group")
#    map_group.pack()

    maps = game.maps()
    map = ui.StringCombobox(master=shortcut_frame, name="Map", values=maps, selected=maps[0], tooltip="Selected map within selected game mode")
    map.pack()

    player_count = ui.IntegerSpinbox(master=shortcut_frame, name="Player count", range=(1,64), initial_value=5, tooltip="Number of players on server")
    player_count.pack()

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def on_close_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = False
    g_terminal_open_close.off()

# main

root = ui.Window(title="Simple Game Server Launcher" + " " + VERSION)

g_terminal_window = terminal.TerminalWindow(root, on_close_terminal_window, title="Log Output")

g_main_frame = ui.MainFrame(master=root)
g_main_frame.pack()

current_dir = os.getcwd()

app_config_file = Path(current_dir) / "sgsl.toml"
g_app_config = TomlConfigParser.read(app_config_file, build_app_defaults())

terminal_printer = lambda line: g_terminal_window.add_line(line)
game = GameFactory.create(current_dir, terminal_printer)

if game is None:
    setup_install_game(current_dir)
else:
    setup_detected_game_server(game)

TomlConfigParser.write(app_config_file, g_app_config)

root.mainloop()
