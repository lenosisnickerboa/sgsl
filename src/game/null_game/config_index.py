from enum import IntEnum


class ConfigIndex(IntEnum):
    """Stable, permanent numeric IDs for config items.

    IMPORTANT: Never reuse or renumber existing values, even if an
    item is removed/deprecated. Only ever append new entries with
    new numbers. This keeps saved/serialized configs (files, network
    data, etc.) valid across versions.
    """

    GAME_MODE = (1,)
    SELECTED_MAP = 2
    PLAYER_COUNT = 3
    FRIENDLY_FIRE_ENABLED = 4
    DUMMY_0 = 5
    DUMMY_1 = 6
    DUMMY_2 = 7
    DUMMY_3 = 8
    DUMMY_4 = 9
    DUMMY_5 = 10
    DUMMY_6 = 11
    DUMMY_7 = 12
    DUMMY_8 = 13
    DUMMY_9 = 14
    PASSWORD = 15
    BOT_DIFFICULTY = 16
    AVAILABLE_MAPS = 17
    RUN_COMMAND_EDIT = 18


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
