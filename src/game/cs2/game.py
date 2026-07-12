import re
import shutil
from pathlib import Path
from typing import Callable, Optional, Union
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
from game.cs2.config_defaults import build_game_defaults
from game.cs2.config_index import ConfigIndex
from game.game import Game, OperationResult
from support import bat_runner
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

    def detect(self) -> bool:
        return self.server_binary.exists()

    def get_short_name(self) -> str:
        return "cs2"

    def get_long_name(self) -> str:
        return "Counter-Strike 2"

    # def download_steamcmd(self, cancel_token, progress_cb=None) -> bool:
    #     steamcmd_dir = self.directory / "steamcmd"
    #     steamcmd_zip = steamcmd_dir / "steamcmd.zip"
    #     steamcmd_command= steamcmd_dir / "steamcmd"

    #     steamcmd_dir.mkdir(parents=True, exist_ok=True)

    #     bat_runner.run([
    #         f"curl https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -o {steamcmd_zip}",
    #         f"tar -xf {steamcmd_zip} -C {steamcmd_command}",
    #         f"{steamcmd_command} +force_install_dir {self.server_root} +login anonymous +app_update 730 validate +quit",
    #         ], 
    #         self.directory, 
    #         lambda l: self.print(l)
    #     )

    #     def on_download_progress(downloaded, total):
    #         cancel_token.raise_if_cancelled()
    #         if progress_cb and total:
    #             progress_cb(int(downloaded / total * 100))

    #     result = download_with_return(
    #         "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
    #         steamcmd_zip,
    #         progress_callback=on_download_progress,
    #     )
    #     if not result:
    #         return False
    #     return unzip_with_return(steamcmd_zip)

    # def install_or_update(self, result_callback: Callable[[OperationResult], None]) -> None:

    #     def on_done(result):
    #         self.print(f"Downloaded steamcmd finished: {result}")
    #         result_callback(OperationResult.OK if result else OperationResult.FAIL)

    #     def on_progress(pct):
    #         self.print(f"Downloading steamcmd : {pct}")

    #     task = TaskRunner("Download steamcmd", self.download_steamcmd, done_cb=on_done, progress_cb=on_progress)
    #     task.run_async()

    #     command = Path("steamcmd") / "steamcmd"
    #     args=["+force_install_dir", str(self.server_root), "+login", "anonymous", "+app_update", "730", "validate", "+quit"]
    #     super().start_command(command, args)

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

    _DiskSpaceLogPattern = re.compile(r'Failed to preallocate \(Not enough disk space\) "([^"]+)"')

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
        free_gb = shutil.disk_usage(self.server_root).free / (1024 ** 3)
        return (
            f"Not enough disk space to install {self.get_long_name()}: needs {required} free, "
            f"but only {free_gb:.2f} GB free on {self.server_root.drive or self.server_root.anchor}"
        )

    def install_or_update(self, result_callback: Callable[[OperationResult], None]) -> None:
        steamcmd_dir = self.directory / "steamcmd"
        steamcmd_zip = steamcmd_dir / "steamcmd.zip"

        steamcmd_dir.mkdir(parents=True, exist_ok=True)

        def on_output(l):
            self.print(l)

        def run_update_install(attempt: int):
            def on_result(exit_code):
                if self.server_binary.exists():
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
                    self.print(f"Failed to install {self.get_long_name()} after {self.InstallAttempts} attempts")
                    result_callback(OperationResult.FAIL)

            bat_runner.run(
                [f"cd {steamcmd_dir}", "update_install.bat"],
                self.directory,
                on_output,
                on_result,
            )

        def on_setup_result(exit_code):
            run_update_install(1)

        # Pinned to the Windows-native executables via their full paths:
        # PATH commonly also resolves to Git for Windows' curl/tar
        # (e.g. C:\Program Files\Git\usr\bin\tar.exe), whose GNU tar
        # misreads a bare drive-letter path like "C:\..." as a
        # host:path remote-tape spec ("Cannot connect to C:").
        bat_runner.run([
            f"curl.exe https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -o {steamcmd_zip}",
            f"tar.exe -xf {steamcmd_zip} -C {steamcmd_dir}",
            f"cd {steamcmd_dir}",
            f"echo steamcmd +force_install_dir {self.server_root} +login anonymous +app_update 730 validate +quit > update_install.bat",
            ],
            self.directory,
            on_output,
            on_setup_result,
        )

    def install(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Installing {self.get_long_name()} into {self.server_root}")
        self.install_or_update(result_callback)

    def update(self, result_callback: Callable[[OperationResult], None]) -> None:
        self.print(f"Updating {self.get_long_name()} in {self.server_root}")
        self.install_or_update(result_callback)

    def run(self, config: Config[IndexT]) -> None:
        args=["-dedicated", "-usercon", "+game_type", "TYPE", "+game_mode", "MODE", "+map", "MAP", "-maxplayers", "<number>"]
        game_mode = config[ConfigIndex.GAME_MODE].value
        if game_mode == "Casual":
            args[3]="0" # game_type
            args[5]="0" # gamne_mode
        elif game_mode == "Competitive":
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

    def config_tabs(self) -> list[TabSpec]:
        return [TabSpec(title="General", items=list(self.config_defaults().keys()))]

    # def config_item_changed(self, config_item: IndexT, config: Config[IndexT]) -> None:
    #     self.print(f"config_item_changed({config_item}, {config})")
