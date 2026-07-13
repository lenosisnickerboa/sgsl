from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Callable, Union

from config.config_item import ConfigItem
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from process import process_handler


class OperationResult(Enum):
    """Outcome reported to install()'s/update()'s result_callback."""

    OK = "OK"
    FAIL = "FAIL"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class Game(ABC):
    """Interface that every game implementation must follow."""

    def __init__(self, directory: Union[str, Path], terminal):
        self.directory = Path(directory)
        self.terminal = terminal
        self.server_root = self.directory / "server"
        self.server_root.mkdir(parents=True, exist_ok=True)
        self.process_handler = None

    def print(self, message: str) -> None:
        self.terminal(message)

    def get_directory(self) -> Path:
        return self.directory

    def handle_stdout_output(self, line: str):
        prefix = "[OUT]"
        self.print(f"{prefix} {line}")

    def handle_stderr_output(self, line: str):
        prefix = "[ERR]"
        self.print(f"{prefix} {line}")

    def handle_done(self, pid: int, returncode: int):
        self.print(f"Process tree {pid} finished with exit code {returncode}")

    def start_server(self, args) -> None:
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

    def stop_server(self):
        self.print(
            f'Stopping game server {self.get_long_name()} with executable "{self.get_server_binary_path()}" ...'
        )
        if not self.process_handler:
            return
        server_pids = self.process_handler.list_pids()
        if len(server_pids) > 0:
            self.process_handler.kill_pids(server_pids, timeout=10.0, force=True)
        self.print(
            f"Stopped game server {self.get_long_name()} with pids {server_pids}"
        )

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
    def run(self, config: Config[IndexT]) -> None:
        """Launch the game."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop the game."""
        raise NotImplementedError

    @abstractmethod
    def is_running(self) -> None:
        """Check if the game is running."""
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
