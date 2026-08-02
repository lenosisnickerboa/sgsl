from __future__ import annotations

import copy
from dataclasses import dataclass

from config.config_item import ConfigItem
from config.toml_config import Config, IndexT


@dataclass
class ConfigItemUpgrade:
    """One config index's default as it used to be (`old`) and as it
    is now (`new`) — used by a ConfigUpgrader to detect whether a
    loaded config's current value at `index` was simply left at the
    old default (in which case it's carried forward to the new
    default) or was deliberately changed by the user away from it (in
    which case it's left exactly as the user set it — a config
    upgrade should never overwrite an intentional customization, only
    move a never-touched item's default forward)."""

    index: IndexT
    old: ConfigItem
    new: ConfigItem


@dataclass
class ConfigUpgrader:
    """One version's worth of config migrations, applied to an
    already-loaded Config[IndexT] — see apply_upgraders().

    `version` is the version these changes were introduced in —
    compared against a config's previously stored version (see
    TomlConfigParser.read_version()) to decide whether this
    upgrader's changes still need applying, so each one only ever
    takes effect once per saved file.

    `upgrades` replaces the item at each ConfigItemUpgrade's index
    with a fresh copy of its `new` ConfigItem, but only if that index
    is still present in the config AND its current value still equals
    ConfigItemUpgrade.old.value (see ConfigItemUpgrade) -- a value the
    user has since changed to anything else, including back to what
    used to be the default, is left untouched.

    `removed_indexes` are indexes that no longer exist at all as of
    this version (e.g. a retired config item) and are dropped from
    the config outright."""

    version: int
    upgrades: list[ConfigItemUpgrade]
    removed_indexes: list[IndexT]


def apply_upgraders(
    config: Config[IndexT],
    stored_version: int,
    upgraders: list[ConfigUpgrader],
) -> Config[IndexT]:
    """Apply every upgrader in `upgraders` whose version is newer than
    `stored_version` (the version the loaded file was actually last
    saved at — see TomlConfigParser.read_version()), oldest first, so
    a file several versions behind catches up through each step in
    order. Each upgrader removes its own removed_indexes from
    `config` and, for each of its upgrades whose index is present and
    still holds its old default value, replaces it with a fresh copy
    of that upgrade's `new` ConfigItem (see ConfigItemUpgrade) --
    leaving anything the user has deliberately customized alone.
    Mutates and returns `config`.

    An upgrader whose version is at or below `stored_version` is
    skipped entirely — its changes were already applied (and saved)
    on a previous run, so reapplying them would stomp on any edits
    the user has made since."""
    for upgrader in sorted(upgraders, key=lambda u: u.version):
        if stored_version >= upgrader.version:
            continue
        for index in upgrader.removed_indexes:
            config.pop(index, None)
        for upgrade in upgrader.upgrades:
            item = config.get(upgrade.index)
            if item is not None and item.value == upgrade.old.value:
                config[upgrade.index] = copy.deepcopy(upgrade.new)
    return config
