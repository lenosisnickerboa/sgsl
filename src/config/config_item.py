from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional


class ConfigType(Enum):
    """Maps to the value types TOML supports."""

    STRING = str
    INTEGER = int
    FLOAT = float
    BOOLEAN = bool
    DATETIME = datetime
    DATE = date
    TIME = time
    ARRAY = list
    TABLE = dict


def _check_scalar(name: str, value: Any, expected_type: ConfigType) -> None:
    """Validate a single scalar value against a ConfigType, with the
    bool/int special case handled explicitly."""

    py_type = expected_type.value

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
    """

    name: str
    visible_name: str
    type: ConfigType
    value: Any
    item_type: Optional[ConfigType] = None
    schema: Optional[dict[str, ConfigType]] = None

    def __post_init__(self) -> None:
        if self.type is ConfigType.ARRAY and self.item_type is None:
            raise ValueError(f"{self.name}: ARRAY items require item_type")
        if self.type is ConfigType.TABLE and self.schema is None:
            raise ValueError(f"{self.name}: TABLE items require schema")
        self._validate()

    def _validate(self) -> None:
        if self.type is ConfigType.ARRAY:
            self._validate_array()
        elif self.type is ConfigType.TABLE:
            self._validate_table()
        else:
            _check_scalar(self.name, self.value, self.type)

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
        """Update the value, re-validating against the declared type."""
        self.value = value
        self._validate()

    def __repr__(self) -> str:
        return (
            f"ConfigItem(name={self.name!r}, visible_name={self.visible_name!r}, "
            f"type={self.type.name}, value={self.value!r})"
        )