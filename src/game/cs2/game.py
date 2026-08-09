import getpass
import re
import shutil
import socket
import winreg
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
from config.config_item import ConfigDeliveryType, ConfigItem, ConfigType
from config.config_upgrader import ConfigItemUpgrade, ConfigUpgrader
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from game.cs2.config_defaults import GameModeCanonicalAlias, build_game_defaults
from game.cs2.config_index import ConfigIndex
from game.cs2.config_parser.valve_config_parser import ValveConfigParser
from game.cs2.config_parser.valve_gamemode_config_parser import (
    ConfigEntry,
    ValveGamemodeConfigParser,
)
from game.game import ExtraResetOption, Game, OperationResult, TerminalLineResult
from support import bat_runner
from support import command_log
from support.dialog import cancelable_progress_dialog, edit_string_dialog_box, ok_dialog
from support.rcon_client import run_rcon_command
from support.run_command import split_run_command
from support.steam_app_update_check import check_for_steam_app_update
from support.unzip import unzip_with_return
from support.wget import download_with_return
from thread.run_task import TaskRunner

GameExe = "cs2.exe"

# All relative to server root directory
GameExeWithPath = Path("game") / "bin" / "win64" / GameExe

AppId = 730

# Preferred default map -- most servers ship it, and it's a familiar
# choice for a first-time setup. Falls back to the first detected map
# (see config_defaults()) if it isn't installed.
_DefaultMap = "de_dust2"

# sgsl's own curated shortlist of the 20 most commonly used CS2/
# Source-engine dedicated server admin console commands (no
# authoritative usage-frequency source exists) -- covering match
# control, player admin, and core server settings. Shared with csgo
# (see CSGOGame.rcon_quick_commands()), since both speak the same
# Source engine console. See RconWindow's own docstring for how these
# are used (one-click-insert buttons, not sent immediately).
RconQuickCommands = [
    "status",
    "changelevel",
    "map",
    "mp_restartgame",
    "mp_warmup_start",
    "mp_warmup_end",
    "mp_pause_match",
    "mp_unpause_match",
    "kick",
    "kickid",
    "banid",
    "removeid",
    "sv_cheats",
    "sv_password",
    "rcon_password",
    "say",
    "bot_kick",
    "bot_add",
    "sv_gravity",
    "mp_maxrounds",
]


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
        # Tracks WORKSHOP_MAPS' own value so config_item_changed() can
        # tell which entry (if any) was just added and only pre-download
        # that one -- see _predownload_workshop_map().
        self._known_workshop_maps: set[str] = set()

    def detect(self) -> bool:
        return self.server_binary.exists()

    def get_short_name(self) -> str:
        return "cs2"

    def get_long_name(self) -> str:
        return "Counter-Strike 2"

    def get_developer_url(self) -> str:
        return "https://store.steampowered.com/app/730/CounterStrike_2/"

    # Both observed accompanying a broken/crashed server that's still
    # technically running (an unrecoverable bad map, or an engine-level
    # assertion) -- see Game.suspicious_terminal_line_patterns().
    _SuspiciousTerminalLinePatterns = ["Error map!", ": Assertion Failed in "]

    def suspicious_terminal_line_patterns(self) -> list[str]:
        return self._SuspiciousTerminalLinePatterns

    def supports_rcon(self) -> bool:
        return True

    def rcon_enabled(self, config: Config[IndexT]) -> bool:
        return config[ConfigIndex.RCON_ENABLE].value

    def rcon_password_configured(self, config: Config[IndexT]) -> bool:
        return bool(config[ConfigIndex.RCON_PASSWORD].value)

    def rcon_quick_commands(self) -> list[str]:
        return RconQuickCommands

    def send_rcon_command(self, command: str, config: Config[IndexT]) -> str:
        # RCON has no port of its own on Source engine servers -- it
        # authenticates over the game's own listen port (see run()'s
        # cvar_overrides comment for the same point re: sv_lan).
        return run_rcon_command(
            command,
            enabled=config[ConfigIndex.RCON_ENABLE].value,
            host=config[ConfigIndex.LISTEN_ADDRESS].value,
            port=config[ConfigIndex.LISTEN_PORT].value,
            password=config[ConfigIndex.RCON_PASSWORD].value,
        )

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
            dest = dest_dir / dll_name
            command_log.run(
                self.print,
                f'copy "{source}" "{dest}"',
                lambda: shutil.copy2(source, dest),
            )

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
        return map.startswith("workshop/")

    def _get_workshop_id(self, map: str) -> int:
        match = re.search(r"workshop/(\d+)/", map)
        if match:
            return int(match.group(1))
        else:
            return -1

    def _get_workshop_name(self, map: str) -> Optional[str]:
        """The name half of a "workshop/<id>/<name>" entry (see
        _normalize_workshop_map()) -- the map's title as reported by
        the Steam Web API when the entry was added, or "unknown" if
        that lookup failed at the time."""
        match = re.search(r"workshop/\d+/(.+)$", map)
        return match.group(1) if match else None

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
            manifest_file = self._appmanifest_path()
            if manifest_file.exists():
                command_log.run(
                    self.print, f'del "{manifest_file}"', manifest_file.unlink
                )

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

        update_install_bat_line = f"echo steamcmd +force_install_dir {self.server_root} +login anonymous +app_update {AppId} validate +quit > update_install.bat"
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

    def _appmanifest_path(self) -> Path:
        return self.server_root / "steamapps" / f"appmanifest_{AppId}.acf"

    def check_for_server_update(self) -> Optional[bool]:
        return check_for_steam_app_update(
            AppId, self._appmanifest_path(), printer=self.print
        )

    def supports_game_update_check(self) -> bool:
        return True

    def automatic_update_check_enabled(self, config: Config[IndexT]) -> bool:
        return config[ConfigIndex.AUTOMATIC_GAME_UPDATE_CHECK].value

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
            "+game_alias",
            "ALIAS",
            "-maxplayers",
            "<number>",
        ]
        game_mode = config[ConfigIndex.GAME_MODE].value
        args[2] = GameModeCanonicalAlias[game_mode]
        args[4] = str(config[ConfigIndex.PLAYER_COUNT].value)
        if config[ConfigIndex.CONSOLE_ENABLED].value:
            args.append("-console")
        if config[ConfigIndex.RCON_ENABLE].value:
            # -usercon lets a client "connect" to RCON via the in-game
            # console rather than a raw socket -- no reason to enable
            # it while RCON itself is off.
            args.append("-usercon")
        # A LAN-only server logs in anonymously instead -- see
        # cvar_overrides below, which always forces the actual sv_lan
        # cvar to 0 regardless of this toggle.
        if (
            not config[ConfigIndex.SV_LAN].value
            and config[ConfigIndex.STEAM_GSLT].value
        ):
            args.append("+sv_setsteamaccount")
            args.append(config[ConfigIndex.STEAM_GSLT].value)
        if config[ConfigIndex.STEAM_API_AUTH_KEY].value:
            args.append("-authkey")
            args.append(config[ConfigIndex.STEAM_API_AUTH_KEY].value)
        args.append("-ip")
        args.append(config[ConfigIndex.LISTEN_ADDRESS].value)
        args.append("-port")
        args.append(str(config[ConfigIndex.LISTEN_PORT].value))
        args.append("-tickrate")
        args.append(config[ConfigIndex.SERVER_FREQUENCY].value)

        # RCON has no port of its own on Source engine servers — it
        # authenticates over the game's own port via rcon_password
        # (a SERVER_CFG_FILE item, so it's written by
        # _write_sgsl_overrides_cfg() like any other cvar) — forced to
        # empty here when disabled, which is how Source servers turn
        # RCON off, regardless of whatever password is configured.
        cvar_overrides = (
            {} if config[ConfigIndex.RCON_ENABLE].value else {"rcon_password": ""}
        )
        # Always written as 0 -- Source's own "sv_lan 1" local mode is
        # never actually enabled. SV_LAN (see above) instead controls
        # whether we log in with a GSLT at all: skipping
        # +sv_setsteamaccount (an anonymous login) is what keeps a
        # "LAN only" server off the public server browser, so the cvar
        # itself doesn't need to (and shouldn't) also flip to 1.
        cvar_overrides["sv_lan"] = "0"

        # A map group only ever supplies which maps to cycle through —
        # CS2 only supports one game mode/round limit per running
        # server, so those still come from Game mode/Max rounds as
        # usual and apply to the whole rotation.
        workshop_collection_id = self._active_workshop_collection(config)
        if workshop_collection_id is not None:
            # A workshop map group is a Steam Workshop collection id,
            # not a locally-defined map list — Steam itself resolves
            # and rotates through the collection's maps, so there's no
            # mapgroups.txt to write here, unlike an ordinary map group.
            self._append_workshop_host_args(
                args, "host_workshop_collection", workshop_collection_id
            )
        else:
            map_group = self._active_map_group(config)
            if map_group:
                selected_map_group = config[ConfigIndex.SELECTED_MAP_GROUP].value
                self._write_map_groups(selected_map_group, map_group)
                args.append("+mapgroup")
                args.append(selected_map_group)
                launch_map = map_group[0]["name"]
                cvar_overrides.update(
                    {
                        # Without these the engine just restarts the same map
                        # at match end instead of advancing through the map
                        # group — see _write_sgsl_overrides_cfg().
                        "mp_match_end_changelevel": "1",
                        "mp_match_end_restart": "0",
                    }
                )
            else:
                launch_map = config[ConfigIndex.SELECTED_MAP].value

            if self._is_workshop_map(launch_map):
                self._append_workshop_host_args(
                    args, "host_workshop_map", self._get_workshop_id(launch_map)
                )
            else:
                args.append("+map")
                args.append(launch_map)
        self._write_sgsl_overrides_cfg(config, cvar_overrides)
        self._write_gamemode_server_cfgs()
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
        super().start_server(args, self._filter_stdout)
        return True

    _MapGroupsFileName = "gamemodes_server.txt"
    # CS2 dropped support for the old CS:GO mapcyclefile mechanism —
    # +mapgroup + a gamemodes_server.txt KeyValues file (see
    # _write_map_groups()) is what actually rotates through an
    # ordinary map group's maps now.
    # A generic placeholder -- sgsl has no per-group icon/display-name
    # data of its own to put here, and neither one affects server
    # behavior (purely cosmetic, used by CS2's own in-game server
    # browser UI).
    _MapGroupImageName = "img-group_active"

    def _map_groups_path(self) -> Path:
        return self.server_root / "game" / "csgo" / self._MapGroupsFileName

    def _write_map_groups(self, group_name: str, group: list[dict]) -> None:
        """Write `group`'s maps as CS2's gamemodes_server.txt KeyValues
        format: a "GameModes_Server.txt" -> "mapgroups" block
        containing one group, named `group_name` (the currently
        selected ORDINARY_MAPGROUPS entry's own key -- see run(),
        which also passes that same name to +mapgroup), with a "maps"
        block listing one entry per map ("1", meaning enabled -- CS2's
        own convention, not really a boolean toggle sgsl has any
        control over). A workshop map is listed by its bare workshop
        id, same as the old mapcyclefile format did, since a
        "workshop/<id>/<name>" entry isn't itself a real map name
        CS2 would recognize here."""
        maps = {
            (
                str(self._get_workshop_id(entry["name"]))
                if self._is_workshop_map(entry["name"])
                else entry["name"]
            ): "1"
            for entry in group
        }
        ValveConfigParser.write(
            self._map_groups_path(),
            {
                "GameModes_Server.txt": {
                    "mapgroups": {
                        group_name: {
                            "imagename": self._MapGroupImageName,
                            "name": group_name,
                            "maps": maps,
                        }
                    }
                }
            },
        )

    def _append_workshop_host_args(
        self,
        args: list[str],
        host_cvar: str,
        workshop_id: int,
    ) -> None:
        # Without this dummy +map, hosting from a workshop map/collection
        # simply doesn't work -- the server starts but never actually
        # loads the workshop content, host_cvar or not. Cause unknown;
        # this is just the workaround observed to fix it.
        args.append("+map")
        args.append("de_dust2")
        args.append(f"+{host_cvar}")
        args.append(str(workshop_id))

    def _active_workshop_collection(self, config: Config[IndexT]) -> Optional[int]:
        """The Steam Workshop collection id if the currently selected
        map group is one of WORKSHOP_MAPGROUPS' entries, or None
        otherwise (an ordinary map group, "ALL", or empty)."""
        selected_map_group = config[ConfigIndex.SELECTED_MAP_GROUP].value
        if not selected_map_group or selected_map_group == "ALL":
            return None
        if selected_map_group not in config[ConfigIndex.WORKSHOP_MAPGROUPS].value:
            return None
        return self._get_workshop_id(selected_map_group)

    def _active_map_group(self, config: Config[IndexT]) -> Optional[list[dict]]:
        """The list of {"name"} entries for the currently selected map
        group, or None if SELECTED_MAP_GROUP is "ALL"/empty/not a real
        group."""
        selected_map_group = config[ConfigIndex.SELECTED_MAP_GROUP].value
        if not selected_map_group or selected_map_group == "ALL":
            return None
        return self._find_map_group(config, selected_map_group)

    def _find_map_group(self, config: Config[IndexT], key: str) -> Optional[list[dict]]:
        """The list of {"name"} entries stored under `key` in
        ORDINARY_MAPGROUPS, or None if no such group exists."""
        for entry in config[ConfigIndex.ORDINARY_MAPGROUPS].value:
            if entry["key"] == key:
                return entry["value"]
        return None

    def _cfg_dir(self) -> Path:
        return self.server_root / "game" / "csgo" / "cfg"

    # A user-maintained file sgsl never writes to itself: if present,
    # its cvars are always folded into sgsl_overrides.cfg last (after
    # sgsl's own config-item cvars), giving users an escape hatch for
    # cvars sgsl has no config item for. Purely optional, and not tied
    # to any particular game mode -- it applies regardless of which
    # one is currently selected.
    def _sgsl_overrides_append_cfg_path(self) -> Path:
        return self._cfg_dir() / "sgsl_overrides_append.cfg"

    def _sgsl_overrides_cfg_path(self) -> Path:
        return self._cfg_dir() / "sgsl_overrides.cfg"

    @staticmethod
    def _cfg_header(timestamp: str) -> list[str]:
        return [
            "// Generated by sgsl.exe -- do not edit, changes will be overwritten",
            f"// Last updated: {timestamp}",
        ]

    @staticmethod
    def _cfg_banner(label: str, timestamp: str) -> list[str]:
        # Printed via echo (not a // comment) so it actually shows up
        # in the server console/log at the moment this file is execed
        # -- makes it obvious sgsl_overrides.cfg really ran, and when.
        return [
            "echo ================================================================",
            f"echo == sgsl_overrides.cfg -- {label}",
            "echo == Generated by sgsl.exe",
            f"echo == Last updated: {timestamp}",
            "echo ================================================================",
        ]

    def _write_sgsl_overrides_cfg(
        self,
        config: Config[IndexT],
        cvar_overrides: Optional[dict[str, str]] = None,
    ) -> None:
        """(Re)write sgsl_overrides.cfg from scratch with the current
        config's SERVER_CFG_FILE items, plus any sgsl_overrides_append.cfg
        cvars folded in last -- entirely replacing whatever was written
        there before, rather than merging with it, since sgsl owns this
        file outright. Every gamemode_<mode>_server.cfg execs this same
        file (see _write_gamemode_server_cfgs()), so it applies
        regardless of which gamemode ends up running.

        If USE_SGSL_OVERRIDES is off, the file is written with just the
        header and a note that overrides are disabled -- gamemode
        behavior is then left entirely up to the game's own cfg files.

        `cvar_overrides`, if given, replaces (or adds, for cvars with
        no matching config item, e.g. mp_match_end_changelevel) specific
        cvar values on top of the usual SERVER_CFG_FILE items — used
        when a map group is active, since its rotation cvars need to
        win over an item's own separately-configured value."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entries: list[Union[ConfigEntry, str]] = self._cfg_header(
            timestamp
        ) + self._cfg_banner("START", timestamp)

        if not config[ConfigIndex.USE_SGSL_OVERRIDES].value:
            entries.append("// sgsl overrides disabled")
            entries += self._cfg_banner("END", timestamp)
            ValveGamemodeConfigParser.write(self._sgsl_overrides_cfg_path(), entries)
            return

        cvar_overrides = cvar_overrides or {}
        written_names = set()
        for item in config.values():
            if item.config_type is not ConfigDeliveryType.SERVER_CFG_FILE:
                continue
            value = cvar_overrides.get(item.name, self._cvar_value(item))
            entries.append(ConfigEntry(name=item.name, value=value))
            written_names.add(item.name)
            if item is config[ConfigIndex.MP_WARMUP_TIME] and item.value == 0:
                # mp_warmuptime 0 doesn't actually skip warmup the way
                # sgsl's own UI implies -- _cvar_value() writes a small
                # positive value instead (see there), and this extra
                # bare command ends it immediately, right as the match
                # starts, achieving the same effect.
                entries.append("mp_warmup_end")
        # Overrides with no matching SERVER_CFG_FILE item (e.g.
        # mp_match_end_changelevel/mp_match_end_restart) still need to
        # be written -- the loop above only covers ones that do.
        for name, value in cvar_overrides.items():
            if name in written_names:
                continue
            entries.append(ConfigEntry(name=name, value=value))

        append_path = self._sgsl_overrides_append_cfg_path()
        if append_path.exists():
            append_entries = ValveGamemodeConfigParser.read(append_path)
            entries.extend(
                entry for entry in append_entries if isinstance(entry, ConfigEntry)
            )

        entries += self._cfg_banner("END", timestamp)
        ValveGamemodeConfigParser.write(self._sgsl_overrides_cfg_path(), entries)

    def _write_gamemode_server_cfgs(self) -> None:
        """For every Valve-provided gamemode_<mode>.cfg in the cfg
        directory, (re)write a sibling gamemode_<mode>_server.cfg whose
        only job is to exec sgsl_overrides.cfg -- CS2 automatically
        execs a gamemode's own _server.cfg right after loading its
        gamemode_<mode>.cfg, so this is what actually applies sgsl's
        overrides, regardless of which mode ends up running."""
        cfg_dir = self._cfg_dir()
        if not cfg_dir.is_dir():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for path in cfg_dir.glob("gamemode_*.cfg"):
            if not path.is_file():
                continue
            if path.name.endswith("_append.cfg") or path.name.endswith("_server.cfg"):
                continue
            server_path = path.with_name(f"{path.stem}_server.cfg")
            entries = self._cfg_header(timestamp) + ["exec sgsl_overrides.cfg"]
            ValveGamemodeConfigParser.write(server_path, entries)

    def _cvar_value(self, item: ConfigItem) -> str:
        if item.name == "bot_difficulty":
            # Stored/edited as a friendly label (see config_defaults.py's
            # allowed_values), but the game cvar takes its list position
            # as an integer.
            return str(item.allowed_values.index(item.value))
        if item.name == "mp_warmuptime" and item.value == 0:
            # 0 doesn't mean "no warmup" to the engine the way it does
            # in sgsl's own UI (tooltip aside) -- write the smallest
            # positive value instead and let the extra mp_warmup_end
            # command _write_sgsl_overrides_cfg() appends right after
            # this one end it immediately instead.
            return "1"
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

    def _unique_preserving_order(self, values: list[str]) -> list[str]:
        """`values` with duplicates removed, keeping each entry's
        first occurrence and the original order -- SELECTED_MAP's
        allowed_values is assembled from several overlapping sources
        (ORDINARY_MAPS, WORKSHOP_MAPS, freshly-loaded not-yet-installed
        workshop maps, ...) that can end up naming the same map more
        than once."""
        return list(dict.fromkeys(values))

    def _ordinary_maps(self) -> list[str]:
        maps_dir = self._ordinary_maps_dir()
        names = [p.stem for p in maps_dir.glob("*.vpk")] + [
            p.stem for p in maps_dir.glob("*.bsp")
        ]
        names += self._downloaded_workshop_maps()
        return names

    def _downloaded_workshop_maps(self) -> list[str]:
        maps_dir = self._ordinary_maps_dir() / "workshop"
        entries = []
        for path in list(maps_dir.glob("**/*_dir.vpk")) + list(
            maps_dir.glob("**/*_dir.bsp")
        ):
            workshop_id = path.parent.name
            name = path.stem[: -len("_dir")]
            entries.append(f"workshop/{workshop_id}/{name}")
        return entries

    # A map's .vpk/.bsp can be split into numbered parts sharing its
    # workshop id, e.g. "<id>_000.vpk", "<id>_001.vpk" — strip that
    # suffix to recover the id all parts share.
    _WorkshopMapFilePattern = re.compile(r"^(\d+)(?:_\d+)?$")

    # Some old workshop maps are instead stored as a single
    # "<id>_legacy.bin" with no publish_data.txt alongside it, so
    # there's no title to read — synthesize one from the id. The id
    # in the filename itself isn't reliable; the containing directory
    # is named after the actual workshop id, so use that instead.

    def _workshop_content_dir(self) -> Path:
        return (
            Path(self.server_root)
            / "game"
            / "bin"
            / "win64"
            / "steamapps"
            / "workshop"
            / "content"
            / str(AppId)
        )

    def _workshop_maps(self) -> list[str]:
        maps_dir = self._workshop_content_dir()
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
                maps.append(f"workshop/{map_id}/{title}")

        for legacy_file in maps_dir.glob("**/*_legacy.bin"):
            map_id = legacy_file.parent.name
            if map_id in seen_ids:
                continue
            seen_ids.add(map_id)
            maps.append(f"workshop/{map_id}/legacy_{map_id}")

        return maps

    def _ordinary_maps_dir(self) -> Path:
        return Path(self.server_root) / "game" / "csgo" / "maps"

    def _workshop_predownload_content_dir(self) -> Path:
        # Where "+force_install_dir {server_root} ... +workshop_download_item"
        # actually places downloaded content -- unrelated to
        # _workshop_content_dir() above, which is where CS2's own
        # Steamworks-based auto-download (via +host_workshop_map) puts
        # it instead, nested under the game binary's own Steam library
        # context rather than server_root.
        return self.server_root / "steamapps" / "workshop" / "content" / str(AppId)

    def _workshop_predownload_dir(self, workshop_id: str) -> Path:
        return self._workshop_predownload_content_dir() / workshop_id

    def _workshop_map_cache_dir(self, workshop_id: str) -> Path:
        # maps/workshop/<id>/ -- see _ordinary_maps()'s matching glob.
        return self._ordinary_maps_dir() / "workshop" / workshop_id

    # Characters Windows filenames can't contain, plus control chars.
    _UnsafeFilenameCharsPattern = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

    def _sanitize_map_name(self, name: str) -> str:
        """A Steam Workshop title as reported by the Steam Web API can
        contain arbitrary characters/whitespace -- neither valid in a
        Windows filename nor usable as a Source engine map name (e.g.
        for +map <name>), so collapse whitespace to underscores and
        strip anything else that isn't."""
        sanitized = self._UnsafeFilenameCharsPattern.sub("_", name.strip())
        sanitized = re.sub(r"\s+", "_", sanitized)
        sanitized = sanitized.strip("._")
        return sanitized or "unknown"

    # A .vpk map is often split into a "<name>_dir.vpk" directory file
    # plus numbered "<name>_NNN.vpk" pak chunks, all of which must keep
    # sharing the exact same <name> for the engine to find them as one
    # map -- matched here so renaming preserves whichever suffix (if
    # any) a given file has instead of replacing the whole stem.
    _MapFileSuffixPattern = re.compile(r"^(.*)(_dir|_\d+)$")

    def _map_file_base(self, original: Path) -> str:
        """`original`'s stem with any "_dir"/"_NNN" pak-chunk suffix
        (see _MapFileSuffixPattern) stripped back off -- the name a
        sidecar file (e.g. a .nav mesh) that isn't itself a chunk would
        share with the map, used by _copy_predownloaded_workshop_map()
        to find those and rename them alongside it."""
        match = self._MapFileSuffixPattern.match(original.stem)
        return match.group(1) if match else original.stem

    def _renamed_map_filename(self, original: Path, new_name: str) -> str:
        match = self._MapFileSuffixPattern.match(original.stem)
        suffix = match.group(2) if match else ""
        return f"{new_name}{suffix}{original.suffix}"

    def _copy_predownloaded_workshop_map(self, workshop_id: str, map_name: str) -> None:
        """Copy every file (not just the map itself -- whatever else
        steamcmd downloaded alongside it, e.g. publish_data.txt) for
        `workshop_id` into its own maps/workshop/<workshop_id>/
        subfolder -- Valve's own convention for a workshop map cached
        locally rather than hosted on demand, so the engine finds it
        there without sgsl needing to flatten anything.

        The actual map file(s) (.vpk/.bsp) are renamed to `map_name`
        (sanitized -- see _sanitize_map_name()), the title the Steam
        Web API reported for this WORKSHOP_MAPS entry when it was
        added, rather than whatever filename the uploader originally
        used. Any sidecar file that shares one of those map files' own
        original name (before renaming) -- e.g. a "<mapname>.nav" bot
        navigation mesh sitting next to "<mapname>.bsp" -- is renamed
        right along with it, since the engine only finds it by still
        matching the (now renamed) map file's stem exactly. Anything
        else downloaded alongside them (e.g. publish_data.txt) keeps
        its own name, unreferenced by either."""
        content_dir = self._workshop_predownload_dir(workshop_id)
        source_files = [p for p in content_dir.rglob("*") if p.is_file()]
        if not source_files:
            self.print(
                f"No files found in {content_dir} after downloading workshop "
                f"item {workshop_id} -- it may not be a valid map"
            )
            return
        dest_dir = self._workshop_map_cache_dir(workshop_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        sanitized_name = self._sanitize_map_name(map_name)
        map_file_bases = {
            self._map_file_base(source_file)
            for source_file in source_files
            if source_file.suffix.lower() in (".vpk", ".bsp")
        }
        for source_file in source_files:
            is_map_file = source_file.suffix.lower() in (".vpk", ".bsp")
            is_sidecar = source_file.stem in map_file_bases
            if is_map_file or is_sidecar:
                dest = dest_dir / self._renamed_map_filename(
                    source_file, sanitized_name
                )
            else:
                dest = dest_dir / source_file.relative_to(content_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            command_log.run(
                self.print,
                f'copy "{source_file}" "{dest}"',
                lambda source_file=source_file, dest=dest: shutil.copy2(
                    source_file, dest
                ),
            )
        self.print(f"Installed workshop item {workshop_id} into {dest_dir}")

    def _predownload_workshop_map(self, entry: str, is_update: bool = False) -> bool:
        """Fetch `entry` (a "workshop/<id>/<name>" WORKSHOP_MAPS
        entry) via steamcmd, showing a cancelable "Download map
        <name>..." dialog (or "Updating map <name>...." if `is_update`
        -- see _dedupe_workshop_maps()) for the duration, then copy the
        result into its own maps/workshop/<id>/ subfolder (see
        _copy_predownloaded_workshop_map()) and show a final "Download
        finished" dialog. The download itself runs on a background
        thread (see bat_runner.run()), but this method blocks the
        caller until it finishes or is cancelled.

        Only called when PRE_DOWNLOAD_WORKSHOP_MAPS is enabled (see
        config_item_changed()) -- with it off, a WORKSHOP_MAPS entry
        is still fully usable, just fetched on demand via
        +host_workshop_map the first time it's actually hosted instead
        of right away.

        Returns True if the download actually completed, False if the
        user cancelled it -- in which case nothing was copied, and the
        caller (config_item_changed()) should drop `entry` back out of
        WORKSHOP_MAPS."""
        workshop_id = str(self._get_workshop_id(entry))
        map_name = self._get_workshop_name(entry) or "unknown"
        steamcmd_dir = self.directory / "steamcmd"
        steamcmd_dir.mkdir(parents=True, exist_ok=True)
        self.print(f"Downloading workshop item {workshop_id} via steamcmd...")

        def on_output(line):
            self.print(line)

        def on_result(exit_code):
            if exit_code != 0 and not handle.cancelled:
                self.print(
                    f"steamcmd exited with code {exit_code} while downloading "
                    f"workshop item {workshop_id}"
                )
            # Runs on bat_runner's own background thread -- closing the
            # dialog from here is safe, see CancelableProgressDialog.finish().
            dialog.finish()

        handle = bat_runner.run(
            [
                f"cd {steamcmd_dir}",
                f"steamcmd +force_install_dir {self.server_root} +login anonymous "
                f"+workshop_download_item {AppId} {workshop_id} +quit",
            ],
            self.directory,
            on_output,
            on_result,
        )
        verb = "Updating" if is_update else "Downloading"
        dialog = cancelable_progress_dialog(
            f"{verb} workshop map {map_name}...\nThis may take a while...",
            title=f"{verb} workshop map",
            on_cancel=handle.cancel,
        )
        cancelled = dialog.show()
        if cancelled:
            self.print(f"Download of workshop item {workshop_id} was cancelled")
            return False

        self._copy_predownloaded_workshop_map(workshop_id, map_name)
        ok_dialog("Download finished")
        return True

    def config_defaults(self) -> Config[IndexT]:
        defaults = build_game_defaults()
        maps = self._ordinary_maps()
        defaults[ConfigIndex.ORDINARY_MAPS].value = maps
        workshop_maps = self._workshop_maps()
        defaults[ConfigIndex.WORKSHOP_MAPS].value = workshop_maps
        # A separate list, not the same object as ORDINARY_MAPS.value —
        # SELECTED_MAP.allowed_values gets extended in place elsewhere
        # (config_loaded()), which would otherwise silently mutate
        # ORDINARY_MAPS.value too since lists are shared by reference.
        # Already-installed workshop maps are included here too (not
        # just in config_loaded()) so a saved SELECTED_MAP pointing at
        # one of them still validates when TomlConfigParser.read() loads
        # it further up the call chain, before config_loaded() ever runs
        # -- otherwise it'd be rejected as not in allowed_values yet and
        # silently fall back to the default map.
        defaults[ConfigIndex.SELECTED_MAP].allowed_values = (
            self._unique_preserving_order(list(maps) + workshop_maps)
        )
        if _DefaultMap in maps:
            defaults[ConfigIndex.SELECTED_MAP].value = _DefaultMap
        else:
            defaults[ConfigIndex.SELECTED_MAP].value = maps[0] if len(maps) else ""
        username = getpass.getuser()  # current logged-in user
        hostname = socket.gethostname()  # machine's hostname
        defaults[ConfigIndex.HOSTNAME].value = f"My server {username}@{hostname}"

        for item in defaults.values():
            self._append_default_and_range_to_tooltip(item)

        return defaults

    def config_version(self) -> int:
        # No release has shipped yet, so there's no saved config out
        # there predating GAME_MODE's default change below -- nothing
        # to migrate from yet. Bump to 2 (and uncomment
        # config_upgraders() below) once that change has actually
        # shipped in a release.
        return 1

    def config_upgraders(self) -> list[ConfigUpgrader]:
        # Example upgrader, kept as a reference for the next time a
        # default changes: this is how GAME_MODE's default change from
        # "Casual" to "DeathMatch" would be migrated for anyone who
        # saved a config before that change shipped -- carrying
        # forward anyone still on the old default, while leaving
        # anyone who deliberately chose something else (including
        # "Casual" itself, on purpose) alone. Not live (see
        # config_version() above).
        #
        # old_game_mode = ConfigItem(
        #     name="game_mode",
        #     visible_name="Game mode",
        #     type=ConfigType.STRING_LIST,
        #     value="Casual",
        #     allowed_values=[
        #         "Casual",
        #         "Competitive",
        #         "ArmsRace",
        #         "Demolition",
        #         "DeathMatch",
        #     ],
        # )
        # return [
        #     ConfigUpgrader(
        #         version=2,
        #         upgrades=[
        #             ConfigItemUpgrade(
        #                 index=ConfigIndex.GAME_MODE,
        #                 old=old_game_mode,
        #                 new=build_game_defaults()[ConfigIndex.GAME_MODE],
        #             )
        #         ],
        #         removed_indexes=[],
        #     )
        # ]
        return []

    def extra_reset_options(self) -> list[ExtraResetOption]:
        # None of these three have a fixed "default" the normal reset
        # pass could restore anyway: WORKSHOP_MAPS' own "default" is
        # just whatever's currently downloaded (so a normal reset never
        # empties it), and while ORDINARY_MAPGROUPS/WORKSHOP_MAPGROUPS
        # technically default to [], wiping out a user's hand-built map
        # groups as a side effect of resetting some unrelated setting
        # would be surprising -- so all three are excluded from the
        # normal pass and only touched if explicitly checked here.
        return [
            ExtraResetOption(
                label="Remove downloaded workshop maps",
                tooltip="Delete all downloaded workshop map content and clear the "
                "workshop maps list",
                index=ConfigIndex.WORKSHOP_MAPS,
                action=self._remove_downloaded_workshop_maps,
            ),
            ExtraResetOption(
                label="Remove custom map groups",
                tooltip="Clear all user-defined ordinary map groups",
                index=ConfigIndex.ORDINARY_MAPGROUPS,
                action=self._remove_ordinary_map_groups,
            ),
            ExtraResetOption(
                label="Remove workshop map groups",
                tooltip="Clear all configured Steam Workshop map groups",
                index=ConfigIndex.WORKSHOP_MAPGROUPS,
                action=self._remove_workshop_map_groups,
            ),
        ]

    def _remove_downloaded_workshop_maps(self, config: Config[IndexT]) -> list[IndexT]:
        self._remove_orphaned_workshop_content([])
        config[ConfigIndex.WORKSHOP_MAPS].value = []
        return [ConfigIndex.WORKSHOP_MAPS]

    def _remove_ordinary_map_groups(self, config: Config[IndexT]) -> list[IndexT]:
        config[ConfigIndex.ORDINARY_MAPGROUPS].value = []
        return [ConfigIndex.ORDINARY_MAPGROUPS]

    def _remove_workshop_map_groups(self, config: Config[IndexT]) -> list[IndexT]:
        config[ConfigIndex.WORKSHOP_MAPGROUPS].value = []
        return [ConfigIndex.WORKSHOP_MAPGROUPS]

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
        # Whatever's already saved (or auto-detected as already
        # installed, just above) is assumed already downloaded -- only
        # an entry added later, in this running session, should
        # trigger a fresh pre-download (see config_item_changed()).
        self._known_workshop_maps = set(config[ConfigIndex.WORKSHOP_MAPS].value)
        # installed_ws_maps is already in allowed_values -- config_defaults()
        # put it there so a saved SELECTED_MAP pointing at an already-
        # installed workshop map still validates when TomlConfigParser.read()
        # loads it, before this method ever runs. Only not_installed_ws_maps
        # (freshly loaded from the saved config, unknown at config_defaults()
        # time) is new here.
        config[ConfigIndex.SELECTED_MAP].allowed_values = self._unique_preserving_order(
            config[ConfigIndex.SELECTED_MAP].allowed_values + not_installed_ws_maps
        )
        # Picks up whatever map groups were just loaded from the saved
        # config, since config_defaults() alone only ever sees an
        # empty ORDINARY_MAPGROUPS (the TOML values haven't been
        # merged in yet at that point).
        self._refresh_map_group_choices(config)
        # Likewise for SELECTED_MAP's enabled state, which depends on
        # whatever SELECTED_MAP_GROUP was just loaded.
        self._sync_selected_map_state(config)
        # And for RCON_PASSWORD's enabled state, which depends on
        # whatever RCON_ENABLE was just loaded.
        self._sync_rcon_password_state(config)

    def _sync_rcon_password_state(self, config: Config[IndexT]) -> None:
        """RCON_PASSWORD only takes effect while RCON is enabled (see
        run()'s rcon_password cvar_override) -- disable the field
        rather than leave an edit sitting there with no effect."""
        config[ConfigIndex.RCON_PASSWORD].read_only = not config[
            ConfigIndex.RCON_ENABLE
        ].value

    def _refresh_map_group_choices(self, config: Config[IndexT]) -> None:
        """Keep the selected-map-group dropdown's choices in sync with
        the user-defined map groups (plus the built-in "ALL") and the
        workshop collection map groups; if the currently selected group
        was renamed/removed, fall back to "ALL"."""
        group_keys = [
            entry["key"] for entry in config[ConfigIndex.ORDINARY_MAPGROUPS].value
        ]
        workshop_group_keys = list(config[ConfigIndex.WORKSHOP_MAPGROUPS].value)
        choices = ["ALL"] + group_keys + workshop_group_keys
        config[ConfigIndex.SELECTED_MAP_GROUP].allowed_values = choices
        if config[ConfigIndex.SELECTED_MAP_GROUP].value not in choices:
            config[ConfigIndex.SELECTED_MAP_GROUP].set("ALL")

    def _sync_selected_map_state(self, config: Config[IndexT]) -> None:
        """SELECTED_MAP only means anything when every map is in play
        ("ALL") — once a custom map group is selected, the maps to
        play come from that group's own list instead (see
        _active_map_group()/run()), so disable SELECTED_MAP rather
        than leave an edit sitting there with no effect."""
        config[ConfigIndex.SELECTED_MAP].read_only = (
            config[ConfigIndex.SELECTED_MAP_GROUP].value != "ALL"
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
                    ConfigIndex.USE_SGSL_OVERRIDES,
                    ConfigIndex.GAME_MODE,
                    ConfigIndex.SELECTED_MAP_GROUP,
                    ConfigIndex.SELECTED_MAP,
                    ConfigIndex.PLAYER_COUNT,
                    ConfigIndex.AUTOMATIC_GAME_UPDATE_CHECK,
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
                    ConfigIndex.STEAM_HELP_TEXT,
                ],
            ),
            TabSpec(
                title="Server",
                items=[
                    ConfigIndex.HOSTNAME,
                    ConfigIndex.SV_LAN,
                    ConfigIndex.SV_PASSWORD,
                    ConfigIndex.SERVER_FREQUENCY,
                ],
            ),
            TabSpec(
                title="Network",
                items=[
                    ConfigIndex.LISTEN_ADDRESS,
                    ConfigIndex.LISTEN_PORT,
                    ConfigIndex.CONSOLE_ENABLED,
                    ConfigIndex.RCON_ENABLE,
                    ConfigIndex.RCON_PASSWORD,
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
                title="Times",
                items=[
                    ConfigIndex.MP_ROUNDTIME,
                    ConfigIndex.MP_ROUNDTIME_DEFUSE,
                    ConfigIndex.MP_ROUNDTIME_HOSTAGE,
                    ConfigIndex.MP_FREEZETIME,
                    ConfigIndex.MP_MAXROUNDS,
                    ConfigIndex.MP_HALFTIME,
                    ConfigIndex.MP_OVERTIME_ENABLE,
                    ConfigIndex.MP_OVERTIME_MAXROUNDS,
                    ConfigIndex.MP_WARMUP_TIME,
                    ConfigIndex.MP_WARMUP_PAUSETIMER,
                    ConfigIndex.MP_WARMUPTIME_ALL_PLAYERS_CONNECTED,
                    ConfigIndex.MP_RESPAWN_IMMUNITYTIME,
                    ConfigIndex.MP_ROUND_RESTART_DELAY,
                    ConfigIndex.MP_TEAM_INTRO_TIME,
                ],
            ),
            TabSpec(
                title="Misc",
                items=[
                    ConfigIndex.MP_FRIENDLYFIRE,
                    ConfigIndex.MP_AUTO_TEAM_BALANCE,
                    ConfigIndex.MP_LIMIT_TEAMS,
                    ConfigIndex.MP_RESPAWN_ON_DEATH_CT,
                    ConfigIndex.MP_RESPAWN_ON_DEATH_T,
                ],
            ),
            TabSpec(
                title="Economy",
                items=[
                    ConfigIndex.MP_STARTMONEY,
                    ConfigIndex.MP_MAXMONEY,
                    ConfigIndex.MP_BUYTIME,
                    ConfigIndex.MP_BUY_DURING_IMMUNITY,
                    ConfigIndex.MP_BUY_ANYWHERE,
                    ConfigIndex.MP_BUY_ALLOW_GUNS,
                    ConfigIndex.MP_BUY_ALLOW_GRENADES,
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
                items=[
                    ConfigIndex.ORDINARY_MAPS,
                    ConfigIndex.WORKSHOP_MAPS,
                    ConfigIndex.PRE_DOWNLOAD_WORKSHOP_MAPS,
                    ConfigIndex.WORKSHOP_MAPS_HELP_TEXT,
                ],
            ),
            TabSpec(
                title="Map groups",
                items=[ConfigIndex.ORDINARY_MAPGROUPS, ConfigIndex.WORKSHOP_MAPGROUPS],
            ),
            TabSpec(
                title="MapVote",
                items=[
                    ConfigIndex.MAPVOTE_ALLOW_VOTES,
                    ConfigIndex.MAPVOTE_ENDMATCH_ENABLE,
                    ConfigIndex.MAPVOTE_MATCH_RESTART_DELAY,
                    ConfigIndex.MAPVOTE_ENDMATCH_DURATION,
                ],
            ),
            TabSpec(
                title="Troubleshooting",
                items=[
                    ConfigIndex.REMOVE_MANIFEST_FILE,
                    ConfigIndex.UPDATE_STEAMCMD,
                ],
            ),
        ]

    def _remove_orphaned_workshop_content(
        self, current_workshop_maps: list[str]
    ) -> None:
        """Delete the downloaded content directory for any workshop
        map id that's no longer in `current_workshop_maps` (i.e. the
        user just removed it from WORKSHOP_MAPS), so it doesn't keep
        taking up disk space until the next full reinstall. Ids that
        currently have no directory on disk (never downloaded, or
        already removed) are silently skipped. Only applies to
        individual maps -- a WORKSHOP_MAPGROUPS collection id is never
        itself downloaded to its own directory (see _workshop_maps()'s
        docstring reference in _normalize_workshop_map()).

        Covers every place a map's content can actually live: CS2's
        own Steamworks-based auto-download cache (_workshop_content_dir()),
        steamcmd's own +workshop_download_item output
        (_workshop_predownload_dir()'s parent -- normally cleared out
        right after a pre-download finishes copying from it, but left
        behind by e.g. a cancelled or killed-mid-copy one), and, if it
        was ever pre-downloaded (see PRE_DOWNLOAD_WORKSHOP_MAPS/
        _predownload_workshop_map()), its maps/workshop/<id>/ cache
        directory (_workshop_map_cache_dir()) -- any, all, or none may
        exist for a given id."""
        current_ids = {self._get_workshop_id(m) for m in current_workshop_maps}
        for content_dir in (
            self._workshop_content_dir(),
            self._workshop_predownload_content_dir(),
            self._ordinary_maps_dir() / "workshop",
        ):
            self._remove_orphaned_workshop_ids(content_dir, current_ids)

    def _remove_orphaned_workshop_ids(
        self, content_dir: Path, current_ids: set[int]
    ) -> None:
        if not content_dir.is_dir():
            return
        for entry in content_dir.iterdir():
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            if int(entry.name) in current_ids:
                continue
            self._remove_workshop_dir(entry)

    def _remove_workshop_dir(self, content_dir: Path) -> None:
        # Best-effort (reraise=False): one locked/in-use directory
        # (e.g. still open in another process) shouldn't abort whatever
        # cleanup pass this is part of -- its failure is still logged,
        # just not raised.
        command_log.run(
            self.print,
            f'rmdir /s /q "{content_dir}"',
            lambda: shutil.rmtree(content_dir),
            reraise=False,
        )

    def _remove_workshop_content_for_id(self, workshop_id: int) -> None:
        """Force-delete every cached copy of workshop item
        `workshop_id` -- all three places content can live, see
        _remove_orphaned_workshop_content() -- regardless of whether
        it's still referenced elsewhere. Used when the user re-adds an
        id/url that's already in WORKSHOP_MAPS, to force a genuinely
        fresh download rather than silently keep reusing whatever's
        already cached (see _dedupe_workshop_maps())."""
        id_str = str(workshop_id)
        for content_dir in (
            self._workshop_content_dir() / id_str,
            self._workshop_predownload_dir(id_str),
            self._workshop_map_cache_dir(id_str),
        ):
            if content_dir.is_dir():
                self._remove_workshop_dir(content_dir)

    def _dedupe_workshop_maps(self, config_item: ConfigItem) -> set[int]:
        """If the same workshop id now appears more than once in
        WORKSHOP_MAPS (the user re-entered an id/url that was already
        in the list, to refresh it), keep only the last -- i.e. the
        just re-added -- occurrence, and force-delete whatever's
        already downloaded for that id (see
        _remove_workshop_content_for_id()) so a fresh download
        actually happens.

        Also drops the id from _known_workshop_maps, so
        config_item_changed() treats it as newly-added below (and
        pre-downloads it again, if enabled) even if its normalized
        string happens to come out unchanged -- re-entering the same
        id is itself the signal to refresh it, regardless of whether
        the title changed.

        Returns the set of workshop ids that were re-added this way,
        so config_item_changed() can tell _predownload_workshop_map()
        to show its dialog as an update rather than a fresh download."""
        seen_ids: set[int] = set()
        updated_ids: set[int] = set()
        deduped: list[str] = []
        for entry in reversed(config_item.value):
            workshop_id = (
                self._get_workshop_id(entry) if self._is_workshop_map(entry) else None
            )
            if workshop_id is not None:
                if workshop_id in seen_ids:
                    updated_ids.add(workshop_id)
                    continue
                seen_ids.add(workshop_id)
            deduped.append(entry)
        deduped.reverse()
        if not updated_ids:
            return updated_ids
        config_item.value = deduped
        self.print(
            "Re-adding workshop item(s) "
            f"{', '.join(str(i) for i in sorted(updated_ids))} -- removing the "
            "existing entry and any downloaded content first"
        )
        for workshop_id in updated_ids:
            self._remove_workshop_content_for_id(workshop_id)
        self._known_workshop_maps = {
            e
            for e in self._known_workshop_maps
            if not (
                self._is_workshop_map(e) and self._get_workshop_id(e) in updated_ids
            )
        }
        return updated_ids

    def config_item_changed(self, config_item, config: Config[IndexT]) -> list[IndexT]:
        if config_item is config[ConfigIndex.WORKSHOP_MAPS]:
            updated_ids = self._dedupe_workshop_maps(config_item)
            self._remove_orphaned_workshop_content(config_item.value)
            current = set(config_item.value)
            new_entries = current - self._known_workshop_maps
            self._known_workshop_maps = current
            affected = [ConfigIndex.SELECTED_MAP]
            if new_entries and config[ConfigIndex.PRE_DOWNLOAD_WORKSHOP_MAPS].value:
                cancelled_entries = {
                    entry
                    for entry in new_entries
                    if not self._predownload_workshop_map(
                        entry,
                        is_update=self._get_workshop_id(entry) in updated_ids,
                    )
                }
                if cancelled_entries:
                    # Cancelled -- drop it back out rather than leave
                    # an entry in the list nothing was ever downloaded
                    # or hosted for.
                    config_item.value = [
                        entry
                        for entry in config_item.value
                        if entry not in cancelled_entries
                    ]
                    self._known_workshop_maps -= cancelled_entries
                    affected.append(ConfigIndex.WORKSHOP_MAPS)
            # Rescan rather than reuse ORDINARY_MAPS' existing value --
            # it's only ever otherwise computed once, back in
            # config_defaults()/config_loaded(), so it wouldn't
            # otherwise reflect a maps/workshop/<id>/ directory that
            # _remove_orphaned_workshop_content() just deleted above
            # (which would leave its "workshop/<id>/<name>" entry, see
            # _downloaded_workshop_maps(), lingering in SELECTED_MAP's
            # allowed_values below despite nothing being there for it
            # anymore) or one _predownload_workshop_map() just added.
            config[ConfigIndex.ORDINARY_MAPS].value = self._ordinary_maps()
            affected.append(ConfigIndex.ORDINARY_MAPS)
            # Keep the selected-map dropdown's choices in sync with
            # the editable map list; if the currently selected map was
            # removed, fall back to the first of what's left.
            maps = self._unique_preserving_order(
                list(config[ConfigIndex.ORDINARY_MAPS].value) + list(config_item.value)
            )
            config[ConfigIndex.SELECTED_MAP].allowed_values = maps
            if maps and config[ConfigIndex.SELECTED_MAP].value not in maps:
                config[ConfigIndex.SELECTED_MAP].set(maps[0])
            return affected
        elif config_item is config[ConfigIndex.ORDINARY_MAPGROUPS]:
            self._refresh_map_group_choices(config)
            # Covers the case where the removed/renamed group was the
            # selected one: _refresh_map_group_choices() just fell
            # SELECTED_MAP_GROUP back to "ALL", so SELECTED_MAP needs
            # to be re-enabled to match.
            self._sync_selected_map_state(config)
            return [ConfigIndex.SELECTED_MAP_GROUP, ConfigIndex.SELECTED_MAP]
        elif config_item is config[ConfigIndex.WORKSHOP_MAPGROUPS]:
            self._refresh_map_group_choices(config)
            self._sync_selected_map_state(config)
            return [ConfigIndex.SELECTED_MAP_GROUP, ConfigIndex.SELECTED_MAP]
        elif config_item is config[ConfigIndex.SELECTED_MAP_GROUP]:
            self._sync_selected_map_state(config)
            return [ConfigIndex.SELECTED_MAP]
        elif config_item is config[ConfigIndex.RCON_ENABLE]:
            self._sync_rcon_password_state(config)
            return [ConfigIndex.RCON_PASSWORD]
        elif config_item is config[ConfigIndex.PLAYER_COUNT]:
            config[ConfigIndex.SV_VISIBLEMAXPLAYERS].set(
                config[ConfigIndex.PLAYER_COUNT].value
            )
        elif config_item is config[ConfigIndex.MP_WARMUP_TIME]:
            if config[ConfigIndex.MP_WARMUP_TIME].value == 0:
                config[ConfigIndex.MP_WARMUP_PAUSETIMER].set(False)
        return []

    def error_report_files(self) -> list[str]:
        # The Valve-provided gamemode_*.cfg files (the pattern also
        # matches the gamemode_*_server.cfg files sgsl generates),
        # plus sgsl_overrides.cfg and the user-maintained
        # sgsl_overrides_append.cfg (if any) -- useful for seeing
        # exactly what was actually written to disk.
        cfg_dir = self._cfg_dir()
        if not cfg_dir.is_dir():
            return []
        files = [
            str(path.relative_to(self.directory))
            for path in cfg_dir.glob("gamemode_*.cfg")
            if path.is_file()
        ]
        for path in (
            self._sgsl_overrides_cfg_path(),
            self._sgsl_overrides_append_cfg_path(),
        ):
            if path.is_file():
                files.append(str(path.relative_to(self.directory)))
        return files
