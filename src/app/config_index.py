from enum import IntEnum


class ConfigIndex(IntEnum):
    """Stable, permanent numeric IDs for config items.

    IMPORTANT: Never reuse or renumber existing values, even if an
    item is removed/deprecated. Only ever append new entries with
    new numbers. This keeps saved/serialized configs (files, network
    data, etc.) valid across versions.
    """

    TERMINAL_ENABLED = 1


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
