import copy
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from config.config_item import ConfigType
from config.tab_spec import TabSpec
from config.toml_config import Config, TomlConfigParser
from app.version import VERSION
import ui.widgets as ui
import ui.terminal as terminal
import ui.rcon_window as rcon_window
from game.game import Game, OperationResult, TerminalLineResult
from game.game_factory import GameFactory
from app.config_defaults import build_app_defaults
from app.config_index import ConfigIndex
from ui_builder.ui_builder import UiBuilder
from support.browser import open_url
from support.dialog import choice_dialog, link_dialog, ok_dialog, ok_dialog_exit
from support.set_status_line import (
    init_status_line,
    set_status_line,
    restore_status_line,
)
from support.restart_application import restart_application
from support.update_check import check_for_update

g_restart_requested = False
g_main_frame = None
g_status_line = None
g_terminal_window = None
g_terminal_is_open = False
g_terminal_open_close = None
g_configure_window = None
g_configure_is_open = False
g_configure_open_close = None
g_rcon_window = None
g_rcon_is_open = False
g_rcon_open_close = None
g_app_configure_window = None
g_app_configure_is_open = False
g_app_configure_open_close = None
g_install_open_close = None
g_update_open_close = None
g_start_stop_server = None
# Whether the current game is expected to be running (started, and not
# yet stopped/crashed) -- checked by poll_game_running() against
# game.is_running() to notice a crash.
g_server_should_be_running = False
# after() id of the next poll_game_running() call, so it can be
# cancelled before root is destroyed -- otherwise Tk can still try to
# fire it against an already-torn-down interpreter right as the app
# closes, raising a bgerror ("invalid command name ...poll_game_running").
g_poll_game_running_job = None
g_config_default = None
g_app_config = None
g_app_config_file = None
g_game_config = None
g_game_config_file = None
g_ui_builder = None


def print_to_terminal(line: str):
    g_terminal_window.add_line(f"{line}")


def _auto_open_terminal_for_install_or_update() -> bool:
    """If enabled and the terminal isn't already open, open it and
    return True so the caller closes it again once the operation
    finishes successfully; otherwise (disabled, or already open)
    return False and leave it as it is."""
    if (
        not g_app_config[ConfigIndex.AUTO_OPEN_TERMINAL_ON_INSTALL_OR_UPDATE].value
        or g_terminal_window.is_visible()
    ):
        return False
    on_toggle_terminal_window()
    # A real click updates the checkbox's own visual state as part of
    # the click itself before on_toggle_terminal_window() ever runs;
    # this programmatic call has no such click, so it's done here.
    g_terminal_open_close.on()
    return True


def on_install_game_server(name: str):
    print_to_terminal(
        f"Installing game server for {name} in directory {current_dir}..."
    )
    set_status_line(f"Installing {name}...")
    auto_opened_terminal = _auto_open_terminal_for_install_or_update()
    game = GameFactory.create_from_name(name, current_dir, terminal_printer)
    if not game:
        root.after(0, g_install_open_close.off)
        return

    g_install_open_close.disable()

    def on_install_result(result):
        print_to_terminal(f"Install for {game.get_long_name()} finished: {result}")

        def finish():
            g_install_open_close.off()
            g_install_open_close.enable()
            if result == OperationResult.OK and auto_opened_terminal:
                g_terminal_window.hide()
            if result == OperationResult.FAIL:
                on_error_report()
                message = (
                    f"Installation of game {game.get_long_name()} failed, an error "
                    "report was created. Have a look in the terminal output, and if "
                    "a cause can't be determined consider creating a github issue "
                    "attaching the report"
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
                _cancel_poll_game_running()
                root.destroy()

        root.after(0, finish)

    game.install(on_install_result)


def on_update_game_server(game: Game):
    print_to_terminal(
        f"Updating game server for {game.get_long_name()} in directory {game.get_directory()}..."
    )
    set_status_line(f"Updating {game.get_long_name()}...")
    g_start_stop_server.disable()
    g_update_open_close.disable()
    auto_opened_terminal = _auto_open_terminal_for_install_or_update()

    def on_update_result(result):

        def finish():
            if result == OperationResult.OK:
                if auto_opened_terminal:
                    g_terminal_window.hide()
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
            g_update_open_close.enable()
            g_start_stop_server.enable()

        root.after(0, finish)

    game.update(on_update_result)


def restore_status_line_delayed():
    root.after(5000, restore_status_line)


def _write_config_files() -> None:
    TomlConfigParser.write(g_app_config_file, g_app_config)
    if g_game_config is not None:
        TomlConfigParser.write(g_game_config_file, g_game_config)


def save_config():
    set_status_line("Saving Configuration...")
    _write_config_files()
    print_to_terminal("Configuration saved")
    set_status_line("Configuration saved")
    restore_status_line_delayed()


def on_save_config():
    save_config()


def _reset_config_to_defaults(
    config: Config, defaults: Config, keep_masked: bool
) -> list:
    """Reset every non-read_only item in `config` to its value in
    `defaults`, in place (so already-registered UI widgets/game state
    referencing this exact dict keep working) -- except MASKED_STRING
    items (passwords/keys) when `keep_masked` is True, which are left
    untouched. read_only items are skipped, the same as
    TomlConfigParser: they're always recomputed fresh (e.g. a detected
    maps list), not something a "reset" should touch. Returns the list
    of indexes actually changed, so the caller can refresh their
    widgets and react the same way a live edit would (see
    Game.config_item_changed())."""
    changed = []
    for index, item in config.items():
        if item.read_only:
            continue
        if keep_masked and item.type is ConfigType.MASKED_STRING:
            continue
        default_item = defaults.get(index)
        if default_item is None or item.value == default_item.value:
            continue
        try:
            item.set(default_item.value)
        except (TypeError, ValueError):
            # Shouldn't normally happen (the default came from this
            # same item's own schema), but don't let one bad item
            # abort the whole reset.
            continue
        changed.append(index)
    return changed


_GithubUrl = "https://github.com/lenosisnickerboa/sgsl"


def on_open_github():
    open_url(_GithubUrl)


def on_restart_application():
    # Config is saved unconditionally after mainloop() returns (see
    # the bottom of this file) — destroying root just gets us there,
    # the same way a successful install triggers a restart.
    global g_restart_requested
    g_restart_requested = True
    _cancel_poll_game_running()
    root.destroy()


def on_close_main_window():
    _cancel_poll_game_running()
    root.destroy()


def _redact_masked_values(config: Config) -> Config:
    """Return a deep copy of `config` with every MASKED_STRING item's
    value replaced by asterisks, so it's safe to write to a shared
    file like an error report."""
    redacted = copy.deepcopy(config)
    for item in redacted.values():
        if item.type is ConfigType.MASKED_STRING:
            item.value = "********"
    return redacted


def _redact_secrets(text: str, *configs: Config) -> str:
    """Replace any occurrence of a MASKED_STRING item's actual value
    (e.g. a server password) in `text` with asterisks."""
    for config in configs:
        for item in config.values():
            if item.type is ConfigType.MASKED_STRING and item.value:
                text = text.replace(str(item.value), "********")
    return text


def on_error_report():
    # Make sure the config files on disk reflect the current in-memory
    # state, not a stale save — the report below is written from the
    # in-memory configs, but this keeps sgsl.toml/game.toml themselves
    # current too, same as a manual Save config.
    save_config()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_name = f"error-report-{timestamp}"
    report_dir = Path(current_dir) / report_name
    report_dir.mkdir(parents=True)

    configs = [g_app_config] + ([g_game_config] if g_game_config is not None else [])
    (report_dir / "terminal.txt").write_text(
        _redact_secrets(g_terminal_window.get_content(), *configs), encoding="utf-8"
    )
    if g_rcon_window is not None:
        (report_dir / "rcon_output.txt").write_text(
            _redact_secrets(g_rcon_window.get_content(), *configs), encoding="utf-8"
        )
    TomlConfigParser.write(
        report_dir / g_app_config_file.name, _redact_masked_values(g_app_config)
    )
    if g_game_config is not None:
        TomlConfigParser.write(
            report_dir / g_game_config_file.name,
            _redact_masked_values(g_game_config),
        )

    (report_dir / "program_version.txt").write_text(VERSION, encoding="utf-8")
    (report_dir / "install_directory_path.txt").write_text(
        str(current_dir), encoding="utf-8"
    )
    free_gb = shutil.disk_usage(current_dir).free / (1024**3)
    (report_dir / "available_diskspace.txt").write_text(
        f"{free_gb:.2f} GB", encoding="utf-8"
    )

    if game is not None:
        for relative_path in game.error_report_files():
            source_path = Path(current_dir) / relative_path
            if not source_path.is_file():
                # Not created yet, or the game just doesn't have it --
                # skip rather than fail the whole report.
                continue
            dest_path = report_dir / relative_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Text, not a raw copy -- these are game-written cfg/log
            # files that can literally contain a password/token cvar
            # value (e.g. sv_password/rcon_password), same as the
            # terminal log above, so they need the same redaction.
            text = source_path.read_text(encoding="utf-8", errors="replace")
            dest_path.write_text(_redact_secrets(text, *configs), encoding="utf-8")

    error_reports_dir = Path(current_dir) / "error_reports"
    error_reports_dir.mkdir(parents=True, exist_ok=True)
    archive_path = Path(
        shutil.make_archive(
            str(error_reports_dir / report_name), "zip", root_dir=report_dir
        )
    )

    shutil.rmtree(report_dir)

    relative_archive_path = archive_path.relative_to(current_dir)
    print_to_terminal(f"Error report created: {archive_path}")
    set_status_line(f"Error report created: {relative_archive_path}")
    root.after(5000, restore_status_line)


def on_toggle_configure_window():
    global g_configure_is_open
    g_configure_is_open = not g_configure_is_open
    g_configure_window.toggle()


def on_toggle_rcon_window():
    global g_rcon_is_open
    g_rcon_is_open = not g_rcon_is_open
    g_rcon_window.toggle()


def on_toggle_app_configure_window():
    global g_app_configure_is_open
    g_app_configure_is_open = not g_app_configure_is_open
    g_app_configure_window.toggle()


def on_start_stop_game_server(game: Game):
    global g_start_stop_server, g_server_should_be_running

    if not game.is_running():
        _write_config_files()
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
        g_server_should_be_running = True
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
        if not game.stop():
            f"Stopping game server for {game.get_long_name()} in directory {game.get_directory()} failed..."
            set_status_line(
                f"{game.get_long_name()} is running (tried to stop it and failed)..."
            )
            return

        g_server_should_be_running = False
        g_start_stop_server.set_name(name="Start")
        g_start_stop_server.set_tooltip(tooltip="Start server")
        g_update_open_close.enable()
        print_to_terminal(
            f"Stopped game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        restore_status_line()


def on_game_server_crashed(game: Game):
    global g_start_stop_server, g_server_should_be_running

    g_server_should_be_running = False
    ok_dialog(f"{game.get_long_name()} crashed", title="Server crashed")

    g_start_stop_server.set_name(name="Start")
    g_start_stop_server.set_tooltip(tooltip="Start server")
    g_update_open_close.enable()
    set_status_line(f"Game server {game.get_long_name()} crashed...")
    print_to_terminal(
        f"Game server for {game.get_long_name()} in directory {game.get_directory()} crashed..."
    )
    restore_status_line_delayed()


def on_game_map_load_failed(game: Game):
    global g_start_stop_server, g_server_should_be_running

    g_server_should_be_running = False
    ok_dialog("Map load failed, server will be stopped", title="Map load failed")

    game.stop()
    g_start_stop_server.set_name(name="Start")
    g_start_stop_server.set_tooltip(tooltip="Start server")
    g_update_open_close.enable()
    set_status_line(f"Game server {game.get_long_name()} stopped (map load failed)...")
    print_to_terminal(
        f"Game server for {game.get_long_name()} in directory {game.get_directory()} stopped after map load failure..."
    )
    restore_status_line_delayed()


_PollGameRunningIntervalMs = 3000


def poll_game_running():
    """Periodically check whether the current game is still running
    when it's expected to be, so a crash (the process disappearing on
    its own) is noticed even though nothing told us about it directly."""
    global g_poll_game_running_job
    if game is not None and g_server_should_be_running and not game.is_running():
        on_game_server_crashed(game)
    g_poll_game_running_job = root.after(_PollGameRunningIntervalMs, poll_game_running)


def _cancel_poll_game_running():
    """Cancel the pending poll_game_running() call, if any -- must
    happen before root.destroy(), or Tk can still try to fire it
    against an already-torn-down interpreter (see the comment on
    g_poll_game_running_job)."""
    global g_poll_game_running_job
    if g_poll_game_running_job is not None:
        root.after_cancel(g_poll_game_running_job)
        g_poll_game_running_job = None


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

    global g_start_stop_server, g_server_should_be_running
    g_server_should_be_running = game.is_running()
    if g_server_should_be_running:
        g_start_stop_server = ui.Button(
            master=game_frame,
            name="Stop",
            tooltip="Stop server",
            command=lambda: on_start_stop_game_server(game),
        )
        set_status_line(f"{game.get_long_name()} is running...")
    else:
        g_start_stop_server = ui.Button(
            master=game_frame,
            name="Start",
            tooltip="Start server",
            command=lambda: on_start_stop_game_server(game),
        )
        set_status_line("Ready")
    g_start_stop_server.pack()

    # Anchored to the right of game_frame, as a group, so Start stays
    # pinned to the left while these sit flush against the right edge.
    right_button_frame = ui.Frame(master=game_frame)
    right_button_frame.pack(side=ui.RIGHT)

    developer_button = ui.Button(
        master=right_button_frame,
        name="Developer",
        tooltip=f"Open {game.get_long_name()}'s developer/publisher page in your default browser",
        command=lambda: open_url(game.get_developer_url()),
    )
    developer_button.pack()

    global g_configure_open_close
    g_configure_open_close = ui.CheckButton(
        master=right_button_frame,
        name="Configure",
        tooltip="Edit game server configuration",
        command=lambda _value: on_toggle_configure_window(),
    )
    g_configure_open_close.pack()

    global g_update_open_close
    g_update_open_close = ui.CheckButton(
        master=right_button_frame,
        name="Update",
        tooltip="Update game server",
        command=lambda value: on_update_game_server(game) if value else None,
    )
    g_update_open_close.pack()
    if g_server_should_be_running:
        g_update_open_close.disable()

    global g_rcon_open_close
    g_rcon_open_close = None
    if game.supports_rcon():
        g_rcon_open_close = ui.CheckButton(
            master=right_button_frame,
            name="RCON",
            tooltip="Open an interactive RCON console for this server",
            command=lambda _value: on_toggle_rcon_window(),
        )
        g_rcon_open_close.pack()

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

    def send_rcon_command(command: str) -> str:
        if not game.rcon_enabled(g_game_config):
            raise RuntimeError("RCON is disabled -- enable it first")
        if not game.is_running():
            raise RuntimeError(
                f"{game.get_long_name()} is not running -- start it first"
            )
        return game.send_rcon_command(command, g_game_config)

    global g_rcon_window
    if game.supports_rcon():
        g_rcon_window = rcon_window.RconWindow(
            root,
            on_close_rcon_window,
            command_callback=send_rcon_command,
            install_dir=game.get_directory(),
            quick_commands=game.rcon_quick_commands(),
            title=f"RCON — {game.get_long_name()}",
        )

    # -- spacer

    spacer_between_shortcut_and_application_frame = ui.Spacer(master=g_main_frame)
    spacer_between_shortcut_and_application_frame.pack()

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
                items=[
                    ConfigIndex.SNAP_WINDOWS_ENABLED,
                    ConfigIndex.AUTOMATIC_UPDATE_CHECK,
                ],
            ),
            TabSpec(
                title="Terminal",
                items=[
                    ConfigIndex.TERMINAL_ENABLED,
                    ConfigIndex.TERMINAL_LOG_MAX_LINES,
                    ConfigIndex.AUTO_OPEN_TERMINAL_ON_INSTALL_OR_UPDATE,
                ],
            ),
        ],
        g_app_config,
        on_app_config_item_changed,
    )

    def on_set_defaults():
        choice = choice_dialog(
            "Set config back to default values?",
            title="Set defaults",
            choices=[
                ("All", "All config items including masked", "all"),
                (
                    "All excluding masked",
                    "All config items but keep masked config items, i.e. all passwords and keys",
                    "all_excluding_masked",
                ),
                ("Cancel", "Don't touch my config, I want it as it is", "cancel"),
            ],
            cancel_value="cancel",
        )
        if choice == "cancel":
            return

        keep_masked = choice == "all_excluding_masked"

        app_changed = _reset_config_to_defaults(
            g_app_config, build_app_defaults(), keep_masked
        )
        app_affected = set(app_changed)
        for index in app_changed:
            app_affected.update(
                on_app_config_item_changed(g_app_config[index], g_app_config)
            )
        app_ui_builder.config_changed(list(app_affected), g_app_config)

        if g_game_config is not None:
            game_changed = _reset_config_to_defaults(
                g_game_config, game.config_defaults(), keep_masked
            )
            game_affected = set(game_changed)
            for index in game_changed:
                game_affected.update(
                    game.config_item_changed(g_game_config[index], g_game_config)
                )
            g_ui_builder.config_changed(list(game_affected), g_game_config)

        print_to_terminal("Configuration reset to default values")
        set_status_line("Configuration reset to default values")
        restore_status_line_delayed()

    # -- application frame

    application_frame = ui.EditGroupFrame(master=g_main_frame, name="Application")
    application_frame.pack()

    # Anchored to the left of application_frame, opposite the button
    # group below.
    github_button = ui.Button(
        master=application_frame,
        name="GitHub",
        tooltip="Open the sgsl GitHub page in your default browser",
        command=on_open_github,
    )
    github_button.pack()

    check_for_updates_button = ui.Button(
        master=application_frame,
        name="Check for updates",
        tooltip="Check GitHub for a newer sgsl release",
        command=on_check_for_updates,
    )
    check_for_updates_button.pack()

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

    set_defaults_button = ui.Button(
        master=app_right_button_frame,
        name="Set defaults...",
        tooltip="Reset the application and/or game configuration to default values",
        command=on_set_defaults,
    )
    set_defaults_button.pack()

    restart_button = ui.Button(
        master=app_right_button_frame,
        name="Restart",
        tooltip="Save configuration and restart the application",
        command=on_restart_application,
    )
    restart_button.pack()

    error_report_button = ui.Button(
        master=app_right_button_frame,
        name="Error report",
        tooltip="Bundle the terminal log and config files into a zipped error report",
        command=on_error_report,
    )
    error_report_button.pack()

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


def on_close_rcon_window():
    global g_rcon_is_open
    g_rcon_is_open = False
    g_rcon_open_close.off()


def on_close_app_configure_window():
    global g_app_configure_is_open
    g_app_configure_is_open = False
    g_app_configure_open_close.off()


def _show_update_available_dialog(new_version: str, release_url: str) -> None:
    link_dialog(
        message=(
            f"A new version {new_version} of sgsl has been detected and is "
            "available for download here:"
        ),
        link_text=release_url,
        link_url=release_url,
        title="Update available",
    )


def _check_for_update_in_background(manual: bool = False) -> None:
    """Check GitHub for a newer sgsl release on a background thread
    (network I/O, must not block startup), then hop back to the main
    thread via root.after() -- same pattern as the install/update
    result callbacks below -- to show a dialog if one was found.

    `manual`, if True (a user-triggered check via the "Check for
    updates" button, rather than the silent one done at startup), also
    gives feedback via the status line when no update is available,
    rather than doing nothing visible."""

    def worker():
        result = check_for_update(VERSION)

        def finish():
            if result is not None:
                new_version, release_url = result
                _show_update_available_dialog(new_version, release_url)
            elif manual:
                set_status_line("You already have the latest version of sgsl")
                restore_status_line_delayed()

        root.after(0, finish)

    threading.Thread(target=worker, daemon=True).start()


def on_check_for_updates():
    set_status_line("Checking for updates...")
    _check_for_update_in_background(manual=True)


# main

root = ui.Window(title="Simple Game Server Launcher" + " " + VERSION)
root.protocol("WM_DELETE_WINDOW", on_close_main_window)

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
)

print_to_terminal(f"sgsl.exe {VERSION} starting...")

if g_app_config[ConfigIndex.AUTOMATIC_UPDATE_CHECK].value:
    _check_for_update_in_background()

g_status_line = ui.StatusLine(master=root, initial_text="Ready")
g_status_line.pack()
init_status_line(g_status_line)

g_main_frame = ui.MainFrame(master=root)
g_main_frame.pack()

terminal_printer = lambda line: g_terminal_window.add_line(line)
game = GameFactory.create(current_dir, terminal_printer)


def on_terminal_line(line: str):
    """Ask the currently active game what a line of terminal output
    means, if a game is active."""
    if not game:
        return
    result = game.interpret_terminal_line(line)
    if result == TerminalLineResult.OK:
        return
    if result == TerminalLineResult.MAP_DOWNLOAD_FAILED:
        return
    if result == TerminalLineResult.MAP_LOAD_FAILED:
        on_game_map_load_failed(game)
        return


g_terminal_window.register_listener(on_terminal_line)

if game is None:
    setup_install_game(current_dir)
else:
    setup_detected_game_server(game)

root.center_on_screen()

g_poll_game_running_job = root.after(_PollGameRunningIntervalMs, poll_game_running)

print_to_terminal(f"sgsl.exe {VERSION} entering mainloop...")
root.mainloop()

print_to_terminal(f"sgsl.exe {VERSION} saving config...")
save_config()

if g_restart_requested:
    print_to_terminal(f"sgsl.exe {VERSION} restarting application...")
    restart_application()

print_to_terminal(f"sgsl.exe {VERSION} exiting application...")
