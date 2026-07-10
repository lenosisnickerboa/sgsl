from enum import IntEnum


class ConfigIndex(IntEnum):
    """Stable, permanent numeric IDs for config items.

    IMPORTANT: Never reuse or renumber existing values, even if an
    item is removed/deprecated. Only ever append new entries with
    new numbers. This keeps saved/serialized configs (files, network
    data, etc.) valid across versions.
    """

    SELECTED_MAP = 1
    SELECTED_MAP_GROUP = 2
    GAME_MODE = 3
    PLAYER_COUNT = 4
    # DEPRECATED_OLD_FIELD = 6   # <- if removed, leave a comment, don't reuse 6
    # LANGUAGE = 7

_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"