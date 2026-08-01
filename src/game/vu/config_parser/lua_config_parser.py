"""
lua_config_parser.py

Reads and writes simple Lua config assignment files: one assignment per line,

    Config.Name = value -- comment

where value is a Lua literal (true/false, a bare number, or a "quoted
string"). `--` starts a line comment; a line that's entirely a comment
(or blank) is kept verbatim rather than parsed, so round-tripping an
unmodified file back through dumps() preserves it exactly. Only the
whitespace *within* a parsed assignment line is normalized on write --
see dumps().
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass
class ConfigEntry:
    """One parsed `Name = value` assignment line."""

    name: str
    value: str
    comment: str = ""


# A document is an ordered mix of parsed assignment entries and
# verbatim lines (blank lines, full-line comments, or anything else
# that isn't a recognizable "name = value" assignment) -- kept as
# plain strings so writing an untouched document back out reproduces
# it exactly.
LuaConfig = list[Union[ConfigEntry, str]]

_LinePattern = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*"
    r'(?:"(?P<qvalue>[^"]*)"|(?P<value>[^\s]+?))'
    r"\s*(?:--\s*(?P<comment>.*))?$"
)


def _parse_line(line: str) -> Union[ConfigEntry, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("--"):
        return line

    match = _LinePattern.match(stripped)
    if not match:
        # Doesn't look like an assignment -- keep it verbatim rather
        # than losing/mangling content we don't understand.
        return line

    value = (
        match.group("qvalue")
        if match.group("qvalue") is not None
        else match.group("value")
    )
    return ConfigEntry(
        name=match.group("name"),
        value=value,
        comment=match.group("comment") or "",
    )


def parse(text: str) -> LuaConfig:
    """Parse a Lua config file into an ordered list of ConfigEntry
    (recognized "name = value" lines) and str (everything else --
    blank lines, comment-only lines, or unparseable lines -- kept
    verbatim)."""
    return [_parse_line(line) for line in text.splitlines()]


def _format_entry(entry: ConfigEntry) -> str:
    line = f"{entry.name} = {entry.value}"
    if entry.comment:
        line += f" -- {entry.comment}"
    return line


def dumps(config: LuaConfig) -> str:
    """Render a parsed document (as returned by parse()) back into
    text. Verbatim (str) entries are written unchanged; ConfigEntry
    lines are rewritten as `name = value[ -- comment]`."""
    lines = [
        _format_entry(entry) if isinstance(entry, ConfigEntry) else entry
        for entry in config
    ]
    return "\n".join(lines) + "\n"


class LuaConfigParser:
    """Reads and writes simple Lua config assignment files (see module
    docstring) to/from a list of ConfigEntry/str."""

    @staticmethod
    def read(path: Union[str, Path]) -> LuaConfig:
        return parse(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def write(path: Union[str, Path], config: LuaConfig) -> None:
        Path(path).write_text(dumps(config), encoding="utf-8")
