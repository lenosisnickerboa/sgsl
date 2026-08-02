from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Iterable, Optional, TypeVar, Union

import tomli_w

from config.config_item import ConfigItem, ConfigType

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

    A read_only item (e.g. one a Game recomputes fresh on every
    config_defaults() call, like a list of maps detected from disk) is
    never written to the file and, symmetrically, any stored value for
    one is ignored on read — it always reflects whatever config_defaults()
    just computed for it, not a stale or hand-edited value left over
    from before.

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
            try:
                raw = tomllib.load(f)
            except tomllib.TOMLDecodeError:
                # Corrupt/unparseable file (e.g. hand-edited, or left
                # over from a version that could write invalid TOML) --
                # same "don't fail the whole load" philosophy as an
                # unknown key or a value that no longer validates
                # below, just for the file as a whole instead of one
                # entry: fall back to defaults rather than crash.
                return config

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
            if item.read_only:
                # Never loaded from file -- always whatever
                # config_defaults() just computed for it (see class
                # docstring). A stray entry here is most likely left
                # over from before the item became read_only.
                continue
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
        # read_only items aren't stored at all (see class docstring) —
        # config_defaults() recomputes them fresh every run, so a
        # written copy would just be redundant at best and stale at
        # worst.
        ordered_items = [
            (idx, item) for idx, item in ordered_items if not item.read_only
        ]

        # Each item is dumped independently (see _format_entry) and the
        # resulting blocks are just concatenated as text, rather than
        # dumped from one combined dict via a single tomli_w.dumps()
        # call -- which is what makes this reordering necessary: a
        # dict-shaped value (TABLE/STRUCT) always renders as a "[name]"
        # table header, and a list-of-dicts value (STRUCT_MAP, ARRAY-
        # of-TABLE-likes, ...) renders as a "[[name]]" array-of-tables
        # header instead of an inline literal whenever an entry doesn't
        # fit inline on one line (e.g. a STRUCT_MAP entry whose value
        # is itself a STRUCT_LIST, or just has enough fields) -- and in
        # TOML every bare "key = value" line belongs to whichever
        # header most recently appeared above it. Left in index order,
        # a plain item written after one of these would silently become
        # a field of that header's table instead of its own top-level
        # key. Detected empirically (does the rendered block open a
        # header?) rather than by ConfigType, since whether tomli_w
        # reaches for header syntax depends on the actual value's shape,
        # not just the declared type -- e.g. the same STRUCT_MAP can
        # render either way depending on what's currently in it. Moving
        # every such block to the end (each still its own header, so
        # none of them capture each other) avoids the problem regardless
        # of how the items are indexed or what they currently contain.
        blocks = [TomlConfigParser._format_entry(item) for _, item in ordered_items]
        header_blocks = [b for b in blocks if TomlConfigParser._opens_table_header(b)]
        plain_blocks = [
            b for b in blocks if not TomlConfigParser._opens_table_header(b)
        ]

        path.write_text("\n".join(plain_blocks + header_blocks), encoding="utf-8")

    @staticmethod
    def _opens_table_header(block: str) -> bool:
        """True if `block` (one item's rendered comment+value text)
        contains a TOML table/array-of-tables header line ("[name]" or
        "[[name]]") -- which, unlike a plain "key = value" line, stays
        open and would swallow any bare assignment written after it.
        Comment lines (from _format_entry) always start with "#", so
        they can't false-positive here."""
        return any(line.startswith("[") for line in block.splitlines())

    @staticmethod
    def _format_entry(item: ConfigItem) -> str:
        """Render one ConfigItem as a `key = value` line preceded by
        comment lines describing it (visible name, type, tooltip, and
        any constraints), so the TOML file is self-documenting enough
        to hand-edit without cross-referencing the source."""
        comment_lines = [f"# {item.visible_name} ({item.type.name})"]
        if item.tooltip:
            # A multi-line tooltip (e.g. one with a "Default: ..."/
            # "Range: ..." line appended) needs every line commented
            # out individually -- a single "# " prefix on the whole
            # string only comments out its first line, leaving the
            # rest as bare, invalid TOML.
            for tooltip_line in item.tooltip.splitlines():
                comment_lines.append(f"# {tooltip_line}")
        if item.allowed_values is not None:
            values = ", ".join(str(v) for v in item.allowed_values)
            comment_lines.append(f"# Allowed values: {values}")
        if item.range is not None:
            comment_lines.append(f"# Range: {item.range.describe()}")
        if item.max_length is not None:
            comment_lines.append(f"# Max length: {item.max_length}")

        # Let tomli_w handle the actual TOML value formatting/escaping
        # (quoting, floats, nested arrays/tables, ...) rather than
        # reimplementing it here — only the surrounding comments are
        # hand-rolled.
        value_line = tomli_w.dumps({item.name: item.value}).rstrip("\n")

        return "\n".join(comment_lines) + "\n" + value_line + "\n\n"


def reset_to_defaults(
    config: Config[IndexT],
    defaults: Config[IndexT],
    keep_masked: bool = False,
    indexes: Optional[Iterable[IndexT]] = None,
) -> list[IndexT]:
    """Reset every non-read_only item in `config` to its value in
    `defaults`, in place (so already-registered UI widgets/game state
    referencing this exact dict keep working) -- except MASKED_STRING
    items (passwords/keys) when `keep_masked` is True, which are left
    untouched. read_only items are skipped, the same as
    TomlConfigParser: they're always recomputed fresh (e.g. a detected
    maps list), not something a "reset" should touch.

    `indexes`, if given, restricts the reset to just those indexes
    (e.g. one config tab's own items) instead of every index in
    `config` -- used by a per-tab "Set defaults..." button so resetting
    one tab doesn't touch items shown on another.

    Returns the list of indexes actually changed, so the caller can
    refresh their widgets and react the same way a live edit would
    (see Game.config_item_changed())."""
    changed = []
    for index in config.keys() if indexes is None else indexes:
        item = config.get(index)
        if item is None or item.read_only:
            continue
        if keep_masked and item.type is ConfigType.MASKED_STRING:
            continue
        default_item = defaults.get(index)
        if default_item is None or item.value == default_item.value:
            continue
        try:
            item.set(default_item.value)
        except (TypeError, ValueError):
            # Shouldn't normally happen (the default came from this
            # same item's own schema), but don't let one bad item
            # abort the whole reset.
            continue
        changed.append(index)
    return changed
