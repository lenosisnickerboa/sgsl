import os
from pathlib import Path
from config.config_item import ConfigItem, ConfigType
from config.toml_config import Config, TomlConfigParser
from app.version import VERSION
import ui.widgets as ui
import ui.terminal as terminal
from game.game import Game
from game.game_factory import GameFactory
from app.config_index import ConfigIndex
from ui_builder.ui_builder import UiBuilder

g_main_frame = None
g_terminal_window = None
g_terminal_is_open = False
g_terminal_open_close = None
g_configure_window = None
g_configure_is_open = False
g_configure_open_close = None
g_install_open_close = None
g_update_open_close = None
g_start_stop_server = None
g_config_default = None
g_app_config = None
g_app_config_file = None
g_game_config = None
g_game_config_file = None
g_ui_builder = None

def build_app_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.TERMINAL_ENABLED: ConfigItem(
            name="terminal_enable",
            visible_name="Enable terminal",
            type=ConfigType.BOOLEAN,
            value=False,
        ),
    }

def print_to_terminal(line: str):
    g_terminal_window.add_line(f"{line}")

def on_install_game_server(name: str):
    print_to_terminal(f"Installing game server for {name}...")
    game = GameFactory.create_from_name(name, current_dir, terminal_printer)
    if not game:
        root.after(0, g_install_open_close.off)
        return

    def on_install_result(result):
        print_to_terminal(f"Install for {game.get_long_name()} finished: {result}")
        root.after(0, g_install_open_close.off)

    game.install(on_install_result)

def on_update_game_server(game: Game):
    print_to_terminal(f"Updating game server for {game.get_long_name()} in directory {game.get_directory()}...")

    def on_update_result(result):
        print_to_terminal(f"Update for {game.get_long_name()} finished: {result}")
        root.after(0, g_update_open_close.off)

    game.update(on_update_result)

def on_toggle_configure_window():
    global g_configure_is_open
    g_configure_is_open = not g_configure_is_open
    g_configure_window.toggle()

def on_start_stop_game_server(game: Game):
    global g_start_stop_server

    if not game.is_running():
        global g_game_config
        game.run(g_game_config)
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

    global g_install_open_close
    g_install_open_close = ui.CheckButton(master=game_frame, name="Install game server", tooltip="Install selected game server", command=lambda value: on_install_game_server(selected_game.combobox.get()) if value else None)
    g_install_open_close.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda _value: on_toggle_terminal_window())
    g_terminal_open_close.pack()

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def setup_detected_game_server(game: Game):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name=game.get_long_name())
    game_frame.pack()

    global g_start_stop_server
    if game.is_running():
        g_start_stop_server = ui.Button(master=game_frame, name="Stop", tooltip="Stop server", command=lambda: on_start_stop_game_server(game))
    else:
        g_start_stop_server = ui.Button(master=game_frame, name="Start", tooltip="Start server", command=lambda: on_start_stop_game_server(game))
    g_start_stop_server.pack()

    global g_update_open_close
    g_update_open_close = ui.CheckButton(master=game_frame, name="Update", tooltip="Update game server", command=lambda value: on_update_game_server(game) if value else None)
    g_update_open_close.pack()

    global g_configure_open_close
    g_configure_open_close = ui.CheckButton(master=game_frame, name="Configure", tooltip="Edit game server configuration", command=lambda _value: on_toggle_configure_window())
    g_configure_open_close.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda _value: on_toggle_terminal_window())
    g_terminal_open_close.pack()

    # -- spacer

    spacer_between_game_and_shortcut_frame = ui.Spacer(master=g_main_frame)
    spacer_between_game_and_shortcut_frame.pack()

    # -- shortcut frame

    shortcut_frame = ui.EditGroupFrame(master=g_main_frame, name="Shortcuts")
    shortcut_frame.pack()

    global g_game_config
    global g_game_config_file
    g_game_config_file = game.get_directory() / "game.toml"
    g_game_config = TomlConfigParser.read(g_game_config_file, game.config_defaults())

    def on_config_item_changed(config_item, config):
        game.config_item_changed(config_item, config)

    global g_ui_builder
    g_ui_builder = UiBuilder()
    g_ui_builder.build_shortcuts(shortcut_frame, game.config_shortcuts(), g_game_config, on_config_item_changed)

    global g_configure_window
    g_configure_window = g_ui_builder.build_configuration_window(
        root,
        on_close_configure_window,
        f"Configure {game.get_long_name()}",
        game.config_tabs(),
        g_game_config,
        on_config_item_changed,
    )
    # Keep an already-open terminal window snapped to the config
    # window whenever the config window (re)opens.
    g_configure_window.add_snap_follower(g_terminal_window)

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def on_close_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = False
    g_terminal_open_close.off()

def on_close_configure_window():
    global g_configure_is_open
    g_configure_is_open = False
    g_configure_open_close.off()

# main

root = ui.Window(title="Simple Game Server Launcher" + " " + VERSION)

g_terminal_window = terminal.TerminalWindow(
    root,
    on_close_terminal_window,
    title="Log Output",
    # Snap onto the config window if it's open, else the main window.
    snap_anchor=lambda: g_configure_window if g_configure_window is not None and g_configure_window.is_visible() else root,
)

g_main_frame = ui.MainFrame(master=root)
g_main_frame.pack()

current_dir = os.getcwd()

g_app_config_file = Path(current_dir) / "sgsl.toml"
g_app_config = TomlConfigParser.read(g_app_config_file, build_app_defaults())

terminal_printer = lambda line: g_terminal_window.add_line(line)
game = GameFactory.create(current_dir, terminal_printer)

if game is None:
    setup_install_game(current_dir)
else:
    setup_detected_game_server(game)

root.mainloop()

TomlConfigParser.write(g_app_config_file, g_app_config)
if g_game_config != None:
    TomlConfigParser.write(g_game_config_file, g_game_config)
