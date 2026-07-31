import getpass
import socket
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
from support.run_command import split_run_command

GameExe = "vu.com"

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
    _VotemapArchiveFileName = "votemap.zip"

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

        votemap_enabled = config[ConfigIndex.MODS_VOTEMAP_ENABLED].value
        votemap_archive_path = self.directory / self._VotemapArchiveFileName
        if votemap_enabled:
            votemap_url = config[ConfigIndex.MODS_VOTEMAP_URL].value
            votemap_dir = self.server_root / self._ModsDirName / self._VotemapModDirName
            votemap_dir.mkdir(parents=True, exist_ok=True)
            commands += [
                f'{self._CurlExe} -fsSL "{votemap_url}" -o "{votemap_archive_path}"',
                # --strip-components=1 drops the archive's own
                # top-level folder (named after its repo/branch, e.g.
                # "BF3-Mods-Votemap-main", which would otherwise vary
                # with MODS_VOTEMAP_URL) so its contents land directly
                # in a fixed, predictable folder name instead.
                f'{self._TarExe} -xf "{votemap_archive_path}" -C "{votemap_dir}" --strip-components=1',
            ]

        def on_output(line: str) -> None:
            self.print(line)

        def on_result(exit_code: int) -> None:
            archive_path.unlink(missing_ok=True)
            if fun_bots_enabled:
                fun_bots_archive_path.unlink(missing_ok=True)
            if votemap_enabled:
                votemap_archive_path.unlink(missing_ok=True)

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
            f"{config[ConfigIndex.LISTEN_ADDRESS].value}:{config[ConfigIndex.LISTEN_PORT_FROSTBITE].value}",
            "-mHarmonyPort" f"{config[ConfigIndex.LISTEN_PORT_HARMONY].value}",
            "-server",
            "-dedicated",
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
            split_run_command(config[ConfigIndex.CUSTOM_RUN_COMMAND_PRE].value)
            + args
            + split_run_command(config[ConfigIndex.CUSTOM_RUN_COMMAND_POST].value)
        )
        if config[ConfigIndex.RUN_COMMAND_EDIT].value:
            edited = edit_string_dialog_box("Edit run command", " ".join(args))
            if edited is None:
                return False
            args = split_run_command(edited)
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

        map_list_path = self.server_root / self._MapListFileName
        map_list_lines = self._map_list_lines(config) + self._read_append_lines(
            map_list_path
        )
        map_list_path.write_text("\n".join(map_list_lines) + "\n", encoding="utf-8")

        startup_path = self.server_root / self._StartupFileName
        startup_lines = [
            self._format_cvar_line(item)
            for item in config.values()
            if item.config_type is ConfigDeliveryType.SERVER_CFG_FILE
        ] + self._read_append_lines(startup_path)
        startup_path.write_text("\n".join(startup_lines) + "\n", encoding="utf-8")

        self._write_mod_list(config)

    def _map_list_lines(self, config: Config[IndexT]) -> list[str]:
        """The generated (pre-append) lines for MapList.txt: one line
        per map/mode/rounds entry of the selected map group, if
        SELECTED_MAP_GROUP names a real group in ORDINARY_MAPGROUPS —
        otherwise just the single selected map/mode, rounds hardcoded
        to 1, same as before ORDINARY_MAPGROUPS existed."""
        selected_map_group = config[ConfigIndex.SELECTED_MAP_GROUP].value
        if selected_map_group and selected_map_group != "ALL":
            group = self._find_map_group(config, selected_map_group)
            if group is not None:
                return [
                    f'{self.maps.id_from_name(entry["name"])} '
                    f'{self.modes.id_from_name(entry["mode"])} '
                    f'{entry["rounds"]}'
                    for entry in group
                ]

        selected_map_id = self.maps.id_from_name(config[ConfigIndex.SELECTED_MAP].value)
        selected_game_mode_id = self.modes.id_from_name(
            config[ConfigIndex.GAME_MODE].value
        )
        return [f"{selected_map_id} {selected_game_mode_id} 1"]

    def _find_map_group(self, config: Config[IndexT], key: str) -> Optional[list[dict]]:
        """The list of {"name", "mode", "rounds"} entries stored under
        `key` in ORDINARY_MAPGROUPS, or None if no such group exists."""
        for entry in config[ConfigIndex.ORDINARY_MAPGROUPS].value:
            if entry["key"] == key:
                return entry["value"]
        return None

    _FunBotsRepoName = "fun-bots"
    # Fixed (see _install_or_update()'s --strip-components=1), unlike
    # fun-bots' folder name, which still varies with its release tag.
    _VotemapModDirName = "vu-mapvote"
    _NoModsPlaceholder = "# No mods yet"

    def _find_mod_dir_name(self, repo_name: str) -> Optional[str]:
        """A mod's archive extracts into a folder named after its repo
        and release tag/branch (e.g. "fun-bots-3.0.0-Release" or
        "BF3-Mods-Votemap-main"), which varies with its own URL config
        item — so look up the actual folder under Admin/mods by its
        repo-name prefix, rather than guessing the full name."""
        mods_dir = self.server_root / self._ModsDirName
        if not mods_dir.is_dir():
            return None
        for entry in mods_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(repo_name):
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
                and line.strip() != self._VotemapModDirName
                # Otherwise, since this file's own previous output is
                # what feeds existing_lines, re-appending append_lines
                # below would duplicate them on every subsequent run.
                and line not in append_lines
            ]

        if config[ConfigIndex.MODS_FUN_BOTS_ENABLED].value:
            fun_bots_dir_name = self._find_mod_dir_name(self._FunBotsRepoName)
            if fun_bots_dir_name is not None:
                existing_lines.append(fun_bots_dir_name)

        if config[ConfigIndex.MODS_VOTEMAP_ENABLED].value:
            votemap_dir = self.server_root / self._ModsDirName / self._VotemapModDirName
            if votemap_dir.is_dir():
                existing_lines.append(self._VotemapModDirName)

        existing_lines += append_lines

        if not existing_lines:
            existing_lines = [self._NoModsPlaceholder]

        mod_list_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

    def _format_cvar_line(self, item: ConfigItem) -> str:
        if item.name == "vars.roundTimeLimit":
            # Stored/edited in minutes (ROUND_TIME, matching cs2's
            # "Round time (min)"), but the cvar itself takes a
            # percentage of a 30-minute baseline round length.
            percentage = round(item.value / 30 * 100)
            return f"{item.name} {percentage}"
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
        username = getpass.getuser()  # current logged-in user
        hostname = socket.gethostname()  # machine's hostname
        defaults[ConfigIndex.SERVER_NAME].value = f"My server {username}@{hostname}"

        for item in defaults.values():
            self._append_default_and_range_to_tooltip(item)

        return defaults

    def config_loaded(self, config: Config[IndexT]) -> None:
        self.config = config
        # Picks up whatever map groups were just loaded from the saved
        # config, since config_defaults() alone only ever sees an
        # empty ORDINARY_MAPGROUPS (the TOML values haven't been
        # merged in yet at that point).
        self._refresh_map_group_choices(config)
        # Likewise for SELECTED_MAP's enabled/allowed_values state,
        # which depends on whatever SELECTED_MAP_GROUP was just loaded.
        self._sync_selected_map_state(config)

    def _refresh_map_group_choices(self, config: Config[IndexT]) -> None:
        """Keep the selected-map-group dropdown's choices in sync with
        the user-defined map groups (plus the built-in "ALL"); if the
        currently selected group was renamed/removed, fall back to
        "ALL"."""
        group_keys = [
            entry["key"] for entry in config[ConfigIndex.ORDINARY_MAPGROUPS].value
        ]
        choices = ["ALL"] + group_keys
        config[ConfigIndex.SELECTED_MAP_GROUP].allowed_values = choices
        if config[ConfigIndex.SELECTED_MAP_GROUP].value not in choices:
            config[ConfigIndex.SELECTED_MAP_GROUP].set("ALL")

    def _sync_selected_map_state(self, config: Config[IndexT]) -> None:
        """SELECTED_MAP only means anything when every map is in play
        ("ALL") — once a custom map group is selected, the maps to
        play come from that group's own list instead (see
        _map_list_lines()), so disable SELECTED_MAP rather than leave
        an edit sitting there with no effect. Re-enables it (with the
        full map list restored) when back on "ALL"."""
        select_all = config[ConfigIndex.SELECTED_MAP_GROUP].value == "ALL"
        config[ConfigIndex.SELECTED_MAP].read_only = not select_all
        if select_all:
            config[ConfigIndex.SELECTED_MAP].allowed_values = self.maps.all_names()

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
                    ConfigIndex.ROUND_TIME,
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
                    ConfigIndex.LISTEN_ADDRESS,
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
                    ConfigIndex.MODS_VOTEMAP_ENABLED,
                    ConfigIndex.MODS_VOTEMAP_URL,
                ],
            ),
            TabSpec(
                title="Maps",
                items=[ConfigIndex.ORDINARY_MAPS],
            ),
            TabSpec(
                title="Map groups",
                items=[ConfigIndex.ORDINARY_MAPGROUPS],
            ),
        ]

    def config_item_changed(self, config_item, config: Config[IndexT]) -> list[IndexT]:
        if config_item is config[ConfigIndex.ORDINARY_MAPGROUPS]:
            self._refresh_map_group_choices(config)
            # Covers the case where the removed/renamed group was the
            # selected one: _refresh_map_group_choices() just fell
            # SELECTED_MAP_GROUP back to "ALL", so SELECTED_MAP needs
            # to be re-enabled to match.
            self._sync_selected_map_state(config)
            return [ConfigIndex.SELECTED_MAP_GROUP, ConfigIndex.SELECTED_MAP]
        if config_item is config[ConfigIndex.SELECTED_MAP_GROUP]:
            self._sync_selected_map_state(config)
            return [ConfigIndex.SELECTED_MAP]
        return []

    def error_report_files(self) -> list[str]:
        # MapList.txt/Startup.txt/ModList.txt (plus any user-maintained
        # *_append.txt siblings, and anything else dropped in here) --
        # useful for seeing exactly what was actually written to disk.
        admin_dir = self.server_root / "Admin"
        if not admin_dir.is_dir():
            return []
        return [
            str(path.relative_to(self.directory))
            for path in admin_dir.glob("*.txt")
            if path.is_file()
        ]
