"""
valve_config_parser.py

Reads and writes Valve's "KeyValues" config format (used e.g. for CS2's
config/config.cfg key bindings): a tree of quoted "key" "value" pairs,
where a value can either be a quoted string or another `{ ... }` block.
`//` starts a line comment; everything up to the next newline is
ignored, including a whole commented-out "key" "value" line.

A parsed file becomes a nested dict — every key and every leaf value
is a plain str (KeyValues has no other scalar types), and a block
becomes a nested dict. Insertion order is preserved both ways since
Python dicts are ordered.
"""

import re
from pathlib import Path
from typing import Union

ValveConfig = dict[str, Union[str, "ValveConfig"]]

# A quoted string (group 1, with \" and \\ un-escaped by the caller),
# a brace, or a line comment (matched only to be discarded — comments
# aren't captured, so they never show up as tokens).
_TokenPattern = re.compile(r'"((?:\\.|[^"\\])*)"|(\{)|(\})|//[^\n]*')

_Indent = "\t"


class _Tokenizer:
    """A one-token-lookahead iterator over `_TokenPattern` matches.
    Each token is either "{", "}", or a string (already unescaped) —
    there's no way to tell a quoted "{" apart from a structural one at
    this level, but KeyValues files never quote braces, so that's fine."""

    def __init__(self, text: str):
        self._tokens = [
            match.group(2) or match.group(3) or _unescape(match.group(1))
            for match in _TokenPattern.finditer(text)
            if match.group(1) is not None or match.group(2) or match.group(3)
        ]
        self._pos = 0

    def peek(self) -> Union[str, None]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def next(self) -> str:
        token = self._tokens[self._pos]
        self._pos += 1
        return token


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_block(tokens: _Tokenizer) -> ValveConfig:
    result: ValveConfig = {}
    while True:
        key = tokens.peek()
        if key is None:
            # Truncated input (missing closing "}") — treat EOF as an
            # implicit close rather than crashing.
            return result
        if key == "}":
            tokens.next()
            return result
        tokens.next()  # consume the key

        value = tokens.peek()
        if value is None:
            # A key with no value before EOF — nothing more to parse.
            return result
        if value == "{":
            tokens.next()
            result[key] = _parse_block(tokens)
        else:
            result[key] = tokens.next()


def parse(text: str) -> ValveConfig:
    """Parse a KeyValues document into a nested dict — a top-level
    "key" { ... } becomes {"key": {...}} (e.g. "config" { ... } or a
    workshop item's publish_data.txt's "publish_data" { ... })."""
    tokens = _Tokenizer(text)
    result: ValveConfig = {}
    while True:
        key = tokens.peek()
        if key is None:
            return result
        tokens.next()

        value = tokens.peek()
        if value is None:
            # A key with no value before EOF — nothing more to parse.
            return result
        if value == "{":
            tokens.next()
            result[key] = _parse_block(tokens)
        else:
            result[key] = tokens.next()


def dumps(config: ValveConfig) -> str:
    """Render a nested dict (as returned by parse()) back into
    KeyValues text."""
    lines: list[str] = []
    _dump_block(config, 0, lines)
    return "\n".join(lines) + "\n"


def _dump_block(config: ValveConfig, depth: int, lines: list[str]) -> None:
    indent = _Indent * depth
    for key, value in config.items():
        if isinstance(value, dict):
            lines.append(f'{indent}"{_escape(key)}"')
            lines.append(f"{indent}{{")
            _dump_block(value, depth + 1, lines)
            lines.append(f"{indent}}}")
        else:
            lines.append(f'{indent}"{_escape(key)}"{_Indent}"{_escape(str(value))}"')


class ValveConfigParser:
    """Reads and writes Valve KeyValues config files (see module
    docstring) to/from nested dicts."""

    @staticmethod
    def read(path: Union[str, Path]) -> ValveConfig:
        return parse(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def write(path: Union[str, Path], config: ValveConfig) -> None:
        Path(path).write_text(dumps(config), encoding="utf-8")
