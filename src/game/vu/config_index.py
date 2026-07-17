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
    SERVER_KEY = 5
    RUN_COMMAND_EDIT = 6
    SERVER_UPDATE_FREQUENCY = 7
    LISTEN_HOST = 8
    LISTEN_PORT_FROSTBITE = 9
    LISTEN_PORT_HARMONY = 10
    LISTEN_PORT_RCON = 11
    RCON_ENABLE = 12
    SERVER_NAME = 13
    SERVER_PASSWORD = 14
    FRIENDLY_FIRE = 15
    DOWNLOAD_URL = 16


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
