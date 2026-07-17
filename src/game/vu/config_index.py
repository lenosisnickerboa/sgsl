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
    LISTEN_HOST = 7
    LISTEN_PORT_FROSTBITE = 8
    LISTEN_PORT_HARMONY = 9
    LISTEN_PORT_RCON = 10
    RCON_ENABLE = 11
    SERVER_NAME = 12
    SERVER_PASSWORD = 13
    FRIENDLY_FIRE = 14
    DOWNLOAD_URL = 15


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
