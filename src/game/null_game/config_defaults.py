from config.config_item import ConfigItem, ConfigType, Range
from config.toml_config import Config
from game.null_game.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.GAME_MODE: ConfigItem(
            name="selected_map",
            visible_name="Game mode",
            type=ConfigType.STRING_LIST,
            value="GunGame",
            allowed_values=["GunGame", "DeathMatch", "Classic"],
#            validator=lambda v: v in ["GunGame", "DeathMatch", "Classic"],
        ),
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING_LIST,
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
        ConfigIndex.DUMMY_0: ConfigItem(
            name="dummy_0",
            visible_name="Dummy 0",
            type=ConfigType.BOOLEAN,
            tooltip="This is tooltip for dummy 0 with default value False",
            value=False,
        ),
        ConfigIndex.DUMMY_1: ConfigItem(
            name="dummy_1",
            visible_name="Dummy 1",
            type=ConfigType.BOOLEAN,
            tooltip="This is tooltip for dummy 1 with default value True",
            value=True,
        ),
        ConfigIndex.DUMMY_2: ConfigItem(
            name="dummy_2",
            visible_name="Dummy 2",
            type=ConfigType.STRING_LIST,
            tooltip="This is tooltip for dummy 2 with default value \"dummy_2_value_3\"",
            value="dummy_2_value_3",
            allowed_values=["dummy_2_value_0", "dummy_2_value_1", "dummy_2_value_2", "dummy_2_value_3", "dummy_2_value_4"]
        ),
        ConfigIndex.DUMMY_3: ConfigItem(
            name="dummy_3",
            visible_name="Dummy 3",
            type=ConfigType.INTEGER,
            tooltip="This is tooltip for dummy 3 with default value 42",
            value=42,
            range=Range(min_value=40, max_value=49),
        ),
        ConfigIndex.DUMMY_4: ConfigItem(
            name="dummy_4",
            visible_name="Dummy 4",
            type=ConfigType.BOOLEAN,
            tooltip="This is tooltip for dummy 4 with default value False",
            value=False,
        ),
        ConfigIndex.DUMMY_5: ConfigItem(
            name="dummy_5",
            visible_name="Dummy 5",
            type=ConfigType.STRING_LIST,
            tooltip="This is tooltip for dummy 5 with default value \"dummy_5_value_0\"",
            value="dummy_5_value_0",
            allowed_values=["dummy_5_value_0", "dummy_5_value_1", "dummy_5_value_2", "dummy_5_value_3", "dummy_5_value_4"]
        ),
        ConfigIndex.DUMMY_6: ConfigItem(
            name="dummy_6",
            visible_name="Dummy 6",
            type=ConfigType.STRING,
            tooltip="This is tooltip for dummy 6 with default value \"nisse\"",
            value="nisse",
            max_length=12,
        ),
        ConfigIndex.DUMMY_7: ConfigItem(
            name="dummy_7",
            visible_name="Dummy 7",
            type=ConfigType.INTEGER,
            tooltip="This is tooltip for dummy 7 with default value 44",
            value=44,
            range=Range(min_value=40, max_value=49),
        ),
        ConfigIndex.DUMMY_8: ConfigItem(
            name="dummy_8",
            visible_name="Dummy 8",
            type=ConfigType.INTEGER,
            tooltip="This is tooltip for dummy 8 with default value 45",
            value=45,
            range=Range(min_value=40, max_value=49),
        ),
        ConfigIndex.DUMMY_9: ConfigItem(
            name="dummy_9",
            visible_name="Dummy 9",
            type=ConfigType.INTEGER,
            tooltip="This is tooltip for dummy 9 with default value 46",
            value=46,
            range=Range(min_value=40, max_value=49),
        ),
    }
