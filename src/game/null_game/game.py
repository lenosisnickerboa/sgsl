from pathlib import Path
from typing import Union
from game.game import Game


GameExe = "null_game.exe"

# All relative to server root directory
GameExeWithPath = GameExe

class NullGame(Game):
    def __init__(self, directory: Union[str, Path], terminal):
        super().__init__(directory, terminal)
        self.running = False
        self.server_binary = self.server_root / GameExeWithPath

    def get_short_name(self) -> str:
        return "ng"

    def get_long_name(self) -> str:
        return "Null Game"

    def detect(self) -> bool:
        return self.server_binary.exists()

    def install(self) -> None:
        print(f"Installing {self.get_long_name()} into {self.server_root}")
        print(f"touch({self.server_binary})")
        self.server_binary.touch(exist_ok=True)
        print(f"Installed {self.get_long_name()} into {self.server_root}")

    def update(self) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")

    def run(self) -> None:
        self.print(f"Running {self.get_long_name()} from {self.server_root}")
        self.running = True

    def stop(self) -> None:
        self.print(f"Stopping {self.get_long_name()} from {self.server_root}")
        self.running = False

    def is_running(self) -> bool:
        return self.running

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def maps(self) -> list[str]:
        return ["NullGameMap1", "NullGameMap2", "NullGameMap3"]