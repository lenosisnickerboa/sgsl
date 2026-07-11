from __future__ import annotations

from dataclasses import dataclass

from config.toml_config import IndexT


@dataclass
class TabSpec:
    """One tab in a detailed configuration window: a title and the
    config items (by index) to show on that tab."""

    title: str
    items: list[IndexT]
