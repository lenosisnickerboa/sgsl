from app.config_index import ConfigIndex
from config.config_item import ConfigItem, ConfigType, Range, finalize_default
from config.toml_config import Config


def build_app_defaults() -> Config[ConfigIndex]:
    defaults = {
        ConfigIndex.TERMINAL_ENABLED: ConfigItem(
            name="terminal_enable",
            visible_name="Enable terminal",
            type=ConfigType.BOOLEAN,
            value=False,
        ),
        ConfigIndex.TERMINAL_LOG_MAX_LINES: ConfigItem(
            name="terminal_log_max_lines",
            visible_name="Terminal log max lines",
            type=ConfigType.INTEGER,
            tooltip="Maximum number of lines kept in the terminal log; 0 = no limit",
            value=0,
            range=Range(min_value=0),
        ),
        ConfigIndex.SNAP_WINDOWS_ENABLED: ConfigItem(
            name="snap_windows_enabled",
            visible_name="Snap windows",
            type=ConfigType.BOOLEAN,
            tooltip="Snap the terminal/config windows to and drag them along with the main window",
            value=True,
        ),
        ConfigIndex.AUTOMATIC_UPDATE_CHECK: ConfigItem(
            name="automatic_update_check",
            visible_name="Automatic update check",
            type=ConfigType.BOOLEAN,
            tooltip="Check GitHub for a newer sgsl release on startup",
            value=True,
        ),
        ConfigIndex.AUTO_OPEN_TERMINAL_ON_INSTALL_OR_UPDATE: ConfigItem(
            name="auto_open_terminal_on_install_or_update",
            visible_name="Auto open terminal on install/update",
            type=ConfigType.BOOLEAN,
            tooltip="If the terminal isn't already open, open it automatically when "
            "install/update starts and close it again once it finishes successfully "
            "(left open if it was already open, or if install/update fails)",
            value=True,
        ),
    }
    for item in defaults.values():
        finalize_default(item)
    return defaults
