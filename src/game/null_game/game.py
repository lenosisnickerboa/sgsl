from pathlib import Path
from typing import Callable, Union
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from game.game import Game, OperationResult
from game.null_game.config_defaults import build_game_defaults
from game.null_game.config_index import ConfigIndex

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

    def install(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Installing {self.get_long_name()} into {self.server_root}")
        self.print(f"touch({self.server_binary})")
        self.server_binary.touch(exist_ok=True)
        self.print(f"Installed {self.get_long_name()} into {self.server_root}")
        result_callback(OperationResult.OK)

    def update(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")
        result_callback(OperationResult.OK)

    def run(self, config: Config[IndexT]) -> None:
        self.print(f"Running {self.get_long_name()} from {self.server_root}")
        args = f"game_mode={config[ConfigIndex.GAME_MODE].value} map={config[ConfigIndex.SELECTED_MAP].value} player_count={config[ConfigIndex.PLAYER_COUNT].value} friendly_fire={config[ConfigIndex.FRIENDLY_FIRE_ENABLED].value}"
        self.print(f"Starting with args: {args}")
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

    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        maps = self.maps()
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = maps
        defaults[ConfigIndex.SELECTED_MAP].value = maps[0]
        return defaults

    def config_shortcuts(self) -> list[IndexT]:
        return [
            ConfigIndex.GAME_MODE,
            ConfigIndex.SELECTED_MAP,
            ConfigIndex.PLAYER_COUNT,
            ConfigIndex.FRIENDLY_FIRE_ENABLED,
        ]

    def config_tabs(self) -> list[TabSpec]:
        return [
            TabSpec(
                title="1st tab title",
                items=[ConfigIndex.DUMMY_0, ConfigIndex.DUMMY_1, ConfigIndex.PASSWORD],
            ),
            TabSpec(
                title="2nd tab title",
                items=[
                    ConfigIndex.DUMMY_2,
                    ConfigIndex.DUMMY_3,
                    ConfigIndex.BOT_DIFFICULTY,
                ],
            ),
            TabSpec(
                title="3rd tab title",
                items=[ConfigIndex.DUMMY_4, ConfigIndex.DUMMY_5, ConfigIndex.DUMMY_6],
            ),
        ]

    # def config_item_changed(self, config_item: IndexT, config: Config[IndexT]) -> None:
    #     self.print(f"config_item_changed({config_item}, {config})")
