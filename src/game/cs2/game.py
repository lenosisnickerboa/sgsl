from pathlib import Path
from typing import Union
from game.game import Game


GameExe = "cs2.exe"

# All relative to server root directory
GameExeWithPath = Path("game") / "bin" / "win64" / GameExe

class CS2Game(Game):
    def __init__(self, directory: Union[str, Path], terminal):
        super().__init__(directory, terminal)
        self.server_binary = self.server_root / GameExeWithPath

    def detect(self) -> bool:
        return self.server_binary.exists()

    def get_short_name(self) -> str:
        return "cs2"

    def get_long_name(self) -> str:
        return "Counter-Strike 2"

    def install(self) -> None:
        self.print(f"Installing {self.get_long_name()} into {self.server_root}")

    def update(self) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")

    def run(self) -> None:
        args=["-dedicated", "-usercon", "+game_type", "0", "+game_mode", "1", "+map", "de_inferno"]
        super().start_server(args)

    def stop(self) -> None:
        super().stop_server()

    def is_running(self) -> bool:
        return super().is_running()

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def maps(self) -> list[str]:
        return [p.stem for p in (Path(self.server_root) / "game" / "csgo" / "maps").glob("*.vpk")]