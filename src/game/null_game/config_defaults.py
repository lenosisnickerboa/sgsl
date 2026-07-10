from config.config_item import ConfigItem, ConfigType, Range
from config.toml_config import Config
from game.null_game.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.GAME_MODE: ConfigItem(
            name="selected_map",
            visible_name="Game mode",
            type=ConfigType.STRING,
            value="GunGame",
            allowed_values=["GunGame", "DeathMatch", "Classic"],
#            validator=lambda v: v in ["GunGame", "DeathMatch", "Classic"],
        ),
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING,
            tooltip="The currently selected map",
            value="", #will be filled in later
            #allowed_values=... will be filled in later
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="player_count",
            visible_name="Players",
            type=ConfigType.INTEGER,
            tooltip="Number of players",
            value=4,
            range=Range(min_value=1, max_value=32),
#            validator=lambda v: 1 <= v <= 32,
        ),
        ConfigIndex.FRIENDLY_FIRE_ENABLED: ConfigItem(
            name="friendly_fire_enabled",
            visible_name="Friendly fire",
            type=ConfigType.BOOLEAN,
            tooltip="When enabled you can shoot your team mates",
            value=False,
        ),
    }
