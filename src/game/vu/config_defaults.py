import re
from pathlib import Path

from config.config_item import (
    ConfigDeliveryType,
    ConfigItem,
    ConfigType,
    Range,
    SchemaField,
)
from config.toml_config import Config
from game.vu.config_index import ConfigIndex

# Relative to the game's install directory (self.directory) -- see
# ConfigItem.file_path.
_FunBotsConfigLuaPath = str(
    Path("server") / "Admin" / "mods" / "fun-bots" / "ext" / "Shared" / "Config.lua"
)

# RCON_SHORTCUTS' default value: sgsl's own curated shortlist of the
# 20 most commonly used VU/Frostbite ("Plasma" RCON) dedicated server
# admin console commands (no authoritative usage-frequency source
# exists) -- covering match control, player admin, and core server
# settings. See RconWindow's own docstring for how these are used
# (one-click-insert buttons, not sent immediately).
RconQuickCommands = [
    "admin.say",
    "admin.yell",
    "admin.listPlayers",
    "admin.kickPlayer",
    "admin.banPlayer",
    "admin.shutDown",
    "mapList.list",
    "mapList.nextLevelIndex",
    "mapList.runNextRound",
    "mapList.restartRound",
    "mapList.endRound",
    "vars.serverName",
    "vars.gamePassword",
    "vars.roundTimeLimit",
    "vars.maxPlayers",
    "vars.friendlyFire",
    "banList.list",
    "banList.save",
    "serverInfo",
    "version",
]


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
            value=9,
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
        ConfigIndex.LISTEN_ADDRESS: ConfigItem(
            name="listen_address",
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
        ConfigIndex.RCON_PASSWORD: ConfigItem(
            name="admin.password",
            visible_name="RCON password",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="The RCON password for remote administration, only takes effect while "
            "RCON is enabled -- distinct from the server (join) password above",
            value="",
        ),
        ConfigIndex.RCON_SHORTCUTS: ConfigItem(
            name="rcon_shortcuts",
            visible_name="RCON quick command shortcuts",
            type=ConfigType.ARRAY,
            item_type=ConfigType.STRING,
            tooltip=f"The {len(RconQuickCommands)} one-click-insert commands shown as "
            "buttons in the RCON console window, one per button. Select an entry "
            "then edit it and click Update to change it -- the list can't grow or "
            "shrink, since it has exactly one entry per button.",
            value=list(RconQuickCommands),
            array_length=len(RconQuickCommands),
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
        ConfigIndex.ROUND_TIME: ConfigItem(
            name="vars.roundTimeLimit",
            visible_name="Round time (min)",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Round time in minutes. Set it to 0 for indefinite round time.",
            value=5,
            range=Range(min_value=0, max_value=60),
        ),
        ConfigIndex.TICKET_COUNT_MODIFIER: ConfigItem(
            name="vars.gameModeCounter",
            visible_name="Ticket count modifier",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Modifies the ticket count (or time, depending on game mode) as a percentage of the default",
            value=100,
            range=Range(min_value=0, max_value=1000),
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
        ConfigIndex.MODS_VOTEMAP_ENABLED: ConfigItem(
            name="modsVotemapEnabled",
            visible_name="Votemap",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Enable mod vu-mapvote",
            value=True,
        ),
        ConfigIndex.MODS_VOTEMAP_URL: ConfigItem(
            name="modsVotemapUrl",
            visible_name="Votemap URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the vu-mapvote mod from this URL. Only change URL if this download does not work or if you want to upgrade the votemap mod.",
            value="https://gitlab.com/n4gi0s/vu-mapvote/-/jobs/artifacts/master/download?job=build",
        ),
        ConfigIndex.MODS_VOTEMAP_PATCH_ENABLED: ConfigItem(
            name="modsVotemapPatchEnabled",
            visible_name="Votemap patch",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="After installing the vu-mapvote mod, also download and extract this patch on top of "
            "it (overwriting some of its files). Only applies while Votemap is also enabled.",
            value=True,
        ),
        ConfigIndex.MODS_VOTEMAP_PATCH_URL: ConfigItem(
            name="modsVotemapPatchUrl",
            visible_name="Votemap patch URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the vu-mapvote patch from this URL. Only change URL if this download does not work or if you want to upgrade the patch.",
            value="https://github.com/muppet99/BF3-Mods-Votemap/archive/refs/heads/main.zip",
        ),
        ConfigIndex.MODS_MORE_GORE_ENABLED: ConfigItem(
            name="modsMoreGoreEnabled",
            visible_name="VU-More-Gore",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Enable mod VU-More-Gore",
            value=True,
        ),
        ConfigIndex.MODS_MORE_GORE_URL: ConfigItem(
            name="modsMoreGoreUrl",
            visible_name="VU-More-Gore URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the VU-More-Gore mod from this URL. Only change URL if this download does not work or if you want to upgrade the mod.",
            value="https://github.com/lywit/VU-More-Gore/releases/download/Release-1.4.0/VU-More-Gore.zip",
        ),
        ConfigIndex.MODS_HEAD_HIT_SOUNDS_ENABLED: ConfigItem(
            name="modsHeadHitSoundsEnabled",
            visible_name="Head hit sounds effect",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Enable mod head-hit-sounds-effect",
            value=True,
        ),
        ConfigIndex.MODS_HEAD_HIT_SOUNDS_URL: ConfigItem(
            name="modsHeadHitSoundsUrl",
            visible_name="Head hit sounds effect URL",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Download the head-hit-sounds-effect mod from this URL. Only change URL if this download does not work or if you want to upgrade the mod.",
            value="https://community.veniceunleashed.net/uploads/short-url/z5dOyKLuxQmnwe3Gu81V1bDLQp2.zip",
        ),
        ConfigIndex.MAPVOTE_RANDOMIZE: ConfigItem(
            name="mapvote.randomize",
            visible_name="Randomize map vote choices",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Randomize the maps offered in the map vote, instead of always offering them in map list order",
            value=False,
        ),
        ConfigIndex.MAPVOTE_LIMIT: ConfigItem(
            name="mapvote.limit",
            visible_name="Map vote choice limit",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Number of selectable random maps",
            value=15,
            range=Range(min_value=2, max_value=30),
        ),
        ConfigIndex.MAPVOTE_EXCLUDE_CURRENT_MAP: ConfigItem(
            name="mapvote.excludecurrentmap",
            visible_name="Exclude current map from vote",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Exclude the currently playing map from the map vote choices",
            value=False,
        ),
        ConfigIndex.BOTS_IGNORE_PERMISSIONS: ConfigItem(
            name="Config.IgnorePermissions",
            visible_name="Bots ignore permissions",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.LUA_CONFIG_FILE,
            file_path=_FunBotsConfigLuaPath,
            tooltip="Let fun-bots ignore Venice Unleashed's normal admin/permission checks. Recommended to leave as is, unless you know what you're doing and want to use Venice Unleashed's permission system to control fun-bots.",
            value=True,
        ),
        ConfigIndex.BOT_ADDITIONAL_SPAWN_DELAY: ConfigItem(
            name="Config.AdditionalBotSpawnDelay",
            visible_name="Bot additional spawn delay",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.LUA_CONFIG_FILE,
            file_path=_FunBotsConfigLuaPath,
            tooltip="Extra delay (in seconds) before a bot spawns. Included so the VU-More-Gore mod has time to affect bots as well, the same way it does regular players.",
            value=5,
        ),
        ConfigIndex.BOTS_HELP_TEXT: ConfigItem(
            name="bots_help_text",
            visible_name="Bots help",
            type=ConfigType.STATIC_TEXT,
            value=(
                "\n"
                "To further configure bots use the in-game bots editor by pressing F12 in-game.\n"
                "To read more about the bot mod go here: https://github.com/Joe91/fun-bots"
            ),
            read_only=True,
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
            display_rows=15,
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
