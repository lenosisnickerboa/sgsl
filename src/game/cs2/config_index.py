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

    # -- Network --
    HOSTNAME = 5
    SV_LAN = 6
    SV_PASSWORD = 7
    SV_VISIBLEMAXPLAYERS = 8
    # SV_REGION = 9   <- removed, don't reuse 9

    # -- Bots --
    BOT_DIFFICULTY = 10
    BOT_QUOTA = 11
    BOT_QUOTA_MODE = 12
    BOT_CHATTER = 13
    BOT_WALK = 14
    BOT_JOIN_AFTER_PLAYER = 15
    BOT_ALL_WEAPONS = 16
    BOT_AUTO_DIFFICULTY = 17

    # -- Match / round rules --
    MP_ROUNDTIME = 18
    MP_FREEZETIME = 19
    MP_BUYTIME = 20
    MP_MAXROUNDS = 21
    MP_HALFTIME = 22
    MP_OVERTIME_ENABLE = 23
    MP_OVERTIME_MAXROUNDS = 24
    MP_STARTMONEY = 25
    MP_MAXMONEY = 26
    MP_FRIENDLYFIRE = 27
    MP_AUTOTEAMBALANCE = 28
    MP_LIMITTEAMS = 29
    MP_WARMUPTIME = 30
    MP_WARMUP_PAUSETIMER = 31
    MP_RESPAWN_ON_DEATH_CT = 32
    MP_RESPAWN_ON_DEATH_T = 33

    # -- Economy / weapons --
    MP_FREE_ARMOR = 34
    MP_AFTERROUNDMONEY = 35
    MP_DEATH_DROP_GUN = 36
    MP_DEATH_DROP_GRENADE = 37

    # -- Voice / comms --
    SV_VOICEENABLE = 38
    SV_ALLTALK = 39
    SV_DEADTALK = 40

    # -- Cheats / security --
    SV_CHEATS = 41
    SV_PURE = 42
    SV_ALLOW_WAIT_COMMAND = 43

    # -- Performance / tickrate --
    SV_MAXUPDATERATE = 44
    SV_MINUPDATERATE = 45
    SV_MAXCMDRATE = 46
    SV_MINCMDRATE = 47

    # -- Maps --
    ORDINARY_MAPS = 48
    WORKSHOP_MAPS = 49


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
