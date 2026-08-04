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

    # -- Network --
    HOSTNAME = 5
    SV_LAN = 6
    SV_PASSWORD = 7
    SV_VISIBLEMAXPLAYERS = 8

    # -- Bots --
    BOT_DIFFICULTY = 9
    BOT_QUOTA = 10
    BOT_QUOTA_MODE = 11
    BOT_CHATTER = 12
    BOT_WALK = 13
    BOT_JOIN_AFTER_PLAYER = 14
    BOT_ALL_WEAPONS = 15

    # -- Match / round rules --
    MP_ROUNDTIME = 16
    MP_FREEZETIME = 17
    MP_BUYTIME = 18
    MP_MAXROUNDS = 19
    MP_HALFTIME = 20
    MP_OVERTIME_ENABLE = 21
    MP_OVERTIME_MAXROUNDS = 22
    MP_STARTMONEY = 23
    MP_MAXMONEY = 24
    MP_FRIENDLYFIRE = 25
    MP_AUTO_TEAM_BALANCE = 26
    MP_LIMIT_TEAMS = 27
    MP_WARMUP_TIME = 28
    MP_WARMUP_PAUSETIMER = 29
    MP_RESPAWN_ON_DEATH_CT = 30
    MP_RESPAWN_ON_DEATH_T = 31

    # -- Economy / weapons --
    MP_FREE_ARMOR = 32
    MP_AFTERROUNDMONEY = 33
    MP_DEATH_DROP_GUN = 34
    MP_DEATH_DROP_GRENADE = 35

    # -- Voice / comms --
    SV_VOICEENABLE = 36
    SV_ALLTALK = 37
    SV_DEADTALK = 38

    # -- Cheats / security --
    SV_CHEATS = 39

    # -- Maps --
    ORDINARY_MAPS = 40
    WORKSHOP_MAPS = 41
    WORKSHOP_MAPS_HELP_TEXT = 65

    # -- Steam --
    STEAM_API_AUTH_KEY = 42
    STEAM_GSLT = 43
    STEAM_HELP_TEXT = 64

    RUN_COMMAND_EDIT = 44

    # -- Troubleshooting --
    REMOVE_MANIFEST_FILE = 45
    UPDATE_STEAMCMD = 46

    CUSTOM_RUN_COMMAND_PRE = 47
    CUSTOM_RUN_COMMAND_POST = 48

    ORDINARY_MAPGROUPS = 50
    WORKSHOP_MAPGROUPS = 51

    # -- Server / network --
    SERVER_FREQUENCY = 52
    LISTEN_ADDRESS = 53
    LISTEN_PORT = 54
    RCON_ENABLE = 55
    RCON_PASSWORD = 56
    CONSOLE_ENABLED = 57

    # -- Map vote --
    MAPVOTE_ENDMATCH_ENABLE = 58
    MAPVOTE_ENDMATCH_DURATION = 59
    MAPVOTE_ALLOW_VOTES = 60
    MAPVOTE_MATCH_RESTART_DELAY = 61

    MP_WARMUPTIME_ALL_PLAYERS_CONNECTED = 62

    MP_RESPAWN_IMMUNITYTIME = 66
    MP_BUY_DURING_IMMUNITY = 67
    MP_ROUND_RESTART_DELAY = 68
    MP_TEAM_INTRO_TIME = 69

    MP_ROUNDTIME_DEFUSE = 70
    MP_ROUNDTIME_HOSTAGE = 71

    MP_BUY_ANYWHERE = 72
    MP_BUY_ALLOW_GUNS = 73
    MP_BUY_ALLOW_GRENADES = 74


_values = [item.value for item in ConfigIndex]
assert len(_values) == len(set(_values)), "Duplicate ConfigIndex values!"
