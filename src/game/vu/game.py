import shlex
from pathlib import Path
from typing import Callable, Optional, Union
from config.config_item import ConfigDeliveryType, ConfigItem, ConfigType
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from game.vu import maps_info
from game.vu import mode_info
from game.vu.config_defaults import build_game_defaults
from game.vu.config_index import ConfigIndex
from game.game import Game, OperationResult
from support.dialog import edit_string_dialog_box
from support.unzip import unzip_with_return
from support.wget import download_with_return

GameExe = "vu.exe"

# All relative to server root directory
GameExeWithPath = Path(GameExe)


class VUGame(Game):
    def __init__(self, directory: Union[str, Path], terminal):
        super().__init__(directory, terminal)
        self.server_binary = self.server_root / GameExeWithPath
        # Only set once config_loaded() runs, i.e. once the game is
        # already installed and its config exists — still None during
        # the initial install (config_defaults()/config_loaded() never
        # ran yet), so _install_or_update() falls back to the default
        # DOWNLOAD_URL in that case.
        self.config: Optional[Config[IndexT]] = None
        self.maps = maps_info.MapsInfo()
        self.modes = mode_info.ModeInfo()

    def detect(self) -> bool:
        return self.server_binary.exists()

    def get_short_name(self) -> str:
        return "vu"

    def get_long_name(self) -> str:
        return "Venice Unleashed"

    def install(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Installing {self.get_long_name()} into {self.server_root}")
        self._install_or_update(result_callback)

    def update(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")
        self._install_or_update(result_callback)

    _ArchiveFileName = "vu.zip"

    def _install_or_update(
        self, result_callback: Callable[[OperationResult], None]
    ) -> None:
        download_url = (
            self.config[ConfigIndex.DOWNLOAD_URL].value
            if self.config is not None
            else build_game_defaults()[ConfigIndex.DOWNLOAD_URL].value
        )

        archive_path = self.directory / self._ArchiveFileName
        self.print(
            f"Downloading {self.get_long_name()} server archive from {download_url} to {archive_path}..."
        )
        if not download_with_return(download_url, archive_path, self.print):
            self.print(
                f"Failed to download {self.get_long_name()} server archive from {download_url}"
            )
            result_callback(OperationResult.FAIL)
            return

        self.print(f"Extracting {archive_path} into {self.server_root}...")
        if not unzip_with_return(archive_path, self.server_root):
            self.print(f"Failed to extract {archive_path} into {self.server_root}")
            result_callback(OperationResult.FAIL)
            return

        archive_path.unlink(missing_ok=True)

        self.print(f"Installed {self.get_long_name()} into {self.server_root}")
        result_callback(OperationResult.OK)

    def run(self, config: Config[IndexT]) -> bool:
        args = [
            "-serverInstancePath",
            f"{self.server_root}",
            "-listen"
            f"{config[ConfigIndex.LISTEN_HOST].value}:{config[ConfigIndex.LISTEN_PORT_FROSTBITE].value}",
            "-mHarmonyPort" f"{config[ConfigIndex.LISTEN_PORT_HARMONY].value}",
            "-server",
            "-dedicated",
            "-headless",
        ]
        if config[ConfigIndex.RCON_ENABLE].value == True:
            args.append("-RemoteAdminPort")
            args.append(f"{config[ConfigIndex.LISTEN_PORT_RCON].value}")
        if config[ConfigIndex.SERVER_UPDATE_FREQUENCY].value == "60":
            args.append("-high60")
        elif config[ConfigIndex.SERVER_UPDATE_FREQUENCY].value == "120":
            args.append("-high120")
        self._write_server_cfg(config)
        if config[ConfigIndex.RUN_COMMAND_EDIT].value:
            edited = edit_string_dialog_box("Edit run command", " ".join(args))
            if edited is None:
                return False
            args = shlex.split(edited)
        super().start_server(args)
        return True

    _MapListFileName = Path("Admin") / "MapList.txt"
    _StartupFileName = Path("Admin") / "Startup.txt"
    _ModListFileName = Path("Admin") / "ModList.txt"

    def _write_server_cfg(self, config: Config[IndexT]) -> None:

        admin_dir = self.server_root / self._MapListFileName.parent
        admin_dir.mkdir(parents=True, exist_ok=True)

        selected_map_id = self.maps.id_from_name(
            config[ConfigIndex.SELECTED_MAP].value
        )
        selected_game_mode_id = self.modes.id_from_name(
            config[ConfigIndex.GAME_MODE].value
        )
        (self.server_root / self._MapListFileName).write_text(
            f'"{selected_map_id}" "{selected_game_mode_id}" "1"\n', encoding="utf-8"
        )

        startup_lines = [
            self._format_cvar_line(item)
            for item in config.values()
            if item.config_type is ConfigDeliveryType.SERVER_CFG_FILE
        ]
        (self.server_root / self._StartupFileName).write_text(
            "\n".join(startup_lines) + "\n", encoding="utf-8"
        )

        (self.server_root / self._ModListFileName).write_text(
            "# No mods yet\n", encoding="utf-8"
        )

    def _format_cvar_line(self, item: ConfigItem) -> str:
        if item.type in (
            ConfigType.STRING,
            ConfigType.STRING_LIST,
            ConfigType.MASKED_STRING,
        ):
            return f'{item.name} "{item.value}"'
        if item.type is ConfigType.BOOLEAN:
            return f"{item.name} {"true" if item.value else "false"}"
        return f"{item.name} {item.value}"

    def stop(self) -> None:
        super().stop_server()

    def is_running(self) -> bool:
        return super().is_server_running()

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        all_maps = self.maps.all_names()
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = all_maps
        defaults[ConfigIndex.SELECTED_MAP].value = all_maps[0]
        all_game_modes = self.modes.all_names()
        defaults[ConfigIndex.GAME_MODE].allowed_values = all_game_modes
        defaults[ConfigIndex.GAME_MODE].value = all_game_modes[0]
        return defaults

    def config_loaded(self, config: Config[IndexT]) -> None:
        self.config = config

    def config_shortcuts(self) -> list[IndexT]:
        return [
            ConfigIndex.GAME_MODE,
            ConfigIndex.SELECTED_MAP_GROUP,
            ConfigIndex.SELECTED_MAP,
            ConfigIndex.PLAYER_COUNT,
            ConfigIndex.FRIENDLY_FIRE,
        ]

    def config_tabs(self) -> list[TabSpec]:
        return [
            TabSpec(
                title="General",
                items=[
                    ConfigIndex.GAME_MODE,
                    ConfigIndex.SELECTED_MAP_GROUP,
                    ConfigIndex.SELECTED_MAP,
                    ConfigIndex.PLAYER_COUNT,
                    ConfigIndex.PLAYER_COUNT_START_ROUND,
                    ConfigIndex.PLAYER_COUNT_RESTART_ROUND,
                    ConfigIndex.FRIENDLY_FIRE,
                    ConfigIndex.RUN_COMMAND_EDIT,
                ],
            ),
            TabSpec(
                title="Server",
                items=[
                    ConfigIndex.SERVER_NAME,
                    ConfigIndex.SERVER_PASSWORD,
                    ConfigIndex.SERVER_UPDATE_FREQUENCY,
                ],
            ),
            TabSpec(
                title="Network",
                items=[
                    ConfigIndex.LISTEN_HOST,
                    ConfigIndex.LISTEN_PORT_FROSTBITE,
                    ConfigIndex.LISTEN_PORT_HARMONY,
                    ConfigIndex.RCON_ENABLE,
                    ConfigIndex.LISTEN_PORT_RCON,
                ],
            ),
            TabSpec(
                title="Downloads",
                items=[
                    ConfigIndex.DOWNLOAD_URL,
                ],
            ),
        ]

    def config_item_changed(self, config_item, config: Config[IndexT]) -> list[IndexT]:
        return []
