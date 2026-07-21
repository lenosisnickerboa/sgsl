import re
import shlex
import shutil
import winreg
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
from config.config_item import ConfigDeliveryType, ConfigItem, ConfigType
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from game.cs2.config_defaults import build_game_defaults
from game.cs2.config_index import ConfigIndex
from game.cs2.config_parser.valve_config_parser import ValveConfigParser
from game.cs2.config_parser.valve_gamemode_config_parser import (
    ConfigEntry,
    ValveGamemodeConfigParser,
)
from game.game import Game, OperationResult, TerminalLineResult
from support import bat_runner
from support.dialog import edit_string_dialog_box
from support.unzip import unzip_with_return
from support.wget import download_with_return
from thread.run_task import TaskRunner

GameExe = "cs2.exe"

# All relative to server root directory
GameExeWithPath = Path("game") / "bin" / "win64" / GameExe


class CS2Game(Game):
    def __init__(self, directory: Union[str, Path], terminal):
        super().__init__(directory, terminal)
        self.server_binary = self.server_root / GameExeWithPath
        # Only set once config_loaded() runs, i.e. once the game is
        # already installed and its config exists — still None during
        # the initial install (config_defaults()/config_loaded() never
        # ran yet), when install-time troubleshooting toggles simply
        # aren't available to the user.
        self.config: Optional[Config[IndexT]] = None

    def detect(self) -> bool:
        return self.server_binary.exists()

    def get_short_name(self) -> str:
        return "cs2"

    def get_long_name(self) -> str:
        return "Counter-Strike 2"

    # steamcmd, on a freshly-unzipped install, typically spends its
    # first invocation only self-updating: it downloads its own
    # bootstrapper, relaunches itself, and the +app_update job that
    # was requested on the original command line never actually runs
    # (fails immediately with e.g. "state is 0x202"). The fix used
    # throughout the community is simply to run the same steamcmd
    # command again -- so we retry update_install.bat, without
    # re-downloading/re-extracting steamcmd, until the server binary
    # actually shows up.
    #
    # A separate, non-retryable cause of the same opaque "state is
    # 0x202" stdout error is insufficient disk space: steamcmd only
    # logs the real reason ("Failed to preallocate (Not enough disk
    # space)") to steamcmd/logs/content_log.txt, never to stdout, so
    # we check that log after a failed attempt and fail fast with a
    # readable message instead of burning through retries that can't
    # possibly succeed.
    InstallAttempts = 3

    _DiskSpaceLogPattern = re.compile(
        r'Failed to preallocate \(Not enough disk space\) "([^"]+)"'
    )

    # A SteamCMD-only install doesn't ship these Steamworks
    # redistributable DLLs, so the dedicated server fails at startup
    # with "Failed to initialize Steamworks SDK for gameserver. Could
    # not determine Steam client install directory." Copying them
    # from a local Steam client install fixes it.
    _SteamworksDllNames = ["steamclient64.dll", "tier0_s64.dll", "vstdlib_s64.dll"]

    def _locate_steam_install_dir(self) -> Optional[Path]:
        """Find a local Steam client install via the registry."""
        candidates = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Valve\Steam",
                "InstallPath",
            ),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]
        for hive, subkey, value_name in candidates:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    path_str, _ = winreg.QueryValueEx(key, value_name)
            except OSError:
                continue
            path = Path(path_str)
            if path.exists():
                return path
        return None

    def _find_steamworks_dll(self, steam_dir: Path, dll_name: str) -> Optional[Path]:
        candidates = [
            steam_dir / dll_name,
            steam_dir / "bin64" / dll_name,
            steam_dir / "steamapps" / "common" / "Steamworks Shared" / dll_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        # Last resort: a shallow recursive search, Steam installs
        # aren't so deep that this is expensive.
        matches = list(steam_dir.glob(f"**/{dll_name}"))
        return matches[0] if matches else None

    def _copy_steamworks_dlls(self) -> None:
        """Best-effort: locate a local Steam client install and copy
        the Steamworks redistributable DLLs into game/bin/win64, next
        to cs2.exe. Missing DLLs/Steam install are logged, not fatal —
        the server may already have them from a previous copy."""
        steam_dir = self._locate_steam_install_dir()
        if steam_dir is None:
            self.print(
                "Could not find a local Steam client install to copy Steamworks DLLs "
                f"({', '.join(self._SteamworksDllNames)}) from; if the server fails to start "
                'with "Failed to initialize Steamworks SDK for gameserver", install Steam on '
                "this machine and update/install the server again."
            )
            return

        dest_dir = self.server_root / "game" / "bin" / "win64"
        dest_dir.mkdir(parents=True, exist_ok=True)

        for dll_name in self._SteamworksDllNames:
            source = self._find_steamworks_dll(steam_dir, dll_name)
            if source is None:
                self.print(f"Could not find {dll_name} under {steam_dir}; skipping")
                continue
            shutil.copy2(source, dest_dir / dll_name)
            self.print(f"Copied {dll_name} from {source} to {dest_dir}")

    def _disk_space_failure_reason(self, steamcmd_dir: Path) -> Optional[str]:
        content_log = steamcmd_dir / "logs" / "content_log.txt"
        try:
            log_text = content_log.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        matches = self._DiskSpaceLogPattern.findall(log_text)
        if not matches:
            return None

        required = matches[-1]
        free_gb = shutil.disk_usage(self.server_root).free / (1024**3)
        return (
            f"Not enough disk space to install {self.get_long_name()}: needs {required} free, "
            f"but only {free_gb:.2f} GB free on {self.server_root.drive or self.server_root.anchor}"
        )

    def _is_workshop_map(self, map: str) -> bool:
        return map.startswith("workshop\\")

    def _get_workshop_id(self, map: str) -> int:
        match = re.search(r"workshop\\(\d+)\\", map)
        if match:
            return int(match.group(1))
        else:
            return -1

    def _install_or_update(
        self, result_callback: Callable[[OperationResult], None]
    ) -> None:
        steamcmd_dir = self.directory / "steamcmd"
        steamcmd_zip = steamcmd_dir / "steamcmd.zip"

        steamcmd_dir.mkdir(parents=True, exist_ok=True)

        if (
            self.config is not None
            and self.config[ConfigIndex.REMOVE_MANIFEST_FILE].value
        ):
            manifest_file = self.server_root / "steamapps" / "appmanifest_730.acf"
            if manifest_file.exists():
                manifest_file.unlink()
                self.print(f"Removed stale Steam app manifest {manifest_file}")

        def on_output(l):
            self.print(l)

        def run_update_install(attempt: int):
            def on_result(exit_code):
                if self.server_binary.exists():
                    self._copy_steamworks_dlls()
                    result_callback(OperationResult.OK)
                    return

                disk_space_reason = self._disk_space_failure_reason(steamcmd_dir)
                if disk_space_reason:
                    self.print(disk_space_reason)
                    result_callback(OperationResult.FAIL)
                    return

                if attempt < self.InstallAttempts:
                    self.print(
                        f"steamcmd exited ({exit_code}) without installing {self.get_long_name()} "
                        f"(likely just a steamcmd self-update run); retrying, attempt {attempt + 1}/{self.InstallAttempts}..."
                    )
                    run_update_install(attempt + 1)
                else:
                    self.print(
                        f"Failed to install {self.get_long_name()} after {self.InstallAttempts} attempts"
                    )
                    result_callback(OperationResult.FAIL)

            bat_runner.run(
                [f"cd {steamcmd_dir}", "update_install.bat"],
                self.directory,
                on_output,
                on_result,
            )

        def on_setup_result(exit_code):
            run_update_install(1)

        update_install_bat_line = f"echo steamcmd +force_install_dir {self.server_root} +login anonymous +app_update 730 validate +quit > update_install.bat"
        update_steamcmd = (
            self.config is None or self.config[ConfigIndex.UPDATE_STEAMCMD].value
        )
        if update_steamcmd:
            # Pinned to the Windows-native executables via their full
            # paths: PATH commonly also resolves to Git for Windows'
            # curl/tar (e.g. C:\Program Files\Git\usr\bin\tar.exe),
            # whose GNU tar misreads a bare drive-letter path like
            # "C:\..." as a host:path remote-tape spec ("Cannot
            # connect to C:").
            bat_runner.run(
                [
                    f"curl.exe https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -o {steamcmd_zip}",
                    f"tar.exe -xf {steamcmd_zip} -C {steamcmd_dir}",
                    f"cd {steamcmd_dir}",
                    update_install_bat_line,
                ],
                self.directory,
                on_output,
                on_setup_result,
            )
        else:
            self.print(
                "Skipping steamcmd download/update because Update steamcmd is disabled"
            )
            bat_runner.run(
                [f"cd {steamcmd_dir}", update_install_bat_line],
                self.directory,
                on_output,
                on_setup_result,
            )

    def install(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Installing {self.get_long_name()} into {self.server_root}")
        self._install_or_update(result_callback)

    def update(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")
        self._install_or_update(result_callback)

    def _filter_stdout(self, line: str) -> str:
        if (
            "CTextConsoleWin::GetLine: !GetNumberOfConsoleInputEvents" in line
        ):  # harmless and uninteresting
            return None
        if " UNEXPECTED LONG FRAME DETECTED:" in line:  # harmless and uninteresting
            return None
        if " Sending S2C_CONNECTION to " in line:  # harmless and uninteresting
            return None
        if " Long frame " in line:  # harmless and uninteresting
            return None
        return line

    def run(self, config: Config[IndexT]) -> bool:
        args = [
            "-dedicated",
            "+game_type",
            "TYPE",
            "+game_mode",
            "MODE",
            "-maxplayers",
            "<number>",
        ]
        game_mode = config[ConfigIndex.GAME_MODE].value
        if game_mode == "Casual":
            args[2] = "0"  # game_type
            args[4] = "0"  # gamne_mode
        elif game_mode == "Competitive":
            args[2] = "0"  # game_type
            args[4] = "1"  # gamne_mode
        elif game_mode == "ArmsRace":
            args[2] = "1"  # game_type
            args[4] = "0"  # gamne_mode
        elif game_mode == "DeathMatch":
            args[2] = "1"  # game_type
            args[4] = "2"  # gamne_mode
        elif game_mode == "Demolition":
            args[2] = "1"  # game_type
            args[4] = "1"  # gamne_mode
        else:
            exit(1)
        args[6] = str(config[ConfigIndex.PLAYER_COUNT].value)
        if config[ConfigIndex.STEAM_GSLT].value:  # possibly required when hosting?
            args.append("+sv_setsteamaccount")
            args.append(config[ConfigIndex.STEAM_GSLT].value)
        if self._is_workshop_map(config[ConfigIndex.SELECTED_MAP].value):
            args.append(
                "+map"  # dummy map seems to be needed when hosting a workshop map
            )
            args.append("de_dust2")
            if config[ConfigIndex.STEAM_API_AUTH_KEY].value:  # required when hosting
                args.append("-authkey")
                args.append(config[ConfigIndex.STEAM_API_AUTH_KEY].value)
            args.append("+host_workshop_map")
            id = self._get_workshop_id(config[ConfigIndex.SELECTED_MAP].value)
            args.append(str(id))
        else:
            args.append("+map")
            args.append(config[ConfigIndex.SELECTED_MAP].value)
        # TODO: add "-usercon",
        self._update_gamemode_cfg(config)
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
        super().start_server(args, self._filter_stdout)
        return True

    def _gamemode_cfg_path(self, config: Config[IndexT]) -> Path:
        cfg_dir = self.server_root / "game" / "csgo" / "cfg"
        gamemode = config[ConfigIndex.GAME_MODE].value.lower()
        return cfg_dir / f"gamemode_{gamemode}.cfg"

    # Marks a line as sgsl's own, so a later run can find and drop it
    # again before appending a fresh copy -- see _update_gamemode_cfg().
    _AddedByComment = "added by sgsl.exe"

    def _update_gamemode_cfg(self, config: Config[IndexT]) -> None:
        """Strip any cvar lines sgsl previously appended to this game
        mode's Valve-provided override cfg, then append the current
        config's SERVER_CFG_FILE items back on, each tagged with when
        it was written -- so repeated runs update in place instead of
        piling up duplicates, while everything else in the file (the
        game's own defaults, comments, formatting) is left alone."""
        path = self._gamemode_cfg_path(config)
        entries = ValveGamemodeConfigParser.read(path)
        entries = [
            entry
            for entry in entries
            if not (
                isinstance(entry, ConfigEntry) and self._AddedByComment in entry.comment
            )
        ]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entries.extend(
            ConfigEntry(
                name=item.name,
                value=self._cvar_value(item),
                comment=f"{self._AddedByComment} {timestamp}",
            )
            for item in config.values()
            if item.config_type is ConfigDeliveryType.SERVER_CFG_FILE
        )

        ValveGamemodeConfigParser.write(path, entries)

    def _cvar_value(self, item: ConfigItem) -> str:
        if item.name == "bot_difficulty":
            # Stored/edited as a friendly label (see config_defaults.py's
            # allowed_values), but the game cvar takes its list position
            # as an integer.
            return str(item.allowed_values.index(item.value))
        if item.type is ConfigType.BOOLEAN:
            return "1" if item.value else "0"
        return str(item.value)

    def stop(self) -> bool:
        return super().stop_server()

    def is_running(self) -> bool:
        return super().is_server_running()

    def interpret_terminal_line(self, line: str) -> TerminalLineResult:
        return TerminalLineResult.OK

    def get_server_binary_path(self) -> Path:
        return self.server_binary

    def _ordinary_maps(self) -> list[str]:
        maps_dir = Path(self.server_root) / "game" / "csgo" / "maps"
        return [p.stem for p in maps_dir.glob("*.vpk")] + [
            p.stem for p in maps_dir.glob("*.bsp")
        ]

    # A map's .vpk/.bsp can be split into numbered parts sharing its
    # workshop id, e.g. "<id>_000.vpk", "<id>_001.vpk" — strip that
    # suffix to recover the id all parts share.
    _WorkshopMapFilePattern = re.compile(r"^(\d+)(?:_\d+)?$")

    # Some old workshop maps are instead stored as a single
    # "<id>_legacy.bin" with no publish_data.txt alongside it, so
    # there's no title to read — synthesize one from the id. The id
    # in the filename itself isn't reliable; the containing directory
    # is named after the actual workshop id, so use that instead.

    def _workshop_maps(self) -> list[str]:
        maps_dir = (
            Path(self.server_root)
            / "game"
            / "bin"
            / "win64"
            / "steamapps"
            / "workshop"
            / "content"
            / "730"
        )
        maps = []
        seen_ids = set()
        map_files = list(maps_dir.glob("**/*.vpk")) + list(maps_dir.glob("**/*.bsp"))
        for map_file in map_files:
            match = self._WorkshopMapFilePattern.match(map_file.stem)
            if match is None:
                continue
            map_id = match.group(1)
            if map_id in seen_ids:
                continue
            seen_ids.add(map_id)
            publish_data_file = maps_dir / map_id / "publish_data.txt"
            if not publish_data_file.exists():
                continue
            try:
                publish_data = ValveConfigParser.read(publish_data_file)
            except (OSError, ValueError):
                continue
            title = publish_data.get("publish_data", {}).get("title")
            if title:
                maps.append(f"workshop\\{map_id}\\{title}")

        for legacy_file in maps_dir.glob("**/*_legacy.bin"):
            map_id = legacy_file.parent.name
            if map_id in seen_ids:
                continue
            seen_ids.add(map_id)
            maps.append(f"workshop\\{map_id}\\legacy_{map_id}")

        return maps

    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        maps = self._ordinary_maps()
        defaults[ConfigIndex.ORDINARY_MAPS].value = maps
        # A separate list, not the same object as ORDINARY_MAPS.value —
        # SELECTED_MAP.allowed_values gets extended in place elsewhere
        # (config_loaded()), which would otherwise silently mutate
        # ORDINARY_MAPS.value too since lists are shared by reference.
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = list(maps)
        defaults[ConfigIndex.SELECTED_MAP].value = maps[0] if len(maps) else ""
        defaults[ConfigIndex.WORKSHOP_MAPS].value = self._workshop_maps()
        return defaults

    def _get_workshop_ids(self, maps: list[str]) -> list[int]:
        installed_ids = []
        for wm in maps:
            if not self._is_workshop_map(wm):
                continue
            installed_ids.append(self._get_workshop_id(wm))
        return installed_ids

    def config_loaded(self, config: Config[IndexT]) -> None:
        self.config = config
        installed_ws_maps = self._workshop_maps()
        installed_ws_maps_ids = self._get_workshop_ids(installed_ws_maps)
        not_installed_ws_maps = []
        for map in config[ConfigIndex.WORKSHOP_MAPS].value:
            if not self._is_workshop_map(map):
                continue
            id = self._get_workshop_id(map)
            if not id in installed_ws_maps_ids:
                not_installed_ws_maps.append(map)
        config[ConfigIndex.WORKSHOP_MAPS].value = (
            installed_ws_maps + not_installed_ws_maps
        )
        config[ConfigIndex.SELECTED_MAP].allowed_values += (
            installed_ws_maps + not_installed_ws_maps
        )

    def config_shortcuts(self) -> list[IndexT]:
        return [
            ConfigIndex.GAME_MODE,
            ConfigIndex.SELECTED_MAP_GROUP,
            ConfigIndex.SELECTED_MAP,
            ConfigIndex.PLAYER_COUNT,
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
                    ConfigIndex.RUN_COMMAND_EDIT,
                    ConfigIndex.CUSTOM_RUN_COMMAND_PRE,
                    ConfigIndex.CUSTOM_RUN_COMMAND_POST,
                ],
            ),
            TabSpec(
                title="Steam",
                items=[
                    ConfigIndex.STEAM_GSLT,
                    ConfigIndex.STEAM_API_AUTH_KEY,
                ],
            ),
            TabSpec(
                title="Network",
                items=[
                    ConfigIndex.HOSTNAME,
                    ConfigIndex.SV_LAN,
                    ConfigIndex.SV_PASSWORD,
                ],
            ),
            TabSpec(
                title="Bots",
                items=[
                    ConfigIndex.BOT_DIFFICULTY,
                    ConfigIndex.BOT_QUOTA,
                    ConfigIndex.BOT_QUOTA_MODE,
                    ConfigIndex.BOT_CHATTER,
                    ConfigIndex.BOT_WALK,
                    ConfigIndex.BOT_JOIN_AFTER_PLAYER,
                    ConfigIndex.BOT_ALL_WEAPONS,
                ],
            ),
            TabSpec(
                title="Match Rules",
                items=[
                    ConfigIndex.MP_ROUNDTIME,
                    ConfigIndex.MP_FREEZETIME,
                    ConfigIndex.MP_BUYTIME,
                    ConfigIndex.MP_MAXROUNDS,
                    ConfigIndex.MP_HALFTIME,
                    ConfigIndex.MP_OVERTIME_ENABLE,
                    ConfigIndex.MP_OVERTIME_MAXROUNDS,
                    ConfigIndex.MP_STARTMONEY,
                    ConfigIndex.MP_MAXMONEY,
                    ConfigIndex.MP_FRIENDLYFIRE,
                    ConfigIndex.MP_AUTOTEAMBALANCE,
                    ConfigIndex.MP_LIMITTEAMS,
                    ConfigIndex.MP_WARMUPTIME,
                    ConfigIndex.MP_WARMUP_PAUSETIMER,
                    ConfigIndex.MP_RESPAWN_ON_DEATH_CT,
                    ConfigIndex.MP_RESPAWN_ON_DEATH_T,
                ],
            ),
            TabSpec(
                title="Economy",
                items=[
                    ConfigIndex.MP_FREE_ARMOR,
                    ConfigIndex.MP_AFTERROUNDMONEY,
                    ConfigIndex.MP_DEATH_DROP_GUN,
                    ConfigIndex.MP_DEATH_DROP_GRENADE,
                ],
            ),
            TabSpec(
                title="Voice",
                items=[
                    ConfigIndex.SV_VOICEENABLE,
                    ConfigIndex.SV_ALLTALK,
                    ConfigIndex.SV_DEADTALK,
                ],
            ),
            TabSpec(
                title="Security",
                items=[
                    ConfigIndex.SV_CHEATS,
                ],
            ),
            TabSpec(
                title="Maps",
                items=[ConfigIndex.ORDINARY_MAPS, ConfigIndex.WORKSHOP_MAPS],
            ),
            TabSpec(
                title="Troubleshooting",
                items=[
                    ConfigIndex.REMOVE_MANIFEST_FILE,
                    ConfigIndex.UPDATE_STEAMCMD,
                ],
            ),
        ]

    def config_item_changed(self, config_item, config: Config[IndexT]) -> list[IndexT]:
        if config_item is config[ConfigIndex.WORKSHOP_MAPS]:
            # Keep the selected-map dropdown's choices in sync with
            # the editable map list; if the currently selected map was
            # removed, fall back to the first of what's left.
            maps = list(config[ConfigIndex.ORDINARY_MAPS].value) + list(
                config_item.value
            )
            config[ConfigIndex.SELECTED_MAP].allowed_values = maps
            if maps and config[ConfigIndex.SELECTED_MAP].value not in maps:
                config[ConfigIndex.SELECTED_MAP].set(maps[0])
            return [ConfigIndex.SELECTED_MAP]
        elif config_item is config[ConfigIndex.PLAYER_COUNT]:
            config[ConfigIndex.SV_VISIBLEMAXPLAYERS].set(
                config[ConfigIndex.PLAYER_COUNT].value
            )
        elif config_item is config[ConfigIndex.MP_WARMUPTIME]:
            if config[ConfigIndex.MP_WARMUPTIME].value == 0:
                config[ConfigIndex.MP_WARMUP_PAUSETIMER].set(False)
                config[ConfigIndex.MP_DO_WARMUP_OFFLINE].set(False)
        return []
