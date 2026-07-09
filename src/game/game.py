from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from process import process_handler


class Game(ABC):
    """Interface that every game implementation must follow."""

    def __init__(self, directory: Union[str, Path], terminal):
        self.directory = Path(directory)
        self.terminal = terminal
        self.pid = None
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
            self.process_handler = process_handler.ProcessHandler(self.get_server_binary_path())
        self.print(f"Starting game server {self.get_long_name()} with executable \"{self.get_server_binary_path()}\" and arguments \"{args}\"...")
        self.pid = self.process_handler.start(
            args,
            no_window=True, 
            stdout_callback=self.handle_stdout_output, 
            stderr_callback=self.handle_stderr_output, 
            on_exit=self.handle_done
        )
        self.print(f"Started game server {self.get_long_name()} with pid {self.pid}")

    def stop_server(self):
        self.print(f"Stopping game server {self.get_long_name()} with executable \"{self.get_server_binary_path()}\" ...")
        if not self.process_handler:
            return
        server_pids = self.process_handler.list_pids()
        if len(server_pids) > 0:
            self.process_handler.kill_pids(server_pids, timeout=10.0, force=True)
        self.print(f"Stopped game server {self.get_long_name()} with pids {server_pids}")

    def is_running(self) -> bool:
        """Check if the game is running."""
        if not self.process_handler:
            return False
        pids = self.process_handler.list_pids()
        print(f"Found {len(pids)} running server(s) {pids} for {self.get_long_name()} with executable {self.get_server_binary_path()}")
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
    def install(self) -> None:
        """Install the game into self.directory."""
        raise NotImplementedError

    @abstractmethod
    def update(self) -> None:
        """Update an already-installed game."""
        raise NotImplementedError

    @abstractmethod
    def run(self) -> None:
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
    def maps(self) -> list[str]:
        """Return a list of available maps for the game."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(directory={self.directory!r})"