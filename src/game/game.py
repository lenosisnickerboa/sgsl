from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union

from config.config_item import ConfigItem, ConfigType
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
        pid = handler.start(
            args,
            no_window=True,
            stdout_callback=self.handle_stdout_output,
            stderr_callback=self.handle_stderr_output,
            on_exit=self.handle_done,
        )
        self.print(f"Started game server {self.get_long_name()} with pid {pid}")

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
        """Append the item's default value, and its allowed values or
        range (whichever it has -- allowed_values wins if somehow both
        are set), to its tooltip -- each on its own new line -- so a
        user hovering over a config item can see both without having
        to look them up elsewhere. Shared across every game's
        config_defaults(): call this on each item in the returned
        Config, last, right before returning, so "default value"
        reflects whatever that method itself just computed (e.g. a
        detected maps list, a generated hostname) rather than a stale
        value from that game's build_game_defaults()."""
        lines = [item.tooltip] if item.tooltip else []
        default_value = (
            "********"
            if item.type is ConfigType.MASKED_STRING and item.value
            else item.value
        )
        lines.append(f"Default: {default_value}")
        if item.allowed_values is not None:
            values = ", ".join(str(v) for v in item.allowed_values)
            lines.append(f"Allowed values: {values}")
        elif item.range is not None:
            lines.append(f"Range: {item.range.describe()}")
        item.tooltip = "\n".join(lines)

    @abstractmethod
    def get_short_name(self) -> str:
        """Return the short name of the game."""
        raise NotImplementedError

    @abstractmethod
    def get_long_name(self) -> str:
        """Return the long name of the game."""
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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(directory={self.directory!r})"
