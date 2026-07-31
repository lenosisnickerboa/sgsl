from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Callable, Optional, Union


class ConfigType(Enum):
    """Maps to the value types TOML supports."""

    STRING = str
    # A single string chosen from ConfigItem.allowed_values (e.g. for a
    # dropdown). Serialized the same as STRING (a plain TOML string);
    # given a distinct sentinel value (rather than `str`) purely so it
    # doesn't alias STRING as an Enum member — see _check_scalar().
    STRING_LIST = "string_list"
    # A string whose value a UI should mask (e.g. show as asterisks)
    # rather than display in the clear, such as a password. Serialized
    # the same as STRING; given a distinct sentinel value for the same
    # reason as STRING_LIST — see _check_scalar().
    MASKED_STRING = "masked_string"
    INTEGER = int
    FLOAT = float
    BOOLEAN = bool
    DATETIME = datetime
    DATE = date
    TIME = time
    ARRAY = list
    TABLE = dict
    # A fixed set of named fields, each holding a scalar ConfigType
    # (declared via `schema`, the same attribute TABLE uses) — e.g.
    # {"host": ConfigType.STRING, "port": ConfigType.INTEGER}.
    # Validated identically to TABLE; kept as a separate type so it
    # reads as "a struct" where it's used standalone or as the payload
    # of a STRUCT_MAP entry. Given a distinct sentinel value for the
    # same reason as STRING_LIST — see _check_scalar().
    STRUCT = "struct"
    # A list mapping a scalar key (`item_type`, restricted to STRING
    # or INTEGER) to a STRUCT (`schema` describes the struct's
    # fields). The value is a list of {"key": ..., "value": {...}}
    # entries with unique keys — see add_struct_map_entry(),
    # remove_struct_map_entry(), and set_struct_map_entry(). Given a
    # distinct sentinel value for the same reason as STRING_LIST —
    # see _check_scalar().
    STRUCT_MAP = "struct_map"
    # A plain list of STRUCTs, all sharing the same fields (declared
    # via `schema`, same as STRUCT) — unlike STRUCT_MAP, entries have
    # no key, just position in the list. Given a distinct sentinel
    # value for the same reason as STRING_LIST — see _check_scalar().
    STRUCT_LIST = "struct_list"


class ConfigDeliveryType(Enum):
    """How a config item's value should reach the running game
    server."""

    # Passed as a command-line argument/option when launching the
    # server process.
    COMMAND_LINE = "command_line"
    # Written into a server-side .cfg file the game reads on startup.
    SERVER_CFG_FILE = "server_cfg_file"


@dataclass(frozen=True)
class Range:
    """An inclusive min/max bound for a numeric ConfigItem. Either
    bound may be omitted (None) to leave that side unconstrained."""

    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None

    def __post_init__(self) -> None:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError(
                f"min_value ({self.min_value}) > max_value ({self.max_value})"
            )

    def describe(self) -> str:
        """Human-readable "min X, max Y" bounds (only whichever
        side(s) are actually set), for UI text like tooltips or the
        TOML file's generated comments -- shared so every caller
        renders a Range the same way."""
        bounds = []
        if self.min_value is not None:
            bounds.append(f"min {self.min_value}")
        if self.max_value is not None:
            bounds.append(f"max {self.max_value}")
        return ", ".join(bounds)


@dataclass
class SchemaField:
    """One field of a TABLE/STRUCT/STRUCT_LIST/STRUCT_MAP `schema`.
    Usually a bare ConfigType is enough (e.g. schema={"x":
    ConfigType.INTEGER}); wrap it in a SchemaField instead when a
    STRING_LIST field's set of valid choices should be taken from
    another ConfigItem's `allowed_values` rather than a fixed list —
    e.g. a struct field for a map name that should always offer
    whatever's currently in some other "list of maps" item. This holds
    a live reference to that ConfigItem (not a snapshot of its
    allowed_values), so it stays correct even if that item's
    allowed_values is populated or changed after this SchemaField is
    created — see _validate_struct_fields().

    `allowed_values_from` only applies to STRING_LIST fields; setting
    it on any other type raises ValueError immediately."""

    type: ConfigType
    allowed_values_from: Optional["ConfigItem"] = None

    def __post_init__(self) -> None:
        if (
            self.allowed_values_from is not None
            and self.type is not ConfigType.STRING_LIST
        ):
            raise ValueError(
                "SchemaField: allowed_values_from only applies to STRING_LIST fields"
            )


def _resolve_schema_field(field: Union[ConfigType, SchemaField]) -> SchemaField:
    """Normalize one schema dict entry -- a bare ConfigType (the common
    case) or an explicit SchemaField -- into a SchemaField."""
    return field if isinstance(field, SchemaField) else SchemaField(type=field)


def _check_scalar(name: str, value: Any, expected_type: ConfigType) -> None:
    """Validate a single scalar value against a ConfigType, with the
    bool/int special case handled explicitly."""

    py_type = (
        str
        if expected_type in (ConfigType.STRING_LIST, ConfigType.MASKED_STRING)
        else expected_type.value
    )

    if expected_type is ConfigType.INTEGER and isinstance(value, bool):
        raise TypeError(f"{name}: expected int, got bool")
    if expected_type is ConfigType.BOOLEAN and not isinstance(value, bool):
        raise TypeError(f"{name}: expected bool, got {type(value).__name__}")

    if not isinstance(value, py_type):
        raise TypeError(
            f"{name}: expected {expected_type.name} ({py_type.__name__}), "
            f"got {type(value).__name__}"
        )


@dataclass
class ConfigItem:
    """A single config entry: a name, a human-readable label, a TOML-
    compatible type, and a value that must match that type.

    For ARRAY items, `item_type` declares the ConfigType every element
    must match (e.g. ConfigType.INTEGER for a list of ints).

    For TABLE and STRUCT items, `schema` declares the expected keys
    and their ConfigType, e.g. {"x": ConfigType.INTEGER, "y":
    ConfigType.INTEGER}. The table's/struct's keys must match the
    schema's keys exactly. STRUCT is validated identically to TABLE;
    it exists as a separate type so it reads as "a struct" where it's
    used standalone or as the payload of a STRUCT_MAP entry. A schema
    value can also be a SchemaField instead of a bare ConfigType —
    see its docstring — to associate a STRING_LIST field with another
    ConfigItem's allowed_values.

    For STRUCT_MAP items, `item_type` declares the ConfigType of the
    map's key (must be ConfigType.STRING or ConfigType.INTEGER) and
    `schema` declares the fields of the STRUCT each key maps to, the
    same as for a STRUCT item. The value is a list of entries shaped
    like {"key": <key value>, "value": <the STRUCT>}, with keys unique
    across the list — this shape (rather than a plain dict) is what
    lets the key be an int, since TOML/JSON table keys must be
    strings. Use add_struct_map_entry()/remove_struct_map_entry()/
    set_struct_map_entry() to mutate a STRUCT_MAP item rather than
    building entry dicts by hand.

    `value_type`, only valid for STRUCT_MAP items, picks the shape of
    each entry's "value": ConfigType.STRUCT (the default — one STRUCT
    per key, validated against `schema`) or ConfigType.STRUCT_LIST (a
    whole list of STRUCTs per key, e.g. a named group of several
    entries, each still validated against `schema`).

    `key_name`, only valid for STRUCT_MAP items, is the human-readable
    name a UI should show for the map's key (e.g. "map_group") instead
    of the generic "key" — purely cosmetic, it has no effect on the
    entry dict's actual "key"/"value" field names or on serialization.
    Defaults to "key" if unset.

    For STRUCT_LIST items, `schema` declares the fields of the STRUCT
    every element must match, the same as for a STRUCT item. The
    value is a plain list of struct dicts — unlike STRUCT_MAP, there's
    no key, so use ordinary list operations on `.value` (plus `set()`
    to have the result re-validated) rather than a dedicated mutation
    API.

    `validator`, if provided, is an additional check run after the
    built-in type/item_type/schema validation passes. It's called with
    the candidate value as its only argument (the same value/element
    passed to `set()` or the constructor) and must return True if the
    value is acceptable, or False to reject it. It may also raise its
    own exception (e.g. ValueError) instead of returning False, if it
    wants to report a more specific reason.

    `transform`, if provided, is called with a candidate value before
    validation and its return value is used as the actual value to
    store — e.g. to normalize user input into a canonical form. For an
    ARRAY item it's applied to each element individually rather than
    the list as a whole. It may raise (e.g. ValueError) to reject a
    value outright, the same as `validator`.

    `allowed_values`, if provided, is the closed set of values this
    item is allowed to hold (e.g. ["low", "medium", "high"] for a
    STRING item, or [0, 1, 2] for an INTEGER item). If set, the current
    value is checked for membership as part of validation, and it's
    also exposed via `values()` — e.g. for a UI to populate a dropdown.

    `range`, only valid for INTEGER and FLOAT items, is a Range whose
    min_value/max_value declare an inclusive bound the value must fall
    within (either or both may be given). Setting it on a non-numeric
    item raises ValueError immediately.

    `max_length`, only valid for STRING items, caps the length of the
    string value. Setting it on a non-STRING item raises ValueError
    immediately.

    `tooltip`, if provided, is shown by a UI in place of `visible_name`
    when hovering over this item's widget. If unset, a UI should fall
    back to `visible_name`.

    `config_type`, if provided, tells a Game how to deliver this
    item's value to the server process — as a COMMAND_LINE argument or
    written into a SERVER_CFG_FILE. Left unset for config items that
    aren't fed to a game server at all (e.g. app-level settings).

    `read_only`, if True, tells a UI to build this item's widget so it
    only displays the current value, with no way to edit it (e.g. a
    list that's derived from another item and shouldn't be hand-edited).
    """

    name: str
    visible_name: str
    type: ConfigType
    value: Any
    config_type: Optional[ConfigDeliveryType] = None
    item_type: Optional[ConfigType] = None
    schema: Optional[dict[str, Union[ConfigType, SchemaField]]] = None
    value_type: Optional[ConfigType] = None
    key_name: Optional[str] = None
    validator: Optional[Callable[[Any], bool]] = None
    transform: Optional[Callable[[Any], Any]] = None
    allowed_values: Optional[list[Any]] = None
    range: Optional[Range] = None
    max_length: Optional[int] = None
    tooltip: Optional[str] = None
    read_only: bool = False

    def __post_init__(self) -> None:
        if self.type is ConfigType.ARRAY and self.item_type is None:
            raise ValueError(f"{self.name}: ARRAY items require item_type")
        if self.type is ConfigType.TABLE and self.schema is None:
            raise ValueError(f"{self.name}: TABLE items require schema")
        if self.type is ConfigType.STRUCT and self.schema is None:
            raise ValueError(f"{self.name}: STRUCT items require schema")
        if self.type is ConfigType.STRUCT_LIST and self.schema is None:
            raise ValueError(f"{self.name}: STRUCT_LIST items require schema")
        if self.type is ConfigType.STRUCT_MAP:
            if self.schema is None:
                raise ValueError(
                    f"{self.name}: STRUCT_MAP items require schema (the struct's fields)"
                )
            if self.item_type not in (ConfigType.STRING, ConfigType.INTEGER):
                raise ValueError(
                    f"{self.name}: STRUCT_MAP items require item_type of STRING or "
                    "INTEGER (the map's key type)"
                )
            if self.value_type is None:
                self.value_type = ConfigType.STRUCT
            elif self.value_type not in (ConfigType.STRUCT, ConfigType.STRUCT_LIST):
                raise ValueError(
                    f"{self.name}: STRUCT_MAP value_type must be STRUCT or STRUCT_LIST"
                )
            if self.key_name is None:
                self.key_name = "key"
        elif self.value_type is not None:
            raise ValueError(f"{self.name}: value_type only applies to STRUCT_MAP items")
        elif self.key_name is not None:
            raise ValueError(f"{self.name}: key_name only applies to STRUCT_MAP items")
        if self.range is not None and self.type not in (
            ConfigType.INTEGER,
            ConfigType.FLOAT,
        ):
            raise ValueError(
                f"{self.name}: range only applies to INTEGER or FLOAT items"
            )
        if self.max_length is not None and self.type is not ConfigType.STRING:
            raise ValueError(f"{self.name}: max_length only applies to STRING items")
        if self.transform is not None:
            self.value = self._apply_transform(self.value)
        self._validate()

    def _validate(self) -> None:
        if self.type is ConfigType.ARRAY:
            self._validate_array()
        elif self.type in (ConfigType.TABLE, ConfigType.STRUCT):
            self._validate_table()
        elif self.type is ConfigType.STRUCT_MAP:
            self._validate_struct_map()
        elif self.type is ConfigType.STRUCT_LIST:
            self._validate_struct_list()
        else:
            _check_scalar(self.name, self.value, self.type)

        if (
            self.type in (ConfigType.INTEGER, ConfigType.FLOAT)
            and self.range is not None
        ):
            if self.range.min_value is not None and self.value < self.range.min_value:
                raise ValueError(
                    f"{self.name}: value {self.value!r} is below min_value {self.range.min_value!r}"
                )
            if self.range.max_value is not None and self.value > self.range.max_value:
                raise ValueError(
                    f"{self.name}: value {self.value!r} is above max_value {self.range.max_value!r}"
                )

        if (
            self.type is ConfigType.STRING
            and self.max_length is not None
            and len(self.value) > self.max_length
        ):
            raise ValueError(
                f"{self.name}: value {self.value!r} exceeds max_length {self.max_length}"
            )

        if self.allowed_values is not None:
            if self.type is ConfigType.ARRAY:
                # allowed_values constrains each element of the list,
                # not the list itself -- the list as a whole could
                # never be "in" a list of individual valid elements.
                invalid = [v for v in self.value if v not in self.allowed_values]
                if invalid:
                    raise ValueError(
                        f"{self.name}: value(s) {invalid!r} not in allowed_values "
                        f"{self.allowed_values!r}"
                    )
            elif self.value not in self.allowed_values:
                raise ValueError(
                    f"{self.name}: value {self.value!r} not in allowed_values "
                    f"{self.allowed_values!r}"
                )

        if self.validator is not None:
            self._run_validator(self.value)

    def _run_validator(self, value: Any) -> None:
        try:
            ok = self.validator(value)
        except Exception as e:
            raise ValueError(f"{self.name}: validator raised an error: {e}") from e

        if not ok:
            raise ValueError(f"{self.name}: rejected by validator (value={value!r})")

    def _validate_array(self) -> None:
        if not isinstance(self.value, list):
            raise TypeError(
                f"{self.name}: expected ARRAY (list), got {type(self.value).__name__}"
            )
        for i, element in enumerate(self.value):
            try:
                _check_scalar(self.name, element, self.item_type)
            except TypeError as e:
                raise TypeError(f"{self.name}[{i}]: {e}") from e

    def _validate_table(self) -> None:
        self._validate_struct_fields(self.name, self.value, self.schema)

    def _validate_struct_fields(
        self, context: str, value: Any, schema: dict[str, Union[ConfigType, SchemaField]]
    ) -> None:
        """Shared by TABLE/STRUCT (validating self.value against
        self.schema) and STRUCT_MAP (validating each entry's "value"
        against self.schema) — `context` is the name to prefix errors
        with, since STRUCT_MAP needs a per-entry context rather than
        just self.name."""
        if not isinstance(value, dict):
            raise TypeError(
                f"{context}: expected {self.type.name} (dict), got {type(value).__name__}"
            )

        expected_keys = set(schema.keys())
        actual_keys = set(value.keys())
        if expected_keys != actual_keys:
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            details = []
            if missing:
                details.append(f"missing {sorted(missing)}")
            if extra:
                details.append(f"unexpected {sorted(extra)}")
            raise TypeError(f"{context}: keys mismatch ({', '.join(details)})")

        for key, raw_field in schema.items():
            field = _resolve_schema_field(raw_field)
            try:
                _check_scalar(context, value[key], field.type)
            except TypeError as e:
                raise TypeError(f"{context}.{key}: {e}") from e

            if field.allowed_values_from is not None:
                candidates = field.allowed_values_from.allowed_values
                # None means "not populated (yet)" — same convention as
                # ConfigItem's own allowed_values: unset means
                # unconstrained rather than "nothing is allowed".
                if candidates is not None and value[key] not in candidates:
                    raise ValueError(
                        f"{context}.{key}: value {value[key]!r} not in "
                        f"{field.allowed_values_from.name}'s allowed_values "
                        f"{candidates!r}"
                    )

    def _validate_struct_map(self) -> None:
        if not isinstance(self.value, list):
            raise TypeError(
                f"{self.name}: expected STRUCT_MAP (list), got {type(self.value).__name__}"
            )

        seen_keys = []
        for i, entry in enumerate(self.value):
            if not isinstance(entry, dict) or set(entry.keys()) != {"key", "value"}:
                raise TypeError(
                    f"{self.name}[{i}]: expected a dict with exactly 'key' and "
                    f"'value' entries, got {entry!r}"
                )

            try:
                _check_scalar(f"{self.name}[{i}].key", entry["key"], self.item_type)
            except TypeError as e:
                raise TypeError(str(e)) from e

            if entry["key"] in seen_keys:
                raise ValueError(
                    f"{self.name}: duplicate key {entry['key']!r} in STRUCT_MAP"
                )
            seen_keys.append(entry["key"])

            if self.value_type is ConfigType.STRUCT_LIST:
                self._validate_struct_list_fields(
                    f"{self.name}[{i}].value", entry["value"], self.schema
                )
            else:
                self._validate_struct_fields(
                    f"{self.name}[{i}].value", entry["value"], self.schema
                )

    def _validate_struct_list(self) -> None:
        self._validate_struct_list_fields(self.name, self.value, self.schema)

    def _validate_struct_list_fields(
        self, context: str, value: Any, schema: dict[str, Union[ConfigType, SchemaField]]
    ) -> None:
        """Shared by STRUCT_LIST (validating self.value against
        self.schema) and a STRUCT_MAP whose value_type is STRUCT_LIST
        (validating each entry's "value" against self.schema) — same
        context-prefixing reasoning as _validate_struct_fields()."""
        if not isinstance(value, list):
            raise TypeError(
                f"{context}: expected STRUCT_LIST (list), got {type(value).__name__}"
            )
        for i, element in enumerate(value):
            self._validate_struct_fields(f"{context}[{i}]", element, schema)

    def set(self, value: Any) -> None:
        """Update the value, re-validating against the declared type,
        item_type/schema, and validator (after first running it through
        `transform`, if set). If transforming or validation fails, the
        item is left unchanged (the old value is restored) rather than
        being left holding an invalid value."""
        previous = self.value
        try:
            if self.transform is not None:
                value = self._apply_transform(value)
            self.value = value
            self._validate()
        except Exception:
            self.value = previous
            raise

    def _apply_transform(self, value: Any) -> Any:
        if self.type in (ConfigType.ARRAY, ConfigType.STRUCT_LIST):
            return [self.transform(element) for element in value]
        return self.transform(value)

    def _require_struct_map(self, method_name: str) -> None:
        if self.type is not ConfigType.STRUCT_MAP:
            raise TypeError(
                f"{self.name}: {method_name} only applies to STRUCT_MAP items "
                f"(this item is {self.type.name})"
            )

    def add_struct_map_entry(self, key: Any, struct_value: Any) -> None:
        """Add a new key -> value entry (`struct_value` is a dict if
        this item's value_type is STRUCT, or a list of dicts if it's
        STRUCT_LIST). Goes through set() so the result is validated
        (and the item left unchanged if it isn't) the same way a plain
        set() call is.

        Raises ValueError if `key` already exists — use
        set_struct_map_entry() to modify an existing entry instead."""
        self._require_struct_map("add_struct_map_entry")
        if any(entry["key"] == key for entry in self.value):
            raise ValueError(f"{self.name}: key {key!r} already exists")
        self.set(self.value + [{"key": key, "value": struct_value}])

    def remove_struct_map_entry(self, key: Any) -> None:
        """Remove the entry for `key`. Raises KeyError if `key` isn't
        present."""
        self._require_struct_map("remove_struct_map_entry")
        if not any(entry["key"] == key for entry in self.value):
            raise KeyError(f"{self.name}: key {key!r} not found")
        self.set([entry for entry in self.value if entry["key"] != key])

    def set_struct_map_entry(self, key: Any, struct_value: Any) -> None:
        """Replace the value stored for an existing `key` (a dict or a
        list of dicts — see add_struct_map_entry()). Raises KeyError
        if `key` isn't present — use add_struct_map_entry() to create
        a new entry instead."""
        self._require_struct_map("set_struct_map_entry")
        if not any(entry["key"] == key for entry in self.value):
            raise KeyError(f"{self.name}: key {key!r} not found")
        self.set(
            [
                {"key": key, "value": struct_value} if entry["key"] == key else entry
                for entry in self.value
            ]
        )

    def values(self) -> Optional[list[Any]]:
        """Return the possible values for this item, or None if it's
        unconstrained (any value matching the declared type is fine)."""
        return self.allowed_values

    def __repr__(self) -> str:
        return (
            f"ConfigItem(name={self.name!r}, visible_name={self.visible_name!r}, "
            f"type={self.type.name}, value={self.value!r})"
        )
