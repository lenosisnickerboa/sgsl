from config.config_item import ConfigItem, ConfigType
from config.toml_config import Config
from game.cs2.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING,
            tooltip="The currently selected map, one of the maps in the selected map group",
            value="",
        ),
        ConfigIndex.SELECTED_MAP_GROUP: ConfigItem(
            name="selected_map_group",
            visible_name="Selected map group",
            type=ConfigType.STRING,
            tooltip="The currently selected map group, if \"ALL\" all maps are included",
            value="ALL",
            #allowed_values=... will be filled in later
        ),
        ConfigIndex.GAME_MODE: ConfigItem(
            name="game_mode",
            visible_name="Game mode",
            type=ConfigType.STRING,
            tooltip="Currently selected game mode",
            value="Casual",
            allowed_values=["Casual", "GunGame", "DeatMatch"]
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="player_count",
            visible_name="Players",
            type=ConfigType.INTEGER,
            tooltip="Number of players",
            value=4,
        ),
        ConfigIndex.FRIENDLY_FIRE_ENABLED: ConfigItem(
            name="friendly_fire_enabled",
            visible_name="Friendly fire",
            type=ConfigType.BOOLEAN,
            tooltip="When enabled you can shoot your team mates",
            value=False,
        ),
    }
