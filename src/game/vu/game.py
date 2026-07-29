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
from game.game import Game, OperationResult, TerminalLineResult
from support import bat_runner
from support.dialog import edit_string_dialog_box

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
    _ModsDirName = Path("Admin") / "mods"
    _FunBotsArchiveFileName = "fun-bots.zip"

    # Bare "curl.exe"/"tar.exe" can resolve to Git for Windows' copies
    # earlier on PATH than the Windows-native ones in System32; Git's
    # GNU tar misreads a bare drive-letter path like "C:\..." as a
    # host:path remote-tape spec and fails ("Cannot connect to C:"), so
    # pin to the Windows-native executables by their full paths.
    #    _CurlExe = r"%SystemRoot%\System32\curl.exe"
    _CurlExe = r"curl.exe"
    #    _TarExe = r"%SystemRoot%\System32\tar.exe"
    _TarExe = r"tar.exe"

    def _install_or_update(
        self, result_callback: Callable[[OperationResult], None]
    ) -> None:
        config = self.config if self.config is not None else build_game_defaults()

        download_url = config[ConfigIndex.DOWNLOAD_URL].value
        archive_path = self.directory / self._ArchiveFileName
        commands = [
            f'{self._CurlExe} -fsSL "{download_url}" -o "{archive_path}"',
            f'{self._TarExe} -xf "{archive_path}" -C "{self.server_root}"',
        ]

        fun_bots_enabled = config[ConfigIndex.MODS_FUN_BOTS_ENABLED].value
        fun_bots_archive_path = self.directory / self._FunBotsArchiveFileName
        if fun_bots_enabled:
            mods_url = config[ConfigIndex.MODS_FUN_BOTS_URL].value
            mods_dir = self.server_root / self._ModsDirName
            mods_dir.mkdir(parents=True, exist_ok=True)
            commands += [
                f'{self._CurlExe} -fsSL "{mods_url}" -o "{fun_bots_archive_path}"',
                f'{self._TarExe} -xf "{fun_bots_archive_path}" -C "{mods_dir}"',
            ]

        def on_output(line: str) -> None:
            self.print(line)

        def on_result(exit_code: int) -> None:
            archive_path.unlink(missing_ok=True)
            if fun_bots_enabled:
                fun_bots_archive_path.unlink(missing_ok=True)

            if not self.server_binary.exists():
                self.print(
                    f"Failed to install {self.get_long_name()} into {self.server_root} "
                    f"(exit code {exit_code})"
                )
                result_callback(OperationResult.FAIL)
                return

            self.print(f"Installed {self.get_long_name()} into {self.server_root}")
            result_callback(OperationResult.OK)

        bat_runner.run(commands, self.directory, on_output, on_result)

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
        args = (
            shlex.split(config[ConfigIndex.CUSTOM_RUN_COMMAND_PRE].value)
            + args
            + shlex.split(config[ConfigIndex.CUSTOM_RUN_COMMAND_POST].value)
        )
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

    def _read_append_lines(self, path: Path) -> list[str]:
        """If a sibling <stem>_append<suffix> file exists next to path
        (e.g. Startup_append.txt next to Startup.txt), return its
        non-blank lines to be appended after sgsl's own generated
        content -- an optional escape hatch for lines sgsl has no
        config item for, mirroring the CS2/CSGO gamemode append cfg
        files. Purely optional -- most setups won't have one."""
        append_path = path.with_name(f"{path.stem}_append{path.suffix}")
        if not append_path.exists():
            return []
        return [
            line
            for line in append_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_server_cfg(self, config: Config[IndexT]) -> None:

        admin_dir = self.server_root / self._MapListFileName.parent
        admin_dir.mkdir(parents=True, exist_ok=True)

        selected_map_id = self.maps.id_from_name(config[ConfigIndex.SELECTED_MAP].value)
        selected_game_mode_id = self.modes.id_from_name(
            config[ConfigIndex.GAME_MODE].value
        )
        map_list_path = self.server_root / self._MapListFileName
        map_list_lines = [
            f'"{selected_map_id}" "{selected_game_mode_id}" "1"'
        ] + self._read_append_lines(map_list_path)
        map_list_path.write_text("\n".join(map_list_lines) + "\n", encoding="utf-8")

        startup_path = self.server_root / self._StartupFileName
        startup_lines = [
            self._format_cvar_line(item)
            for item in config.values()
            if item.config_type is ConfigDeliveryType.SERVER_CFG_FILE
        ] + self._read_append_lines(startup_path)
        startup_path.write_text("\n".join(startup_lines) + "\n", encoding="utf-8")

        self._write_mod_list(config)

    _FunBotsRepoName = "fun-bots"
    _NoModsPlaceholder = "# No mods yet"

    def _find_fun_bots_mod_dir_name(self) -> Optional[str]:
        """The fun-bots archive extracts into a folder named after its
        repo and release tag (e.g. "fun-bots-3.0.0-Release"), which
        varies with MODS_FUN_BOTS_URL — so look up the actual folder
        under Admin/mods rather than guessing the name."""
        mods_dir = self.server_root / self._ModsDirName
        if not mods_dir.is_dir():
            return None
        for entry in mods_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(self._FunBotsRepoName):
                return entry.name
        return None

    def _write_mod_list(self, config: Config[IndexT]) -> None:
        mod_list_path = self.server_root / self._ModListFileName
        append_lines = self._read_append_lines(mod_list_path)

        existing_lines = []
        if mod_list_path.exists():
            existing_lines = [
                line
                for line in mod_list_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
                and line.strip() != self._NoModsPlaceholder
                and not line.strip().startswith(self._FunBotsRepoName)
                # Otherwise, since this file's own previous output is
                # what feeds existing_lines, re-appending append_lines
                # below would duplicate them on every subsequent run.
                and line not in append_lines
            ]

        if config[ConfigIndex.MODS_FUN_BOTS_ENABLED].value:
            fun_bots_dir_name = self._find_fun_bots_mod_dir_name()
            if fun_bots_dir_name is not None:
                existing_lines.append(fun_bots_dir_name)

        existing_lines += append_lines

        if not existing_lines:
            existing_lines = [self._NoModsPlaceholder]

        mod_list_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

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

    def stop(self) -> bool:
        return super().stop_server()

    def is_running(self) -> bool:
        return super().is_server_running()

    def interpret_terminal_line(self, line: str) -> TerminalLineResult:
        return TerminalLineResult.OK

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        all_maps = self.maps.all_names()
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = all_maps
        defaults[ConfigIndex.SELECTED_MAP].value = all_maps[0]
        # Separate list copies, not the same object as SELECTED_MAP's —
        # ORDINARY_MAPS is user-editable, so it shouldn't share a
        # mutable list with (and risk silently altering) another
        # item's allowed_values/value.
        defaults[ConfigIndex.ORDINARY_MAPS].allowed_values = list(all_maps)
        defaults[ConfigIndex.ORDINARY_MAPS].value = list(all_maps)
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
                    ConfigIndex.CUSTOM_RUN_COMMAND_PRE,
                    ConfigIndex.CUSTOM_RUN_COMMAND_POST,
                ],
            ),
            TabSpec(
                title="Server",
                items=[
                    ConfigIndex.SERVER_NAME,
                    ConfigIndex.SERVER_PASSWORD,
                    ConfigIndex.SERVER_UPDATE_FREQUENCY,
                    ConfigIndex.COLOR_CORRECTION_ENABLED,
                    ConfigIndex.SQUAD_SIZE,
                    ConfigIndex.SUN_FLARE_ENABLED,
                    ConfigIndex.DISABLE_PRE_ROUND,
                    ConfigIndex.CORPSE_DAMAGE_ENABLED,
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
            TabSpec(
                title="Mods",
                items=[
                    ConfigIndex.MODS_FUN_BOTS_ENABLED,
                    ConfigIndex.MODS_FUN_BOTS_URL,
                ],
            ),
            TabSpec(
                title="Maps",
                items=[ConfigIndex.ORDINARY_MAPS],
            ),
            TabSpec(
                title="Map groups",
                items=[
                    ConfigIndex.ORDINARY_MAPGROUPS,
                    ConfigIndex.ORDINARY_MAPGROUP,
                    ConfigIndex.ORDINARY_MAPGROUP_LIST,
                ],
            ),
        ]

    def config_item_changed(self, config_item, config: Config[IndexT]) -> list[IndexT]:
        return []
