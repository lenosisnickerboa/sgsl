import re

from config.config_item import (
    ConfigDeliveryType,
    ConfigItem,
    ConfigType,
    Range,
    SchemaField,
)
from config.toml_config import Config
from game.cs2.config_index import ConfigIndex
from support.steam_workshop import fetch_published_file_title

WorkshopMapPattern = re.compile(r"(\d+)(?:\\([^\\]+))?\s*$")
WorkshopUrlIdPattern = re.compile(r"^https?://\S*[?&]id=(\d+)", re.IGNORECASE)


def _parse_workshop_entry(value: str) -> tuple[str, "str | None"]:
    """Extract the workshop id and, if one was already given, the name
    from a raw workshop entry — whether the user typed just the id
    (123), "workshop\\123", the full "workshop\\123\\<name>", or a
    Steam Workshop URL (e.g. "https://steamcommunity.com/sharedfiles/
    filedetails/?id=123"), in which case only the id is extracted from
    it."""
    url_match = WorkshopUrlIdPattern.search(value)
    if url_match is not None:
        value = url_match.group(1)
    match = WorkshopMapPattern.search(value)
    if match is None:
        raise ValueError(
            f"workshop entry must contain a numeric workshop id, got {value!r}"
        )
    return match.group(1), match.group(2)


def _normalize_workshop_map(value: str) -> str:
    """Normalize a workshop entry (an individual map or a collection
    used as a map group) down to "workshop\\<id>\\<name>" — the form
    the name is stored in. If no explicit name was given, the title is
    looked up directly from Valve's public GetPublishedFileDetails API;
    if that lookup fails too (offline, bad id, Steam API hiccup, ...),
    it falls back to "unknown" — re-entering the same id/URL later,
    once reachable, will resolve it.

    For an individual map (WORKSHOP_MAPS), this is only a first guess:
    once the map is actually downloaded, config_loaded() overwrites it
    with the real title read from the server's own publish_data.txt
    (see CS2Game._workshop_maps()), regardless of what's stored here.
    A map group (WORKSHOP_MAPGROUPS) is a Steam Workshop *collection*
    id, which is never itself downloaded to the server (only the maps
    it contains are, once it's actually hosted), so this lookup is the
    only source for its name."""
    workshop_id, name = _parse_workshop_entry(value)
    if name is None:
        name = fetch_published_file_title(int(workshop_id))
    return f"workshop\\{workshop_id}\\{name or 'unknown'}"


def build_game_defaults() -> Config[ConfigIndex]:
    defaults = {
        ConfigIndex.SELECTED_MAP: ConfigItem(
            name="selected_map",
            visible_name="Selected map",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The currently selected map, one of the maps in the selected map group or ALL maps",
            value="",  #  will be filled in later
            # allowed_values=... will be filled in later
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
            value="Casual",
            allowed_values=[
                "Casual",
                "Competitive",
                "ArmsRace",
                "Demolition",
                "DeathMatch",
            ],
        ),
        ConfigIndex.PLAYER_COUNT: ConfigItem(
            name="sv_maxplayers",
            visible_name="Players",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Max number of players",
            value=4,
            range=Range(min_value=1, max_value=64),
        ),
        ConfigIndex.SV_VISIBLEMAXPLAYERS: ConfigItem(
            name="sv_visiblemaxplayers",
            visible_name="Visible max players",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip='Max number of players shown to outside clients, mostly set it to the same as "max number of players"',
            value=4,
            range=Range(min_value=1, max_value=64),
        ),
        # -- Network --
        ConfigIndex.HOSTNAME: ConfigItem(
            name="hostname",
            visible_name="Hostname",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Your servers name",
            value="",  #  will be filled in later
        ),
        ConfigIndex.SV_LAN: ConfigItem(
            name="sv_lan",
            visible_name="LAN only",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="LAN only server, not visible in the internet server browser",
            value=True,
        ),
        ConfigIndex.SV_PASSWORD: ConfigItem(
            name="sv_password",
            visible_name="Server password",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Password required to join, empty means no password",
            value="",
        ),
        # -- Bots --
        ConfigIndex.BOT_DIFFICULTY: ConfigItem(
            name="bot_difficulty",
            visible_name="Bot difficulty",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Bot skill level",
            value="Normal",
            allowed_values=["Harmless", "Easy", "Normal", "Hard", "Harder", "Expert"],
        ),
        ConfigIndex.BOT_QUOTA: ConfigItem(
            name="bot_quota",
            visible_name="Bot quota",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Number of bots to maintain",
            value=4,
            range=Range(min_value=0, max_value=64),
        ),
        ConfigIndex.BOT_QUOTA_MODE: ConfigItem(
            name="bot_quota_mode",
            visible_name="Bot quota mode",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip='How should bots work?\n"fill" - top off empty slots, "normal" = fixed count, "match" = mirror human count',
            value="fill",
            allowed_values=["fill", "normal", "match"],
        ),
        ConfigIndex.BOT_CHATTER: ConfigItem(
            name="bot_chatter",
            visible_name="Bot chatter",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Bot radio chatter verbosity",
            value="off",
            allowed_values=["off", "radio", "minimal", "normal"],
        ),
        ConfigIndex.BOT_WALK: ConfigItem(
            name="bot_walk",
            visible_name="Bots always walk",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Bots always walk instead of run",
            value=False,
        ),
        ConfigIndex.BOT_JOIN_AFTER_PLAYER: ConfigItem(
            name="bot_join_after_player",
            visible_name="Bots join after player",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="When enabled, bots only fill in after a human player joins",
            value=True,
        ),
        ConfigIndex.BOT_ALL_WEAPONS: ConfigItem(
            name="bot_all_weapons",
            visible_name="Bots use all weapons",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Let bots use grenades and the full weapon loadout",
            value=True,
        ),
        # -- Match / round rules --
        ConfigIndex.MP_ROUNDTIME: ConfigItem(
            name="mp_roundtime",
            visible_name="Round time (min)",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Round length in minutes",
            value=5,
            range=Range(min_value=1, max_value=60),
        ),
        ConfigIndex.MP_FREEZETIME: ConfigItem(
            name="mp_freezetime",
            visible_name="Freeze time (s)",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Freeze time at round start, in seconds",
            value=5,
        ),
        ConfigIndex.MP_BUYTIME: ConfigItem(
            name="mp_buytime",
            visible_name="Buy time (s)",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Buy time length, in seconds",
            value=20,
        ),
        ConfigIndex.MP_MAXROUNDS: ConfigItem(
            name="mp_maxrounds",
            visible_name="Max rounds",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Rounds per map, 0 = unlimited",
            value=0,
            range=Range(min_value=0, max_value=24),
        ),
        ConfigIndex.MP_HALFTIME: ConfigItem(
            name="mp_halftime",
            visible_name="Halftime",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Swap sides at half",
            value=True,
        ),
        ConfigIndex.MP_OVERTIME_ENABLE: ConfigItem(
            name="mp_overtime_enable",
            visible_name="Overtime enabled",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Enable overtime if the match is tied",
            value=True,
        ),
        ConfigIndex.MP_OVERTIME_MAXROUNDS: ConfigItem(
            name="mp_overtime_maxrounds",
            visible_name="Overtime max rounds",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Number of overtime rounds",
            value=1,
            range=Range(min_value=0, max_value=24),
        ),
        ConfigIndex.MP_STARTMONEY: ConfigItem(
            name="mp_startmoney",
            visible_name="Start money",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Starting money in round 1",
            value=800,
            range=Range(min_value=0, max_value=16000),
        ),
        ConfigIndex.MP_MAXMONEY: ConfigItem(
            name="mp_maxmoney",
            visible_name="Max money",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Money cap",
            value=16000,
        ),
        ConfigIndex.MP_FRIENDLYFIRE: ConfigItem(
            name="mp_friendlyfire",
            visible_name="Friendly fire",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Friendly fire, i.e. when you shoot at your team mates they take damage",
            value=False,
        ),
        ConfigIndex.MP_AUTO_TEAM_BALANCE: ConfigItem(
            name="mp_autoteambalance",
            visible_name="Auto team balance",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Auto-balance teams between rounds",
            value=False,
        ),
        ConfigIndex.MP_LIMIT_TEAMS: ConfigItem(
            name="mp_limitteams",
            visible_name="Team size limit",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Max player-count difference allowed between teams",
            value=20,
            range=Range(min_value=0, max_value=20),
        ),
        ConfigIndex.MP_WARMUP_TIME: ConfigItem(
            name="mp_warmuptime",
            visible_name="Warmup time",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Warmup length, in seconds. 0 -> disable warmup",
            value=0,
            range=Range(min_value=0, max_value=900),
        ),
        ConfigIndex.MP_WARMUP_PAUSETIMER: ConfigItem(
            name="mp_warmup_pausetimer",
            visible_name="Warmup pause timer",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="When enabled, warmup won't end until manually started",
            value=False,
        ),
        ConfigIndex.MP_DO_WARMUP_OFFLINE: ConfigItem(
            name="mp_do_warmup_offline",
            visible_name="Do warmup offline",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Controls whether the warmup phase happens in offline matches meaning games against bots or local practice matches",
            value=False,
        ),
        ConfigIndex.MP_RESPAWN_ON_DEATH_CT: ConfigItem(
            name="mp_respawn_on_death_ct",
            visible_name="CT respawn on death",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Counter terrorists respawn on death",
            value=True,
        ),
        ConfigIndex.MP_RESPAWN_ON_DEATH_T: ConfigItem(
            name="mp_respawn_on_death_t",
            visible_name="Terrorists respawn on death",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Terrorists respawn on death",
            value=True,
        ),
        # -- Economy / weapons --
        ConfigIndex.MP_FREE_ARMOR: ConfigItem(
            name="mp_free_armor",
            visible_name="Free armor",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Give free armor every round",
            value=False,
        ),
        ConfigIndex.MP_AFTERROUNDMONEY: ConfigItem(
            name="mp_afterroundmoney",
            visible_name="After-round money",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Bonus flat cash awarded at round end",
            value=0,
        ),
        ConfigIndex.MP_DEATH_DROP_GUN: ConfigItem(
            name="mp_death_drop_gun",
            visible_name="Drop gun on death",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Drop weapon on death",
            value=True,
        ),
        ConfigIndex.MP_DEATH_DROP_GRENADE: ConfigItem(
            name="mp_death_drop_grenade",
            visible_name="Drop grenades on death",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Drop grenades on death",
            value=True,
        ),
        # -- Voice / comms --
        ConfigIndex.SV_VOICEENABLE: ConfigItem(
            name="sv_voiceenable",
            visible_name="Voice chat enabled",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Enable voice chat",
            value=True,
        ),
        ConfigIndex.SV_ALLTALK: ConfigItem(
            name="sv_alltalk",
            visible_name="All talk",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="All players hear each other regardless of team",
            value=True,
        ),
        ConfigIndex.SV_DEADTALK: ConfigItem(
            name="sv_deadtalk",
            visible_name="Dead talk",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Dead players can be heard by the living",
            value=True,
        ),
        # -- Cheats / security --
        ConfigIndex.SV_CHEATS: ConfigItem(
            name="sv_cheats",
            visible_name="Cheats enabled",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="Enable if you want to use cheat commands",
            value=False,
        ),
        # -- Maps --
        ConfigIndex.ORDINARY_MAPS: ConfigItem(
            name="ordinary_maps",
            visible_name="Ordinary maps",
            type=ConfigType.ARRAY,
            item_type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Maps installed by the game (as opposed to workshop maps)",
            value=[],  # filled in from maps() in CS2Game.config_defaults()
            read_only=True,
        ),
        ConfigIndex.WORKSHOP_MAPS: ConfigItem(
            name="workshop_maps",
            visible_name="Workshop maps",
            type=ConfigType.ARRAY,
            item_type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Workshop maps downloaded from the Steam workshop. "
            "When adding a new workshop map either use the full url or just the map id. "
            'It will be transformed to workshop\\map-id\\map-name (or map-name will be "unknown" if it can\'t be determined). ',
            value=[],
            transform=_normalize_workshop_map,
        ),
        ConfigIndex.STEAM_API_AUTH_KEY: ConfigItem(
            name="api_auth_key",
            visible_name="API auth key",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The Steam API authorization key used e.g. when hosting workshop maps",
            value="",
        ),
        ConfigIndex.STEAM_GSLT: ConfigItem(
            name="gslt",
            visible_name="Game Server Login Token",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The Game Server Login Token, identifying your game server with Valve",
            value="",
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
        ConfigIndex.REMOVE_MANIFEST_FILE: ConfigItem(
            name="remove_manifest_file",
            visible_name="Remove manifest file before install/update. "
            "This can help when the update process keeps failing.",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Delete the Steam app manifest (appmanifest_730.acf) before installing/updating — use if updates get stuck or fail to detect changes",
            value=False,
        ),
        ConfigIndex.UPDATE_STEAMCMD: ConfigItem(
            name="update_steamcmd",
            visible_name="Update steamcmd before install/update. "
            "Disable this if the steamcmd update for some reason interrupt the update process.",
            type=ConfigType.BOOLEAN,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Re-download the latest steamcmd before installing/updating. Disable to reuse the existing steamcmd if steamcmd download fails.",
            value=True,
        ),
        ConfigIndex.ORDINARY_MAPGROUPS: ConfigItem(
            name="ordinary_mapgroups",
            visible_name="Ordinary map groups",
            type=ConfigType.STRUCT_MAP,
            tooltip="User-defined map groups defining a list of maps to cycle through. "
            "Selecting one of these map groups disables individual map selection since the map is now taken from the map group ",
            value=[],
            item_type=ConfigType.STRING,
            value_type=ConfigType.STRUCT_LIST,
            key_name="map_group",
            schema={
                "name": ConfigType.STRING,
            },
        ),
        ConfigIndex.WORKSHOP_MAPGROUPS: ConfigItem(
            name="workshop_mapgroups",
            visible_name="Workshop map groups",
            type=ConfigType.ARRAY,
            item_type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Workshop map groups downloaded from the Steam workshop. "
            "When adding a new workshop map group either use the full url or just the map group id. "
            'It will be transformed to workshop\\map-group-id\\map-group-name (or map-group-name will be "unknown" if it can\'t be determined).',
            value=[],
            transform=_normalize_workshop_map,
        ),
        # -- Server / network --
        ConfigIndex.SERVER_FREQUENCY: ConfigItem(
            name="server_frequency",
            visible_name="Server frequency (Hz)",
            type=ConfigType.STRING_LIST,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The server tickrate (Hz)",
            value="64",
            allowed_values=["64", "128"],
        ),
        ConfigIndex.LISTEN_ADDRESS: ConfigItem(
            name="listen_address",
            visible_name="Listen address",
            type=ConfigType.STRING,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="Listen on this host IP address (0.0.0.0 == all interfaces). Recommended to keep default since changing this many times lead to issues (google it)",
            value="0.0.0.0",
        ),
        ConfigIndex.LISTEN_PORT: ConfigItem(
            name="listen_port",
            visible_name="Listen port",
            type=ConfigType.INTEGER,
            config_type=ConfigDeliveryType.COMMAND_LINE,
            tooltip="The game server's listen port",
            value=27015,
            range=Range(min_value=1, max_value=65535),
        ),
        ConfigIndex.RCON_ENABLE: ConfigItem(
            name="rcon_enable",
            visible_name="RCON",
            type=ConfigType.BOOLEAN,
            tooltip="Enable remote administration, RCON, over the game's own port, "
            "authenticated with RCON password below",
            value=False,
        ),
        ConfigIndex.RCON_PASSWORD: ConfigItem(
            name="rcon_password",
            visible_name="RCON password",
            type=ConfigType.MASKED_STRING,
            config_type=ConfigDeliveryType.SERVER_CFG_FILE,
            tooltip="The RCON password for remote administration, only takes effect while "
            "RCON is enabled",
            value="",
        ),
        ConfigIndex.CONSOLE_ENABLED: ConfigItem(
            name="console_enabled",
            visible_name="Console",
            type=ConfigType.BOOLEAN,
            tooltip="Show the server's console window",
            value=True,
        ),
    }
    _link_map_group_schema_fields(defaults)
    return defaults


def _link_map_group_schema_fields(defaults: Config[ConfigIndex]) -> None:
    """Point ORDINARY_MAPGROUPS' struct "name" field at SELECTED_MAP's
    allowed_values (rather than leaving it free text), so its editor
    offers the same choices as that item — done as a separate pass
    after the dict above is fully built, since a schema built inline
    within that dict can't yet refer to a sibling entry defined
    elsewhere in the same literal. SELECTED_MAP's allowed_values is
    populated later, by CS2Game.config_defaults()/config_loaded() —
    this holds a live reference to that ConfigItem, so it stays
    correct once that happens (see SchemaField)."""
    schema = defaults[ConfigIndex.ORDINARY_MAPGROUPS].schema
    schema["name"] = SchemaField(
        ConfigType.STRING_LIST, allowed_values_from=defaults[ConfigIndex.SELECTED_MAP]
    )
