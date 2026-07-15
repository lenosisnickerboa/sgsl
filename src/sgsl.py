import os
from pathlib import Path
from config.config_item import ConfigItem, ConfigType, Range
from config.tab_spec import TabSpec
from config.toml_config import Config, TomlConfigParser
from app.version import VERSION
import ui.widgets as ui
import ui.terminal as terminal
from game.game import Game, OperationResult
from game.game_factory import GameFactory
from app.config_index import ConfigIndex
from ui_builder.ui_builder import UiBuilder
from support.dialog import ok_dialog, ok_dialog_exit
from support.set_status_line import (
    init_status_line,
    set_status_line,
    restore_status_line,
)
from support.restart_application import restart_application

g_restart_requested = False
g_main_frame = None
g_status_line = None
g_terminal_window = None
g_terminal_is_open = False
g_terminal_open_close = None
g_configure_window = None
g_configure_is_open = False
g_configure_open_close = None
g_app_configure_window = None
g_app_configure_is_open = False
g_app_configure_open_close = None
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
        ConfigIndex.TERMINAL_LOG_MAX_LINES: ConfigItem(
            name="terminal_log_max_lines",
            visible_name="Terminal log max lines",
            type=ConfigType.INTEGER,
            tooltip="Maximum number of lines kept in the terminal log; 0 = no limit",
            value=0,
            range=Range(min_value=0),
        ),
        ConfigIndex.SNAP_WINDOWS_ENABLED: ConfigItem(
            name="snap_windows_enabled",
            visible_name="Snap windows",
            type=ConfigType.BOOLEAN,
            tooltip="Snap the terminal/config windows to and drag them along with the main window",
            value=True,
        ),
    }


def print_to_terminal(line: str):
    g_terminal_window.add_line(f"{line}")


def on_install_game_server(name: str):
    print_to_terminal(
        f"Installing game server for {name} in directory {current_dir}..."
    )
    set_status_line(f"Installing {name}...")
    game = GameFactory.create_from_name(name, current_dir, terminal_printer)
    if not game:
        root.after(0, g_install_open_close.off)
        return

    def on_install_result(result):
        print_to_terminal(f"Install for {game.get_long_name()} finished: {result}")

        def finish():
            g_install_open_close.off()
            if result == OperationResult.FAIL:
                message = (
                    f"Installation of game {game.get_long_name()} failed, have a look "
                    "in the terminal output. If a cause can't be determined consider "
                    "creating an error report and create a github issue attaching the "
                    "report"
                )
                set_status_line(f"Installation of game {game.get_long_name()} failed")
                ok_dialog_exit(message, title="Install failed")
            elif result == OperationResult.NOT_SUPPORTED:
                message = (
                    f"Installation of game {game.get_long_name()} is not supported, instead "
                    "install the game using the standard installation method and then drop "
                    "the sgsl.exe file into the installation as described in the games "
                    "installation instructions on sgsls github."
                )
                set_status_line(
                    f"Installation of game {game.get_long_name()} not supported"
                )
                ok_dialog_exit(message, title="Install failed")
            else:
                message = "Installation succeeded, press OK and the application will be restarted"
                set_status_line(
                    f"Installation of game {game.get_long_name()} succeeded"
                )
                ok_dialog(message, title="Install succeeded")
                # Let mainloop() return so the config-write code after it
                # runs before we replace the process — see the bottom of
                # this file.
                global g_restart_requested
                g_restart_requested = True
                root.destroy()

        root.after(0, finish)

    game.install(on_install_result)


def on_update_game_server(game: Game):
    print_to_terminal(
        f"Updating game server for {game.get_long_name()} in directory {game.get_directory()}..."
    )
    set_status_line(f"Updating {game.get_long_name()}...")
    g_start_stop_server.disable()

    def on_update_result(result):

        def finish():
            if result == OperationResult.OK:
                message = f"Update of {game.get_long_name()} finished successfully"
                print_to_terminal(message)
                set_status_line(message)
                ok_dialog(message, title="Update succeeded")
            elif result == OperationResult.FAIL:
                message = f"Update of {game.get_long_name()} failed"
                print_to_terminal(message)
                set_status_line(message)
                ok_dialog(message, title="Update failed")
            elif result == OperationResult.NOT_SUPPORTED:
                message = f"Update of {game.get_long_name()} not supported"
                print_to_terminal(f"Update for {game.get_long_name()} not supported")
                set_status_line(f"Update of {game.get_long_name()} not supported")
                ok_dialog(message, title="Update failed")

            restore_status_line()
            g_update_open_close.off()
            g_start_stop_server.enable()

        root.after(0, finish)

    game.update(on_update_result)


def save_config():
    set_status_line("Saving Configuration...")
    TomlConfigParser.write(g_app_config_file, g_app_config)
    if g_game_config is not None:
        TomlConfigParser.write(g_game_config_file, g_game_config)
    print_to_terminal("Configuration saved")
    set_status_line("Configuration saved")
    root.after(5000, restore_status_line)


def on_save_config():
    save_config()


def on_toggle_configure_window():
    global g_configure_is_open
    g_configure_is_open = not g_configure_is_open
    g_configure_window.toggle()


def on_toggle_app_configure_window():
    global g_app_configure_is_open
    g_app_configure_is_open = not g_app_configure_is_open
    g_app_configure_window.toggle()


def on_start_stop_game_server(game: Game):
    global g_start_stop_server

    if not game.is_running():
        print_to_terminal(
            f"Starting game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        set_status_line(f"Starting {game.get_long_name()}...")
        global g_game_config
        if not game.run(g_game_config):
            print_to_terminal(
                f"Starting game server for {game.get_long_name()} in directory {game.get_directory()} was cancelled."
            )
            restore_status_line()
            return
        g_start_stop_server.set_name(name="Stop")
        g_start_stop_server.set_tooltip(tooltip="Stop server")
        g_update_open_close.disable()
        print_to_terminal(
            f"Started game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        set_status_line(f"{game.get_long_name()} is running...")
    else:
        print_to_terminal(
            f"Stopping game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        set_status_line(f"Stopping {game.get_long_name()}...")
        game.stop()
        g_start_stop_server.set_name(name="Start")
        g_start_stop_server.set_tooltip(tooltip="Start server")
        g_update_open_close.enable()
        print_to_terminal(
            f"Stoped game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        restore_status_line()


def on_toggle_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = not g_terminal_is_open
    g_terminal_window.toggle()


def setup_install_game(dir: str):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name="No game server detected")
    game_frame.pack()

    all_games = GameFactory.games()
    selected_game = ui.StringCombobox(
        master=game_frame,
        name="Select a game server to install",
        values=all_games,
        selected=all_games[0],
        tooltip="Select a game server to install",
    )
    selected_game.pack()

    global g_install_open_close
    g_install_open_close = ui.CheckButton(
        master=game_frame,
        name="Install game server",
        tooltip="Install selected game server",
        command=lambda value: (
            on_install_game_server(selected_game.combobox.get()) if value else None
        ),
    )
    g_install_open_close.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(
        master=game_frame,
        name="Terminal",
        tooltip="Toggle terminal window",
        command=lambda _value: on_toggle_terminal_window(),
    )
    g_terminal_open_close.pack()

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()


def setup_detected_game_server(game: Game):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name=game.get_long_name())
    game_frame.pack()

    global g_start_stop_server
    if game.is_running():
        g_start_stop_server = ui.Button(
            master=game_frame,
            name="Stop",
            tooltip="Stop server",
            command=lambda: on_start_stop_game_server(game),
        )
    else:
        g_start_stop_server = ui.Button(
            master=game_frame,
            name="Start",
            tooltip="Start server",
            command=lambda: on_start_stop_game_server(game),
        )
    g_start_stop_server.pack()

    # Anchored to the right of game_frame, as a group, so Start stays
    # pinned to the left while these sit flush against the right edge.
    right_button_frame = ui.Frame(master=game_frame)
    right_button_frame.pack(side=ui.RIGHT)

    global g_update_open_close
    g_update_open_close = ui.CheckButton(
        master=right_button_frame,
        name="Update",
        tooltip="Update game server",
        command=lambda value: on_update_game_server(game) if value else None,
    )
    g_update_open_close.pack()
    if game.is_running():
        g_update_open_close.disable()

    global g_configure_open_close
    g_configure_open_close = ui.CheckButton(
        master=right_button_frame,
        name="Configure",
        tooltip="Edit game server configuration",
        command=lambda _value: on_toggle_configure_window(),
    )
    g_configure_open_close.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(
        master=right_button_frame,
        name="Terminal",
        tooltip="Toggle terminal window",
        command=lambda _value: on_toggle_terminal_window(),
    )
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
    game.config_loaded(g_game_config)

    # A saved value (e.g. a previously edited AVAILABLE_MAPS list) may
    # have just overridden a default independently of any item derived
    # from it (e.g. SELECTED_MAP's allowed_values) — give the game a
    # chance to re-derive those before any widget is built from this
    # config, the same way it would react to a live UI edit.
    for config_item in list(g_game_config.values()):
        game.config_item_changed(config_item, g_game_config)

    def on_config_item_changed(config_item, config):
        return game.config_item_changed(config_item, config)

    global g_ui_builder
    g_ui_builder = UiBuilder()
    g_ui_builder.build_shortcuts(
        shortcut_frame, game.config_shortcuts(), g_game_config, on_config_item_changed
    )

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
    # window whenever the config window (re)opens, moves, or resizes.
    g_configure_window.add_snap_follower(g_terminal_window)
    # Keep the config window (and, transitively, the terminal window
    # via the registration above) snapped when the main window moves.
    root.add_snap_follower(g_configure_window)

    # -- spacer

    spacer_between_shortcut_and_application_frame = ui.Spacer(master=g_main_frame)
    spacer_between_shortcut_and_application_frame.pack()

    # -- application frame

    application_frame = ui.EditGroupFrame(master=g_main_frame, name="Application")
    application_frame.pack()

    # Anchored to the right of application_frame, as a group — same
    # pattern as game_frame's right_button_frame.
    app_right_button_frame = ui.Frame(master=application_frame)
    app_right_button_frame.pack(side=ui.RIGHT)

    global g_app_configure_open_close
    g_app_configure_open_close = ui.CheckButton(
        master=app_right_button_frame,
        name="Configure",
        tooltip="Edit application configuration",
        command=lambda _value: on_toggle_app_configure_window(),
    )
    g_app_configure_open_close.pack()

    save_app_config_button = ui.Button(
        master=app_right_button_frame,
        name="Save config",
        tooltip="Save the current application and game configuration to file",
        command=on_save_config,
    )
    save_app_config_button.pack()

    def on_app_config_item_changed(_config_item, config):
        ui.SnapWindow.enabled = config[ConfigIndex.SNAP_WINDOWS_ENABLED].value
        return []

    # A separate UiBuilder instance: its widget registry is keyed by
    # IndexT enum members, and app.config_index.ConfigIndex's values
    # collide numerically with game.cs2.config_index.ConfigIndex's
    # (both are small IntEnums) — sharing g_ui_builder here would let
    # a change to one wrongly refresh a same-valued widget in the other.
    app_ui_builder = UiBuilder()
    global g_app_configure_window
    g_app_configure_window = app_ui_builder.build_configuration_window(
        root,
        on_close_app_configure_window,
        "Configure application",
        [
            TabSpec(
                title="General",
                items=[ConfigIndex.SNAP_WINDOWS_ENABLED],
            ),
            TabSpec(
                title="Terminal",
                items=[
                    ConfigIndex.TERMINAL_ENABLED,
                    ConfigIndex.TERMINAL_LOG_MAX_LINES,
                ],
            ),
        ],
        g_app_config,
        on_app_config_item_changed,
        # Anchor to the right of the game config window while it's
        # open, so the two don't land on top of each other — both
        # would otherwise snap to the same spot next to the main
        # window.
        snap_anchor=lambda: (
            g_configure_window
            if g_configure_window is not None and g_configure_window.is_visible()
            else root
        ),
    )
    # Keep it snapped alongside the game config window (if open) or
    # the main window, the same way the terminal window does.
    g_configure_window.add_snap_follower(g_app_configure_window)
    root.add_snap_follower(g_app_configure_window)
    # The terminal window chains off the app config window when it's
    # open (see its snap_anchor) — keep it following along too.
    g_app_configure_window.add_snap_follower(g_terminal_window)

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


def on_close_app_configure_window():
    global g_app_configure_is_open
    g_app_configure_is_open = False
    g_app_configure_open_close.off()


# main

root = ui.Window(title="Simple Game Server Launcher" + " " + VERSION)

current_dir = os.getcwd()

g_app_config_file = Path(current_dir) / "sgsl.toml"
g_app_config = TomlConfigParser.read(g_app_config_file, build_app_defaults())
ui.SnapWindow.enabled = g_app_config[ConfigIndex.SNAP_WINDOWS_ENABLED].value

g_terminal_window = terminal.TerminalWindow(
    root,
    on_close_terminal_window,
    install_dir=current_dir,
    title="Log Output",
    max_lines=g_app_config[ConfigIndex.TERMINAL_LOG_MAX_LINES].value,
    # Chain rightward off whichever of the app config / game config
    # windows is open, so it never lands on top of either of them —
    # falling back to the main window if neither is open.
    snap_anchor=lambda: (
        g_app_configure_window
        if g_app_configure_window is not None and g_app_configure_window.is_visible()
        else (
            g_configure_window
            if g_configure_window is not None and g_configure_window.is_visible()
            else root
        )
    ),
)
# Also a direct follower of the main window: when the config window
# isn't open (so the terminal is snapped straight to the main window),
# moving the main window still needs to drag the terminal along.
root.add_snap_follower(g_terminal_window)

g_status_line = ui.StatusLine(master=root, initial_text="Ready")
g_status_line.pack()
init_status_line(g_status_line)

g_main_frame = ui.MainFrame(master=root)
g_main_frame.pack()

terminal_printer = lambda line: g_terminal_window.add_line(line)
game = GameFactory.create(current_dir, terminal_printer)

if game is None:
    setup_install_game(current_dir)
else:
    setup_detected_game_server(game)

root.mainloop()

save_config()

if g_restart_requested:
    restart_application()
