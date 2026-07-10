from config.config_item import ConfigItem, ConfigType
from config.toml_config import Config
from game.null_game.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING,
            value="",
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="player_count",
            visible_name="Players",
            type=ConfigType.INTEGER,
            value=4,
        ),
        ConfigIndex.FRIENDLY_FIRE_ENABLED: ConfigItem(
            name="friendly_fire_enabled",
            visible_name="Friendly fire",
            type=ConfigType.BOOLEAN,
            value=False,
        ),
    }
