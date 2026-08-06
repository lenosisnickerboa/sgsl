from __future__ import annotations

import subprocess
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union

from config.config_item import ConfigItem, ConfigType, finalize_default
from config.config_upgrader import ConfigUpgrader
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from process import process_handler


def _is_blank_line(line: str) -> bool:
    """True if `line` has no real content -- empty, or every character
    in it is whitespace and/or a control character (e.g. a stray
    ANSI/null/backspace byte some game server processes emit on their
    own "line"), so it's not worth showing in the terminal."""
    return all(ch.isspace() or unicodedata.category(ch) == "Cc" for ch in line)


class OperationResult(Enum):
    """Outcome reported to install()'s/update()'s result_callback."""

    OK = "OK"
    FAIL = "FAIL"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class TerminalLineResult(Enum):
    """Outcome of interpret_terminal_line(): what, if anything, a
    single line of terminal output revealed about the game's state.
    Only report stuff which happens assynchronously."""

    OK = "OK"
    MAP_LOAD_FAILED = "MAP_LOAD_FAILED"


@dataclass
class ExtraResetOption:
    """One opt-in "remove ..." toggle offered by the application's
    top-level Set Defaults dialog -- see Game.extra_reset_options().

    `index` is the config index this option governs; it's excluded
    from the dialog's normal reset pass unconditionally, whether or
    not this option's own toggle ends up checked.

    `action`, called only if the toggle is checked (after the normal
    reset pass has already run), performs the actual removal --
    including any side effect beyond the config value itself, e.g.
    deleting downloaded files -- and returns the indexes changed, the
    same contract as Game.config_item_changed()."""

    label: str
    tooltip: str
    index: IndexT
    action: Callable[[Config[IndexT]], list[IndexT]]


class Game(ABC):
    """Interface that every game implementation must follow."""

    def __init__(self, directory: Union[str, Path], terminal):
        self.directory = Path(directory)
        self.terminal = terminal
        self.server_root = self.directory / "server"
        self.server_root.mkdir(parents=True, exist_ok=True)
        self.process_handler = None
        self.filter_stdout = None
        self.filter_stderr = None

    def print(self, message: str) -> None:
        self.terminal(message)

    def get_directory(self) -> Path:
        return self.directory

    def handle_stdout_output(self, line: str):
        if _is_blank_line(line):
            return
        if self.filter_stdout:
            line = self.filter_stdout(line)
            if not line:
                return
        prefix = "[OUT]"
        self.print(f"{prefix} {line}")

    def handle_stderr_output(self, line: str):
        if _is_blank_line(line):
            return
        if self.filter_stderr:
            line = self.filter_stderr(line)
            if not line:
                return
        prefix = "[ERR]"
        self.print(f"{prefix} {line}")

    def handle_done(self, pid: int, returncode: int):
        self.print(f"Process tree {pid} finished with exit code {returncode}")

    def _ensure_process_handler(self) -> process_handler.ProcessHandler:
        """Lazily create process_handler if this is the first thing to
        need it this session -- it's only ever built once, here, but
        this must not be start_server()'s job alone: sgsl.exe may have
        been closed and reopened while the server it started kept
        running, so stop_server()/is_server_running() need to be able
        to find that already-running process too, without a start_server()
        call in this session to have created it first."""
        if not self.process_handler:
            self.process_handler = process_handler.ProcessHandler(
                self.get_server_binary_path()
            )
        return self.process_handler

    def start_server(
        self,
        args,
        filter_stdout: Optional[Callable[[str], str]] = None,
        filter_stderr: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.filter_stdout = filter_stdout
        self.filter_stderr = filter_stderr
        handler = self._ensure_process_handler()
        self.print(
            f'Starting game server {self.get_long_name()} with executable "{self.get_server_binary_path()}" and arguments "{args}"...'
        )
        self._write_run_bat(args)
        pid = handler.start(
            args,
            no_window=True,
            stdout_callback=self.handle_stdout_output,
            stderr_callback=self.handle_stderr_output,
            on_exit=self.handle_done,
        )
        self.print(f"Started game server {self.get_long_name()} with pid {pid}")

    _RunBatFileName = "run_game_server.bat"

    def _write_run_bat(self, args) -> None:
        """Write a run_game_server.bat in the install folder containing
        the exact command line start_server() is about to launch -- lets a
        user start the server the same way sgsl would, without sgsl itself
        (e.g. from a scheduled task, or a machine sgsl isn't installed on)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        command_line = subprocess.list2cmdline(
            [str(self.get_server_binary_path())] + list(args)
        )
        (self.directory / self._RunBatFileName).write_text(
            f"REM Generated by sgsl.exe {timestamp}\r\n{command_line}\r\n",
            encoding="utf-8",
        )

    def stop_server(self) -> bool:
        self.print(
            f'Stopping game server {self.get_long_name()} with executable "{self.get_server_binary_path()}" ...'
        )
        handler = self._ensure_process_handler()
        server_pids = handler.list_pids()
        failed_pids = (
            handler.kill_pids(server_pids, timeout=10.0, force=True)
            if server_pids
            else []
        )
        if failed_pids:
            self.print(
                f"Failed to stop game server {self.get_long_name()}, still running pids {failed_pids}"
            )
            return False
        self.print(
            f"Stopped game server {self.get_long_name()} with pids {server_pids}"
        )
        return True

    def is_server_running(self) -> bool:
        """Check if the game is running. No logging -- called
        periodically (e.g. to poll for a crash), so it must stay
        quiet."""
        pids = self._ensure_process_handler().list_pids()
        return len(pids) > 0

    def _append_default_and_range_to_tooltip(self, item: ConfigItem) -> None:
        """Snapshot the item's default value (see
        config.config_item.finalize_default(), which also appends the
        "Default: ..."/"Range: ..."/"Allowed values: ..." lines to its
        tooltip), then append its underlying variable name too -- so a
        user hovering over a config item can see all of that without
        having to look it up elsewhere. Shared across every game's
        config_defaults(): call this on each item in the returned
        Config, last, right before returning, so "default value"
        reflects whatever that method itself just computed (e.g. a
        detected maps list, a generated hostname) rather than a stale
        value from that game's build_game_defaults()."""
        finalize_default(item)
        item.tooltip = f"{item.tooltip}\nUnderlying variable: {item.name}"

    @abstractmethod
    def get_short_name(self) -> str:
        """Return the short name of the game."""
        raise NotImplementedError

    @abstractmethod
    def get_long_name(self) -> str:
        """Return the long name of the game."""
        raise NotImplementedError

    @abstractmethod
    def get_developer_url(self) -> str:
        """Return the URL of the game's developer/publisher page (e.g.
        its store page, or its own site), shown to the user via a
        "Developer" button."""
        raise NotImplementedError

    @abstractmethod
    def detect(self) -> bool:
        """Return True if the game is present/installed at self.directory."""
        raise NotImplementedError

    @abstractmethod
    def install(self, result_callback: Callable[[OperationResult], None]) -> None:
        """Install the game into self.directory. Must call
        result_callback exactly once with the outcome (OK, FAIL, or
        NOT_SUPPORTED)."""
        raise NotImplementedError

    @abstractmethod
    def update(self, result_callback: Callable[[OperationResult], None]) -> None:
        """Update an already-installed game. Must call result_callback
        exactly once with the outcome (OK, FAIL, or NOT_SUPPORTED)."""
        raise NotImplementedError

    def check_for_server_update(self) -> Optional[bool]:
        """True if a newer server build is available from this game's
        distribution platform than what's currently installed, False
        if already up to date, or None if that can't be determined
        (not installed yet, offline, this game doesn't support the
        check, ...) -- a caller treats None the same as False (nothing
        to report), just without implying the install actually is
        current. Best-effort and non-critical: must never raise.
        None by default; override for a game that can actually check
        (e.g. a Steam app comparing its appmanifest buildid against
        Steam's public API -- see support/steam_app_update_check.py)."""
        return None

    def automatic_update_check_enabled(self, config: Config[IndexT]) -> bool:
        """True if `config` wants check_for_server_update() run
        automatically at startup -- a caller checks this before
        bothering to run that check at all, the same way rcon_enabled()
        gates an RCON action. False by default (also covers a game with
        no such setting of its own, e.g. because check_for_server_update()
        is unsupported there too); override together with a config item
        for a game that offers the toggle (e.g.
        ConfigIndex.AUTOMATIC_GAME_UPDATE_CHECK)."""
        return False

    @abstractmethod
    def run(self, config: Config[IndexT]) -> bool:
        """Launch the game. Returns True if the server was actually
        started, or False if the launch was aborted (e.g. the user
        cancelled an "edit run command" dialog) — callers must not
        treat the server as running in that case."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> bool:
        """Stop the game. Returns True if the server was successfully
        stopped, or False otherwise."""
        raise NotImplementedError

    @abstractmethod
    def is_running(self) -> None:
        """Check if the game is running."""
        raise NotImplementedError

    @abstractmethod
    def interpret_terminal_line(self, line: str) -> TerminalLineResult:
        """Inspect a single line of terminal output and report what it
        reveals about the game's state, if anything. Called for every
        line printed to the terminal while this is the active game."""
        raise NotImplementedError

    @abstractmethod
    def get_server_binary_path(self) -> Path:
        """Return the path to the game server binary."""
        raise NotImplementedError

    @abstractmethod
    def config_defaults(self) -> Config[IndexT]:
        """Return default config for the game."""
        raise NotImplementedError

    @abstractmethod
    def config_shortcuts(self) -> list[IndexT]:
        """Return a list of config items to include in the shortcut menu for the game."""
        raise NotImplementedError

    @abstractmethod
    def config_tabs(self) -> list[TabSpec]:
        """Return the tab layout for the detailed configuration window
        opened by the Configure button. The default puts every config
        item on a single "General" tab; override to group items across
        multiple tabs."""
        raise NotImplementedError

    def config_item_changed(
        self, config_item: ConfigItem, config: Config[IndexT]
    ) -> list[IndexT]:
        """Called after a UI edit has already updated config_item's
        value in `config`. The default is a no-op; override to react
        to specific changes, e.g. keeping other config items in sync.

        Return a list of indexes (may include ones this method itself
        mutated, e.g. another item's allowed_values/value) whose
        widgets should be refreshed to reflect changes made here, in
        addition to config_item's own index (already handled by the
        caller). Empty by default."""
        return []

    @abstractmethod
    def config_loaded(self, config: Config[IndexT]) -> None:
        """Return default config for the game."""
        raise NotImplementedError

    def config_version(self) -> int:
        """Current config schema version for this game -- bump
        whenever an entry is added to config_upgraders() so a saved
        game.toml from before that change gets migrated (see
        config.config_upgrader.apply_upgraders()) on next load. Starts
        at 1; override together with config_upgraders() when a
        migration is first needed."""
        return 1

    def config_upgraders(self) -> list[ConfigUpgrader]:
        """Migrations to apply, in order, to a saved config from an
        older config_version() -- see
        config.config_upgrader.apply_upgraders(). Empty by default."""
        return []

    def extra_reset_options(self) -> list[ExtraResetOption]:
        """Opt-in "remove ..." toggles offered by the application's
        top-level Set Defaults dialog, for bulk content a routine
        reset-to-defaults shouldn't touch just because it's unrelated
        to whatever the user actually meant to reset -- e.g. downloaded
        workshop maps, or user-defined map groups (see
        ExtraResetOption). Each returned option's `index` is excluded
        from that dialog's normal All/All-excluding-masked reset pass
        regardless of whether its own toggle is checked, so the only
        way to actually clear it is to check that toggle explicitly.

        Empty by default -- nothing excluded, the normal reset covers
        every index, same as a game with no such content at all."""
        return []

    def error_report_files(self) -> list[str]:
        """Return extra file paths to bundle into an error report, in
        addition to the terminal log and config files sgsl always
        includes. Each path is relative to the install directory (i.e.
        self.directory, the parent of self.server_root) -- not an
        absolute path, and not relative to self.server_root itself.
        A path that doesn't currently exist is silently skipped rather
        than failing the report. Empty by default; override to add
        game-specific logs/state useful for diagnosing issues."""
        raise NotImplementedError

    def supports_rcon(self) -> bool:
        """True if this game can be controlled via an interactive RCON
        console (see send_rcon_command()) -- a caller uses this to
        decide whether to offer an RCON button/window at all. False by
        default; override together with send_rcon_command() for a
        game that supports it."""
        return False

    def rcon_enabled(self, config: Config[IndexT]) -> bool:
        """True if `config` currently has RCON enabled -- a caller
        checks this before even bothering to check whether the server
        is running, so "RCON is disabled" takes priority over "server
        isn't running" when both are true. Only ever called when
        supports_rcon() is True -- unimplemented otherwise, the same
        as send_rcon_command()."""
        raise NotImplementedError

    def rcon_password_configured(self, config: Config[IndexT]) -> bool:
        """True if `config` has everything RCON needs to actually work
        beyond just being enabled (see rcon_enabled()) -- e.g. a
        non-empty password. True by default (nothing else to check);
        override for a game whose RCON setup has such a requirement.
        Only ever called when supports_rcon() is True, the same as
        rcon_enabled()."""
        return True

    def send_rcon_command(self, command: str, config: Config[IndexT]) -> str:
        """Send `command` over RCON to the running server and return
        its response text; may raise (e.g. RuntimeError if RCON isn't
        enabled/configured, or support.rcon_client.RconError for a
        connection/protocol failure) to report a failure instead.
        Only ever called when supports_rcon() is True -- unimplemented
        otherwise, the same as any other method a subclass is expected
        to override in that case."""
        raise NotImplementedError

    def rcon_quick_commands(self) -> list[str]:
        """A curated shortlist of this game's commonly used RCON
        commands, shown as one-click-insert buttons in the RCON
        console (see ui.rcon_window.RconWindow). Empty by default --
        override for a game whose console supports RCON at all (see
        supports_rcon()); returning no commands just means no buttons
        are shown, rather than failing outright."""
        return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(directory={self.directory!r})"
