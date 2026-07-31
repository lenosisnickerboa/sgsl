import re

from config.config_item import (
    ConfigDeliveryType,
    ConfigItem,
    ConfigType,
    Range,
    SchemaField,
)
from config.toml_config import Config
from game.vu.config_index import ConfigIndex


def build_game_defaults() -> Config[ConfigIndex]:
    defaults = {
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The currently selected map, one of the maps in the selected map group or ALL maps",
            value="",  #  will be filled in later
            # will be filled in later allowed_values=[],
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
            # will be filled in later allowed_values=[],
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="vars.maxPlayers",
            visible_name="Players",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Player count",
            value=4,
            range=Range(min_value=2, max_value=64),
        ),
        ConfigIndex.PLAYER_COUNT_START_ROUND: ConfigItem(
            name="vars.roundStartPlayerCount",
            visible_name="PlayersStart",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Players needed before server starts",
            value=1,
            range=Range(min_value=1, max_value=64),
        ),
        ConfigIndex.PLAYER_COUNT_RESTART_ROUND: ConfigItem(
            name="vars.roundRestartPlayerCount",
            visible_name="PlayersRestart",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Players needed to cause server to restart",
            value=0,
            range=Range(min_value=0, max_value=64),
        ),
        ConfigIndex.SERVER_UPDATE_FREQUENCY: ConfigItem(
            name="update_frequency",
            visible_name="Server frequence (Hz)",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The server tickrate (Hz)",
            value="60",
            allowed_values=["60", "120"],
        ),
        ConfigIndex.LISTEN_HOST: ConfigItem(
            name="listen_host",
            visible_name="Listen Address",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Listen on this host IP address (0.0.0.0 == all interfaces)",
            value="0.0.0.0",
        ),
        ConfigIndex.LISTEN_PORT_FROSTBITE: ConfigItem(
            name="listen_port_frostbite",
            visible_name="Frostbite Listen Port",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The Frostbite network layer listen port",
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
            value="",  #  will be filled in later
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
            tooltip="Download the VU archive from this URL. Don't change unless this URL does not work.",
            value="https://veniceunleashed.net/files/vu.zip",
        ),
        ConfigIndex.RUN_COMMAND_EDIT: ConfigItem(
            name="run_command_edit",
            visible_name="Edit run command",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Show an editable copy of the launch command before starting the server",
            value=False,
        ),
        ConfigIndex.CUSTOM_RUN_COMMAND_PRE: ConfigItem(
            name="custom_run_command_pre",
            visible_name="Custom run command (pre)",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Prepended before the first argument when starting the server",
            value="",
        ),
        ConfigIndex.CUSTOM_RUN_COMMAND_POST: ConfigItem(
            name="custom_run_command_post",
            visible_name="Custom run command (post)",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Appended after the last argument when starting the server",
            value="",
        ),
        ConfigIndex.COLOR_CORRECTION_ENABLED: ConfigItem(
            name="vu.ColorCorrectionEnabled",
            visible_name="Color correction",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Enable the blue-tint color correction filter",
            value=True,
        ),
        ConfigIndex.SQUAD_SIZE: ConfigItem(
            name="vu.SquadSize",
            visible_name="Squad size",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Maximum number of players per squad",
            value=4,
            range=Range(min_value=1),
        ),
        ConfigIndex.SUN_FLARE_ENABLED: ConfigItem(
            name="vu.SunFlareEnabled",
            visible_name="Sun flare",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Enable the sun flare",
            value=True,
        ),
        ConfigIndex.DISABLE_PRE_ROUND: ConfigItem(
            name="vu.DisablePreRound",
            visible_name="Disable pre-round",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Disable the preround",
            value=True,
        ),
        ConfigIndex.CORPSE_DAMAGE_ENABLED: ConfigItem(
            name="vu.CorpseDamageEnabled",
            visible_name="Corpse damage",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Allow dealing damage to a corpse, preventing revival",
            value=False,
        ),
        ConfigIndex.MODS_FUN_BOTS_ENABLED: ConfigItem(
            name="modsFunBotsEnabled",
            visible_name="Fun Bots",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Enable mod fun-boots",
            value=True,
        ),
        ConfigIndex.MODS_FUN_BOTS_URL: ConfigItem(
            name="modsFunBotsUrl",
            visible_name="Fun bots URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the fun-bots mod from this URL. Only change URL if this download does not work or if you want to upgrade the fun-bots mod.",
            value="https://github.com/Joe91/fun-bots/archive/refs/tags/V3.0.0-Release.zip",
        ),
        ConfigIndex.ORDINARY_MAPGROUPS: ConfigItem(
            name="ordinary_mapgroups",
            visible_name="Ordinary map groups",
            type=ConfigType.STRUCT_MAP,
            tooltip="User-defined map groups, each a named list of maps, modes and rounds to execute",
            value=[],
            item_type=ConfigType.STRING,
            value_type=ConfigType.STRUCT_LIST,
            key_name="map_group",
            schema={
                "name": ConfigType.STRING,
                "mode": ConfigType.STRING,
                "rounds": ConfigType.INTEGER,
            },
        ),
        # -- Maps --
        ConfigIndex.ORDINARY_MAPS: ConfigItem(
            name="ordinary_maps",
            visible_name="Ordinary maps",
            type=ConfigType.ARRAY,
            item_type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Maps installed by the game",
            value=[],  # filled in, along with allowed_values, by VUGame.config_defaults()
            read_only=True,
        ),
    }
    _link_map_group_schema_fields(defaults)
    return defaults


def _link_map_group_schema_fields(defaults: Config[ConfigIndex]) -> None:
    """Point ORDINARY_MAPGROUPS' struct "name"/"mode" fields at
    ORDINARY_MAPS'/GAME_MODE's allowed_values (rather than leaving
    them free text), so its editor offers the same choices as those
    items — done as a separate pass after the dict above is fully
    built, since a schema built inline within that dict can't yet
    refer to a sibling entry defined elsewhere in the same literal.
    ORDINARY_MAPS/GAME_MODE's allowed_values is populated later, by
    VUGame.config_defaults() — this holds a live reference to those
    ConfigItems, so it stays correct once that happens (see
    SchemaField)."""
    schema = defaults[ConfigIndex.ORDINARY_MAPGROUPS].schema
    schema["name"] = SchemaField(
        ConfigType.STRING_LIST, allowed_values_from=defaults[ConfigIndex.ORDINARY_MAPS]
    )
    schema["mode"] = SchemaField(
        ConfigType.STRING_LIST, allowed_values_from=defaults[ConfigIndex.GAME_MODE]
    )
