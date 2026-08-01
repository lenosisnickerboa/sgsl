from enum import IntEnum


class ConfigIndex(IntEnum):
    """Stable, permanent numeric IDs for config items.

    IMPORTANT: Once this product has shipped a release, never reuse or
    renumber existing values, even if an item is removed/deprecated —
    only ever append new entries with new numbers, to keep saved/
    serialized configs (files, network data, etc.) valid across
    versions. Pre-release, numbers are free to be reused/renumbered.
    """

    SELECTED_MAP = 1
    SELECTED_MAP_GROUP = 2
    GAME_MODE = 3
    PLAYER_COUNT = 4
    RUN_COMMAND_EDIT = 5
    SERVER_UPDATE_FREQUENCY = 6
    LISTEN_ADDRESS = 7
    LISTEN_PORT_FROSTBITE = 8
    LISTEN_PORT_HARMONY = 9
    LISTEN_PORT_RCON = 10
    RCON_ENABLE = 11
    SERVER_NAME = 12
    SERVER_PASSWORD = 13
    FRIENDLY_FIRE = 14
    DOWNLOAD_URL = 15
    PLAYER_COUNT_START_ROUND = 16
    PLAYER_COUNT_RESTART_ROUND = 17
    MODS_FUN_BOTS_ENABLED = 18
    MODS_FUN_BOTS_URL = 19
    CUSTOM_RUN_COMMAND_PRE = 20
    CUSTOM_RUN_COMMAND_POST = 21
    COLOR_CORRECTION_ENABLED = 22
    SQUAD_SIZE = 23
    SUN_FLARE_ENABLED = 24
    DISABLE_PRE_ROUND = 25
    CORPSE_DAMAGE_ENABLED = 26
    ORDINARY_MAPGROUPS = 27
    ORDINARY_MAPS = 30
    MODS_VOTEMAP_ENABLED = 31
    MODS_VOTEMAP_URL = 32
    ROUND_TIME = 33
    TICKET_COUNT_MODIFIER = 34
    MAPVOTE_RANDOMIZE = 35
    MAPVOTE_LIMIT = 36
    MAPVOTE_EXCLUDE_CURRENT_MAP = 37
    BOTS_IGNORE_PERMISSIONS = 38


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
