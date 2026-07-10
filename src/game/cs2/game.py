from pathlib import Path
from typing import Union
from config.toml_config import Config, IndexT
from game.cs2.config_defaults import build_game_defaults
from game.cs2.config_index import ConfigIndex
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

    def run(self, config: Config[IndexT]) -> None:
        args=["-dedicated", "-usercon", "+game_type", "TYPE", "+game_mode", "MODE", "+map", "MAP", "-maxplayers", "<number>"]
        game_mode = config[ConfigIndex.GAME_MODE].value
        if game_mode == "Casual":
            args[3]="0" # game_type
            args[5]="0" # gamne_mode
        if game_mode == "Competitive":
            args[3]="0" # game_type
            args[5]="1" # gamne_mode
        elif game_mode == "ArmsRace":
            args[3]="1" # game_type
            args[5]="0" # gamne_mode
        elif game_mode == "DeathMatch":
            args[3]="1" # game_type
            args[5]="2" # gamne_mode
        elif game_mode == "Demolition":
            args[3]="1" # game_type
            args[5]="1" # gamne_mode
        else:
            exit(1)
        args[7]=config[ConfigIndex.SELECTED_MAP].value
        args[9]=str(config[ConfigIndex.PLAYER_COUNT].value)
        super().start_server(args)

    def stop(self) -> None:
        super().stop_server()

    def is_running(self) -> bool:
        return super().is_server_running()

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def maps(self) -> list[str]:
        return [p.stem for p in (Path(self.server_root) / "game" / "csgo" / "maps").glob("*.vpk")]
    
    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        maps = self.maps()
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = maps
        defaults[ConfigIndex.SELECTED_MAP].value = maps[0]
        return defaults

    def config_shortcuts(self) -> list[IndexT]:
        return [ConfigIndex.GAME_MODE, ConfigIndex.SELECTED_MAP_GROUP, ConfigIndex.SELECTED_MAP, ConfigIndex.PLAYER_COUNT]

    # def config_item_changed(self, config_item: IndexT, config: Config[IndexT]) -> None:
    #     self.print(f"config_item_changed({config_item}, {config})")
