import re

from config.config_item import ConfigDeliveryType, ConfigItem, ConfigType, Range
from config.toml_config import Config
from game.vu.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    return {
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The currently selected map, one of the maps in the selected map group",
            value="",  #  will be filled in later
            allowed_values=[
                #  will be filled in later
            ],
        ),
        ConfigIndex.SELECTED_MAP_GROUP: ConfigItem(
            name="selected_map_group",
            visible_name="Selected map group",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip='The currently selected map group, if "ALL" all maps are included',
            value="ALL",
            # allowed_values=... will be filled in later
        ),
        ConfigIndex.GAME_MODE: ConfigItem(
            name="game_mode",
            visible_name="Game mode",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Currently selected game mode",
            value="",  # will be filled in later
            allowed_values=[
                # will be filled in later
            ],
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="sv_maxplayers",
            visible_name="Players",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Total player slots — adjust to your group size",
            value=4,
            range=Range(min_value=1, max_value=64),
        ),
        ConfigIndex.SERVER_KEY: ConfigItem(
            name="server_key",
            visible_name="Server Key",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="The server key (identifies your server with the VU site)",
            value="",
        ),
        ConfigIndex.SERVER_UPDATE_FREQUENCY: ConfigItem(
            name="update_frequency",
            visible_name="Update frequence",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The server update frequency",
            value="60",
            allowed_values=["60", "120"],
        ),
        ConfigIndex.LISTEN_HOST: ConfigItem(
            name="listen_host",
            visible_name="Listen Host Address",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Listen on this host IP address (0.0.0.0 == all interfaces)",
            value="0.0.0.0",
        ),
        ConfigIndex.LISTEN_PORT_FROSTBYTE: ConfigItem(
            name="listen_port_frostbyte",
            visible_name="Frostbyte Listen Port",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The Frostbyte network layer listen port",
            value=25200,
            range=Range(min_value=1, max_value=65535),
        ),
        ConfigIndex.LISTEN_PORT_HARMONY: ConfigItem(
            name="listen_port_harmony",
            visible_name="Harmony Listen Port",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The monitored Harmony, the VU network layer listen port",
            value=7948,
            range=Range(min_value=1, max_value=65535),
        ),
        ConfigIndex.LISTEN_PORT_RCON: ConfigItem(
            name="listen_port_rcon",
            visible_name="RCON Listen Port",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The RCON listen port for remote administration",
            value=47200,
            range=Range(min_value=1, max_value=65535),
        ),
        ConfigIndex.RCON_ENABLE: ConfigItem(
            name="rcon_enable",
            visible_name="RCON",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Enable remote administration, RCON",
            value=True,
        ),
        ConfigIndex.SERVER_NAME: ConfigItem(
            name="vars.serverName",
            visible_name="Server Name",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Your servers name",
            value="My own VU server",
        ),
        ConfigIndex.SERVER_PASSWORD: ConfigItem(
            name="vars.gamePassword",
            visible_name="Server Password",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="The server password (required to be entered by all users logging in to your server)",
            value="",
        ),
        ConfigIndex.FRIENDLY_FIRE: ConfigItem(
            name="vars.friendlyFire",
            visible_name="Friendly fire",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Friendly fire, i.e. when you shoot at your team mates they take damage",
            value=False,
        ),
        ConfigIndex.DOWNLOAD_URL: ConfigItem(
            name="downloadURL",
            visible_name="Download URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the VU archive from this URL",
            value="https://veniceunleashed.net",
        ),
    }
