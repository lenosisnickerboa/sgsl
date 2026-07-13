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
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError(f"min_value ({self.min_value}) > max_value ({self.max_value})")


def _check_scalar(name: str, value: Any, expected_type: ConfigType) -> None:
    """Validate a single scalar value against a ConfigType, with the
    bool/int special case handled explicitly."""

    py_type = str if expected_type in (ConfigType.STRING_LIST, ConfigType.MASKED_STRING) else expected_type.value

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

    For TABLE items, `schema` declares the expected keys and their
    ConfigType, e.g. {"x": ConfigType.INTEGER, "y": ConfigType.INTEGER}.
    The table's keys must match the schema's keys exactly.

    `validator`, if provided, is an additional check run after the
    built-in type/item_type/schema validation passes. It's called with
    the candidate value as its only argument (the same value/element
    passed to `set()` or the constructor) and must return True if the
    value is acceptable, or False to reject it. It may also raise its
    own exception (e.g. ValueError) instead of returning False, if it
    wants to report a more specific reason.

    `possible_values`, if provided, is the closed set of values this
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
    """

    name: str
    visible_name: str
    type: ConfigType
    value: Any
    config_type: Optional[ConfigDeliveryType] = None
    item_type: Optional[ConfigType] = None
    schema: Optional[dict[str, ConfigType]] = None
    validator: Optional[Callable[[Any], bool]] = None
    allowed_values: Optional[list[Any]] = None
    range: Optional[Range] = None
    max_length: Optional[int] = None
    tooltip: Optional[str] = None

    def __post_init__(self) -> None:
        if self.type is ConfigType.ARRAY and self.item_type is None:
            raise ValueError(f"{self.name}: ARRAY items require item_type")
        if self.type is ConfigType.TABLE and self.schema is None:
            raise ValueError(f"{self.name}: TABLE items require schema")
        if self.range is not None and self.type not in (
            ConfigType.INTEGER,
            ConfigType.FLOAT,
        ):
            raise ValueError(f"{self.name}: range only applies to INTEGER or FLOAT items")
        if self.max_length is not None and self.type is not ConfigType.STRING:
            raise ValueError(f"{self.name}: max_length only applies to STRING items")
        self._validate()

    def _validate(self) -> None:
        if self.type is ConfigType.ARRAY:
            self._validate_array()
        elif self.type is ConfigType.TABLE:
            self._validate_table()
        else:
            _check_scalar(self.name, self.value, self.type)

        if self.type in (ConfigType.INTEGER, ConfigType.FLOAT) and self.range is not None:
            if self.range.min_value is not None and self.value < self.range.min_value:
                raise ValueError(
                    f"{self.name}: value {self.value!r} is below min_value {self.range.min_value!r}"
                )
            if self.range.max_value is not None and self.value > self.range.max_value:
                raise ValueError(
                    f"{self.name}: value {self.value!r} is above max_value {self.range.max_value!r}"
                )

        if self.type is ConfigType.STRING and self.max_length is not None and len(self.value) > self.max_length:
            raise ValueError(
                f"{self.name}: value {self.value!r} exceeds max_length {self.max_length}"
            )

        if self.allowed_values is not None and self.value not in self.allowed_values:
            raise ValueError(
                f"{self.name}: value {self.value!r} not in possible_values "
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
        if not isinstance(self.value, dict):
            raise TypeError(
                f"{self.name}: expected TABLE (dict), got {type(self.value).__name__}"
            )

        expected_keys = set(self.schema.keys())
        actual_keys = set(self.value.keys())
        if expected_keys != actual_keys:
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            details = []
            if missing:
                details.append(f"missing {sorted(missing)}")
            if extra:
                details.append(f"unexpected {sorted(extra)}")
            raise TypeError(f"{self.name}: table keys mismatch ({', '.join(details)})")

        for key, expected_type in self.schema.items():
            try:
                _check_scalar(self.name, self.value[key], expected_type)
            except TypeError as e:
                raise TypeError(f"{self.name}.{key}: {e}") from e

    def set(self, value: Any) -> None:
        """Update the value, re-validating against the declared type,
        item_type/schema, and validator. If validation fails, the item
        is left unchanged (the old value is restored) rather than
        being left holding an invalid value."""
        previous = self.value
        self.value = value
        try:
            self._validate()
        except Exception:
            self.value = previous
            raise

    def values(self) -> Optional[list[Any]]:
        """Return the possible values for this item, or None if it's
        unconstrained (any value matching the declared type is fine)."""
        return self.allowed_values

    def __repr__(self) -> str:
        return (
            f"ConfigItem(name={self.name!r}, visible_name={self.visible_name!r}, "
            f"type={self.type.name}, value={self.value!r})"
        )