from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import TypeVar, Union

import tomli_w

from config.config_item import ConfigItem

# The index type just needs to behave like an int (any IntEnum works,
# and so would a plain int) — this module never imports or assumes a
# specific ConfigIndex enum, so different config groups (e.g. an
# application config and a per-game config) can each define their own
# IntEnum with its own numeric range, and both work with this parser.
IndexT = TypeVar("IndexT", bound=int)

Config = dict[IndexT, ConfigItem]


class TomlConfigParser:
    """Reads and writes Config dicts (some int-like index -> ConfigItem)
    to/from TOML files.

    Reading takes a `defaults` Config: every entry present in the TOML
    file overrides the matching default's value (validated against that
    default's declared type/item_type/schema); anything absent from the
    file falls back to the default untouched. This means the returned
    Config always has an entry for every index present in `defaults`,
    even if the TOML file is empty, partial, or missing.

    An entry that no longer validates against its default (e.g. a
    saved file from before that item's declared type or constraints
    changed) is treated like an unknown key: it's skipped and the
    default value is kept, rather than failing the whole load.

    This class is agnostic to which specific index enum you use — it
    only ever treats index values as opaque dict keys and, when
    ordering for output, as plain integers via int(idx). Different
    config groups (e.g. AppConfigIndex vs Cs2ConfigIndex) can each use
    their own enum/range without this module needing to know about
    either.
    """

    @staticmethod
    def read(path: Union[str, Path], defaults: Config[IndexT]) -> Config[IndexT]:
        path = Path(path)

        # Start from a deep copy of the defaults so we never mutate the
        # caller's default objects.
        config: Config[IndexT] = copy.deepcopy(defaults)

        if not path.exists():
            return config

        with path.open("rb") as f:
            raw = tomllib.load(f)

        # Map TOML key (ConfigItem.name) -> index, so we can find which
        # default each TOML entry corresponds to.
        name_to_index = {item.name: idx for idx, item in defaults.items()}

        for toml_key, toml_value in raw.items():
            idx = name_to_index.get(toml_key)
            if idx is None:
                # Unknown key in the file (e.g. from a future version,
                # or a typo) — ignore it rather than fail the whole load.
                continue

            item = config[idx]
            try:
                # set() re-validates against the item's declared type,
                # item_type (ARRAY), or schema (TABLE).
                item.set(toml_value)
            except (TypeError, ValueError):
                # Stale value from before this item's type/constraints
                # changed — keep the default rather than fail the load.
                continue

        return config

    @staticmethod
    def write(path: Union[str, Path], config: Config[IndexT]) -> None:
        path = Path(path)

        # Order by the index's integer value for a stable, deterministic
        # file. int(idx) works whether idx is an IntEnum member or a
        # plain int, without relying on a .value attribute.
        ordered_items = sorted(config.items(), key=lambda pair: int(pair[0]))

        data = {item.name: item.value for _, item in ordered_items}

        with path.open("wb") as f:
            tomli_w.dump(data, f)