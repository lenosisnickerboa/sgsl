"""
valve_gamemode_config_parser.py

Reads and writes Valve's flat per-gamemode server cvar override files
(e.g. CS2's gamemode_*_server.cfg): one cvar assignment per line,

    name<whitespace>value<whitespace>// comment

where value is either a bare token (no whitespace, e.g. 0, -2.0, off,
fill_with_minimum) or a "quoted string" (may be empty: ""). `//` starts
a line comment; a line that's entirely a comment (or blank) is kept
verbatim rather than parsed, so round-tripping an unmodified file back
through dumps() preserves it exactly. Only the whitespace *within* a
parsed cvar line is normalized on write (single tabs) -- see dumps().
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass
class ConfigEntry:
    """One parsed cvar assignment line."""

    name: str
    value: str
    comment: str = ""


# A document is an ordered mix of parsed cvar entries and verbatim
# lines (blank lines, full-line comments, or anything else that isn't
# a recognizable "name value" assignment) -- kept as plain strings so
# writing an untouched document back out reproduces it exactly.
GamemodeConfig = list[Union[ConfigEntry, str]]

_LinePattern = re.compile(
    r"^(?P<name>\S+)\s+"
    r'(?:"(?P<qvalue>[^"]*)"|(?P<value>\S+))'
    r"\s*(?://\s*(?P<comment>.*))?$"
)


def _parse_line(line: str) -> Union[ConfigEntry, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return line

    match = _LinePattern.match(stripped)
    if not match:
        # Doesn't look like a cvar assignment -- keep it verbatim
        # rather than losing/mangling content we don't understand.
        return line

    value = (
        match.group("qvalue") if match.group("qvalue") is not None else match.group("value")
    )
    return ConfigEntry(
        name=match.group("name"),
        value=value,
        comment=match.group("comment") or "",
    )


def parse(text: str) -> GamemodeConfig:
    """Parse a gamemode cvar override file into an ordered list of
    ConfigEntry (recognized "name value" lines) and str (everything
    else -- blank lines, comment-only lines, or unparseable lines --
    kept verbatim)."""
    return [_parse_line(line) for line in text.splitlines()]


def _needs_quotes(value: str) -> bool:
    return value == "" or any(c.isspace() for c in value)


def _format_entry(entry: ConfigEntry) -> str:
    value = f'"{entry.value}"' if _needs_quotes(entry.value) else entry.value
    line = f"{entry.name}\t{value}"
    if entry.comment:
        line += f"\t// {entry.comment}"
    return line


def dumps(config: GamemodeConfig) -> str:
    """Render a parsed document (as returned by parse()) back into
    text. Verbatim (str) entries are written unchanged; ConfigEntry
    lines are rewritten as `name<TAB>value[<TAB>// comment]`."""
    lines = [
        _format_entry(entry) if isinstance(entry, ConfigEntry) else entry
        for entry in config
    ]
    return "\n".join(lines) + "\n"


class ValveGamemodeConfigParser:
    """Reads and writes Valve's flat per-gamemode server cvar override
    files (see module docstring) to/from a list of ConfigEntry/str."""

    @staticmethod
    def read(path: Union[str, Path]) -> GamemodeConfig:
        return parse(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def write(path: Union[str, Path], config: GamemodeConfig) -> None:
        Path(path).write_text(dumps(config), encoding="utf-8")
