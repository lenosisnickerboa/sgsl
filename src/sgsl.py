import copy
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from config.config_item import ConfigType
from config.tab_spec import TabSpec
from config.toml_config import Config, TomlConfigParser, reset_to_defaults
from config.config_upgrader import apply_upgraders
from app.resources import resource_path
from app.version import VERSION
import ui.widgets as ui
import ui.terminal as terminal
import ui.rcon_window as rcon_window
from game.game import Game, OperationResult, TerminalLineResult
from game.game_factory import GameFactory
from app.config_defaults import (
    build_app_defaults,
    APP_CONFIG_VERSION,
    APP_CONFIG_UPGRADERS,
)
from app.config_index import ConfigIndex
from ui_builder.ui_builder import UiBuilder
from support.browser import open_url
from support.dialog import (
    choice_dialog,
    choice_dialog_with_toggles,
    confirm_dialog,
    link_dialog,
    ok_dialog,
    ok_dialog_exit,
)
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
g_check_for_update_button = None
# Which of the current game's suspicious_terminal_line_patterns() have
# already triggered a dialog this run -- reset whenever the server is
# (re)started -- see on_terminal_line(). A crash/assertion pattern
# typically repeats every subsequent line/tick once it starts, so
# without this a single bad moment would otherwise queue up an endless
# wall of identical modal dialogs.
g_shown_suspicious_line_patterns: set = set()
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
# The current Game instance -- needed by module-level functions (e.g.
# _write_config_files(), on_toggle_rcon_window()) that only ever run
# after setup_detected_game_server(game) has set this, since `game`
# itself is just a local/closure variable there.
g_game = None
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
    TomlConfigParser.write(g_app_config_file, g_app_config, version=APP_CONFIG_VERSION)
    if g_game_config is not None:
        TomlConfigParser.write(
            g_game_config_file, g_game_config, version=g_game.config_version()
        )


def save_config():
    set_status_line("Saving Configuration...")
    _write_config_files()
    print_to_terminal("Configuration saved")
    set_status_line("Configuration saved")
    restore_status_line_delayed()


def on_save_config():
    save_config()


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
    if not g_rcon_is_open and not (
        g_game.rcon_enabled(g_game_config)
        and g_game.rcon_password_configured(g_game_config)
    ):
        # Only checked when *opening* -- closing an already-open
        # window should never be blocked, even if RCON was disabled
        # out from under it since it was opened. The checkbutton
        # itself already flipped to "on" by the time this runs (see
        # ui.CheckButton.on_event()) -- snap it back to reflect that
        # the window is staying closed.
        g_rcon_open_close.off()
        ok_dialog(
            "In order to use the RCON client you need to enable RCON in the server and "
            "configure an RCON password"
        )
        return
    g_rcon_is_open = not g_rcon_is_open
    g_rcon_window.toggle()


def on_toggle_app_configure_window():
    global g_app_configure_is_open
    g_app_configure_is_open = not g_app_configure_is_open
    g_app_configure_window.toggle()


def on_start_stop_game_server(game: Game):
    global g_start_stop_server, g_server_should_be_running, g_shown_suspicious_line_patterns, g_game_config

    if not game.is_running():
        if g_app_config[ConfigIndex.WARN_ABOUT_CONFIG_PROBLEMS].value:
            ok, warning = game.validate_before_start(g_game_config)
            if not ok:
                message = (
                    f"{warning}\n\n"
                    "Press OK to ignore warning and start server anyway.\n"
                    "Press Cancel to cancel starting the server and fix the configuration."
                )
                if not confirm_dialog(message, title="Configuration warning"):
                    return
        g_shown_suspicious_line_patterns = set()
        _write_config_files()
        print_to_terminal(
            f"Starting game server for {game.get_long_name()} in directory {game.get_directory()}..."
        )
        set_status_line(f"Starting {game.get_long_name()}...")
        if not game.run(
            g_game_config, g_app_config[ConfigIndex.USE_SGSL_OVERRIDES].value
        ):
            print_to_terminal(
                f"Starting game server for {game.get_long_name()} in directory {game.get_directory()} was cancelled."
            )
            restore_status_line()
            return
        g_server_should_be_running = True
        g_start_stop_server.set_name(name="Stop")
        g_start_stop_server.set_tooltip(tooltip="Stop server")
        g_update_open_close.disable()
        if g_check_for_update_button is not None:
            g_check_for_update_button.disable()
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
        if g_check_for_update_button is not None:
            g_check_for_update_button.enable()
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
    if g_check_for_update_button is not None:
        g_check_for_update_button.enable()
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
    if g_check_for_update_button is not None:
        g_check_for_update_button.enable()
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
    global g_game
    g_game = game
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
    # Explicit side=LEFT (rather than plain pack()'s default side=TOP)
    # so a subsequent same-row sibling (the "Check for update" button
    # below) actually lands beside it instead of on its own row.
    g_start_stop_server.pack(side=ui.LEFT)

    global g_check_for_update_button
    g_check_for_update_button = None
    if game.supports_game_update_check():
        g_check_for_update_button = ui.Button(
            master=game_frame,
            name="Check for update",
            tooltip=f"Manually check whether a newer {game.get_long_name()} server build is available",
            command=lambda: on_check_for_server_update(game),
        )
        g_check_for_update_button.pack(side=ui.LEFT)
        if g_server_should_be_running:
            g_check_for_update_button.disable()

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
    apply_upgraders(
        g_game_config,
        TomlConfigParser.read_version(g_game_config_file),
        game.config_upgraders(),
    )
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
        defaults_factory=game.config_defaults,
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
                    ConfigIndex.USE_SGSL_OVERRIDES,
                    ConfigIndex.WARN_ABOUT_CONFIG_PROBLEMS,
                    ConfigIndex.AUTOMATIC_UPDATE_CHECK,
                    ConfigIndex.SNAP_WINDOWS_ENABLED,
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
        defaults_factory=build_app_defaults,
    )

    def on_set_defaults():
        extra_options = game.extra_reset_options() if g_game_config is not None else []
        toggles = [
            (str(i), option.label, option.tooltip)
            for i, option in enumerate(extra_options)
        ]
        choice, toggle_states = choice_dialog_with_toggles(
            "Set config back to default values?",
            toggles=toggles,
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

        app_changed = reset_to_defaults(g_app_config, build_app_defaults(), keep_masked)
        app_affected = set(app_changed)
        for index in app_changed:
            app_affected.update(
                on_app_config_item_changed(g_app_config[index], g_app_config)
            )
        app_ui_builder.config_changed(list(app_affected), g_app_config)

        if g_game_config is not None:
            # Indexes with their own opt-in "remove ..." toggle (see
            # Game.extra_reset_options()) are excluded from this normal
            # pass regardless of whether that toggle is checked -- a
            # game with such content (e.g. downloaded workshop maps,
            # user-defined map groups) doesn't have a sensible "default"
            # for it that a routine reset should silently restore.
            excluded_indexes = {option.index for option in extra_options}
            game_reset_indexes = [
                index for index in g_game_config if index not in excluded_indexes
            ]
            game_changed = reset_to_defaults(
                g_game_config,
                game.config_defaults(),
                keep_masked,
                indexes=game_reset_indexes,
            )
            extra_changed = []
            for i, option in enumerate(extra_options):
                if toggle_states.get(str(i)):
                    extra_changed.extend(option.action(g_game_config))

            game_affected = set(game_changed) | set(extra_changed)
            for index in list(game_changed) + extra_changed:
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
    print_to_terminal("Checking for a newer sgsl version...")

    def worker():
        try:
            result = check_for_update(VERSION, printer=print_to_terminal)
        except Exception as e:
            # check_for_update() is documented to never raise -- this is
            # a last-resort safety net so a bug in it (or in a
            # print_to_terminal() listener it triggers, e.g.
            # Game.interpret_terminal_line()) surfaces here instead of
            # silently killing this daemon thread with nothing printed
            # anywhere. Falls back to a plain print() if even
            # print_to_terminal() itself is what's failing.
            try:
                print_to_terminal(f"Update check failed unexpectedly: {e}")
            except Exception:
                print(f"Update check failed unexpectedly: {e}")
            return

        def finish():
            if result is not None:
                new_version, release_url = result
                print_to_terminal(
                    f"A newer sgsl version is available: {new_version} ({release_url})"
                )
                _show_update_available_dialog(new_version, release_url)
            else:
                print_to_terminal("No newer sgsl version found")
                if manual:
                    set_status_line("You already have the latest version of sgsl")
                    restore_status_line_delayed()

        root.after(0, finish)

    threading.Thread(target=worker, daemon=True).start()


def on_check_for_updates():
    set_status_line("Checking for updates...")
    _check_for_update_in_background(manual=True)


def _show_server_update_available_dialog(game: Game) -> None:
    choice = choice_dialog(
        f"A newer build of {game.get_long_name()} is available than what's "
        "currently installed.",
        title="Server update available",
        choices=[
            ("Update now", "Start updating the server now", True),
            (
                "Later",
                "Dismiss -- you can still update anytime via the Update button",
                False,
            ),
        ],
        cancel_value=False,
    )
    if choice:
        g_update_open_close.on()
        on_update_game_server(game)


def _check_for_server_update_in_background(game: Game, manual: bool = False) -> None:
    """Check whether a newer server build is available for `game` on a
    background thread (network I/O, must not block startup), then hop
    back to the main thread via root.after() -- same pattern as
    _check_for_update_in_background() above, for sgsl's own updates --
    to show a dialog if one was found.

    `manual`, if True (a user-triggered check via the "Check for
    update" button, rather than the silent one done at startup), also
    gives feedback via the status line when no update is available or
    the check couldn't be completed, rather than doing nothing visible."""
    print_to_terminal(f"Checking for a {game.get_long_name()} server update...")

    def worker():
        try:
            needs_update = game.check_for_server_update()
        except Exception as e:
            # check_for_server_update() is documented to never raise --
            # see _check_for_update_in_background()'s matching try/except
            # for why this safety net exists.
            try:
                print_to_terminal(f"Server update check failed unexpectedly: {e}")
            except Exception:
                print(f"Server update check failed unexpectedly: {e}")
            return

        def finish():
            if needs_update:
                print_to_terminal(
                    f"A newer {game.get_long_name()} server build is available"
                )
                _show_server_update_available_dialog(game)
            else:
                message = (
                    f"{game.get_long_name()} is already up to date"
                    if needs_update is not None
                    else f"Could not check for a {game.get_long_name()} server update"
                )
                print_to_terminal(message)
                if manual:
                    set_status_line(message)
                    restore_status_line_delayed()

        root.after(0, finish)

    threading.Thread(target=worker, daemon=True).start()


def on_check_for_server_update(game: Game) -> None:
    set_status_line(f"Checking for a {game.get_long_name()} server update...")
    _check_for_server_update_in_background(game, manual=True)


# main

# Bundled by build-for-test.bat only (via a PyInstaller --add-data entry),
# containing the build timestamp -- so a build-for-test.bat build's main
# window title can be told apart from a release build's or a plain
# from-source run's, both of which lack this marker.
_TestBuildMarker = "app/assets/test_build.marker"


def _main_window_title() -> str:
    title = "Simple Game Server Launcher" + " " + VERSION
    marker = resource_path(_TestBuildMarker)
    if marker.exists():
        timestamp = marker.read_text(encoding="utf-8").strip()
        title += f" (Build for test {timestamp})"
    return title


root = ui.Window(title=_main_window_title())
root.protocol("WM_DELETE_WINDOW", on_close_main_window)

current_dir = os.getcwd()

g_app_config_file = Path(current_dir) / "sgsl.toml"
g_app_config = TomlConfigParser.read(g_app_config_file, build_app_defaults())
apply_upgraders(
    g_app_config,
    TomlConfigParser.read_version(g_app_config_file),
    APP_CONFIG_UPGRADERS,
)
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
    # Deferred via root.after() rather than called directly: it starts
    # a background thread that calls back into Tk (print_to_terminal())
    # as soon as it starts, which errors out ("main thread is not in
    # main loop") if that happens before root.mainloop() (below) has
    # actually started running -- scheduling it through root.after()
    # instead guarantees it only fires once the loop is live.
    root.after(0, _check_for_update_in_background)

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
        pass
    elif result == TerminalLineResult.MAP_DOWNLOAD_FAILED:
        pass
    elif result == TerminalLineResult.MAP_LOAD_FAILED:
        on_game_map_load_failed(game)
    _check_suspicious_terminal_line(game, line)


def _check_suspicious_terminal_line(game: Game, line: str) -> None:
    """Show a dialog the first time (per server run -- see
    g_shown_suspicious_line_patterns) `line` matches one of `game`'s
    own suspicious_terminal_line_patterns()."""
    global g_shown_suspicious_line_patterns
    pattern = game.find_suspicious_terminal_line_pattern(line)
    if pattern is None or pattern in g_shown_suspicious_line_patterns:
        return
    g_shown_suspicious_line_patterns.add(pattern)
    ok_dialog(
        "Something suspicious has happened on the server:\n\n"
        f"{line}\n\n"
        "The server may be in a broken state.",
        title="Suspicious server output detected",
    )


g_terminal_window.register_listener(on_terminal_line)

if game is None:
    setup_install_game(current_dir)
else:
    setup_detected_game_server(game)
    if (
        game.automatic_update_check_enabled(g_game_config)
        and not g_server_should_be_running
    ):
        # See the AUTOMATIC_UPDATE_CHECK root.after() above for why
        # this is deferred rather than called directly.
        root.after(0, lambda: _check_for_server_update_in_background(game))

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
