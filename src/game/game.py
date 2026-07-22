from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union

from config.config_item import ConfigItem
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from process import process_handler


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
    SERVER_CRASHED = "SERVER_CRASHED"
    MAP_DOWNLOAD_FAILED = "MAP_DOWNLOAD_FAILED"
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
        # Set while a stop() (via stop_server()) is in progress, so
        # handle_done() can tell an intentional stop apart from the
        # server process disappearing on its own -- i.e. a crash.
        self._stop_requested = False

    def print(self, message: str) -> None:
        self.terminal(message)

    def get_directory(self) -> Path:
        return self.directory

    def handle_stdout_output(self, line: str):
        if self.filter_stdout:
            line = self.filter_stdout(line)
            if not line:
                return
        prefix = "[OUT]"
        self.print(f"{prefix} {line}")

    def handle_stderr_output(self, line: str):
        if self.filter_stderr:
            line = self.filter_stderr(line)
            if not line:
                return
        prefix = "[ERR]"
        self.print(f"{prefix} {line}")

    def handle_done(self, pid: int, returncode: int):
        self.print(f"Process tree {pid} finished with exit code {returncode}")
        if not self._stop_requested:
            # Same marker text null_game.py's simulated crash uses --
            # lets interpret_terminal_line() implementations detect a
            # crash the same way regardless of which game it is.
            self.print("Server crashed")

    def start_server(
        self,
        args,
        filter_stdout: Optional[Callable[[str], str]] = None,
        filter_stderr: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.filter_stdout = filter_stdout
        self.filter_stderr = filter_stderr
        self._stop_requested = False
        if not self.process_handler:
            self.process_handler = process_handler.ProcessHandler(
                self.get_server_binary_path()
            )
        self.print(
            f'Starting game server {self.get_long_name()} with executable "{self.get_server_binary_path()}" and arguments "{args}"...'
        )
        pid = self.process_handler.start(
            args,
            no_window=True,
            stdout_callback=self.handle_stdout_output,
            stderr_callback=self.handle_stderr_output,
            on_exit=self.handle_done,
        )
        self.print(f"Started game server {self.get_long_name()} with pid {pid}")

    def stop_server(self) -> bool:
        self._stop_requested = True
        self.print(
            f'Stopping game server {self.get_long_name()} with executable "{self.get_server_binary_path()}" ...'
        )
        if not self.process_handler:
            return True
        server_pids = self.process_handler.list_pids()
        failed_pids = (
            self.process_handler.kill_pids(server_pids, timeout=10.0, force=True)
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
        """Check if the game is running."""
        if not self.process_handler:
            return False
        pids = self.process_handler.list_pids()
        self.print(
            f"Found {len(pids)} running server(s) {pids} for {self.get_long_name()} with executable {self.get_server_binary_path()}"
        )
        return len(pids) > 0

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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(directory={self.directory!r})"
