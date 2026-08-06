"""
frostbite_rcon_client.py

A minimal client for the Frostbite "Plasma" RCON protocol used by
Venice Unleashed's dedicated server (the same protocol Battlefield 3/4
servers use for remote admin) -- a different, word-based binary
protocol from Valve's Source RCON (see support/rcon_client.py, used by
cs2/csgo), sent over VU's own dedicated RCON port (-RemoteAdminPort /
ConfigIndex.LISTEN_PORT_RCON) rather than the game's main listen port.
Logs in with ConfigIndex.RCON_PASSWORD (admin.password) -- VU's own
dedicated admin password, distinct from the server join password.

Packet format (all integers little-endian uint32):
    sequence: bit 30 set => this packet is a response (vs. a request);
        bits 29..0 => sequence number, unique per connection. (Bit 31
        is documented by the official BF3 PC Server Remote
        Administration Protocol spec as a client/server "origin" flag,
        but the actively-maintained `vu-rcon` npm package -- used by
        VeniceRCON, a widely-used VU RCON tool -- always sends it 0 and
        never inspects it on receipt either, so it's ignored here too;
        an earlier version of this client set it on every outgoing
        request per the spec, which made real VU servers stop
        responding entirely.)
    total packet size, including this 12-byte header
    word count
    for each word: word length, word bytes (UTF-8), one trailing NUL

A command is a list of words; the response is likewise a list of
words, whose first word is "OK" on success or an error code (e.g.
"InvalidPassword") otherwise.

Logs in via the 2-step hashed procedure (login.hashed with no
arguments to fetch a salt, then login.hashed <MD5(salt + password),
uppercase hex>) rather than login.plainText -- again matching
vu-rcon/VeniceRCON, since that's the login vu-rcon actually uses.

Server-originated unsolicited event packets (e.g. a chat message,
if admin.eventsEnabled is on for this connection) are simply discarded
while waiting for a command's own response, same as vu-rcon does --
they're never acknowledged, despite the official spec saying every
request must be.
"""

import hashlib
import socket
import struct
from typing import Optional

# Bit 30: 1 = this packet is a response (vs. a request). See the
# module docstring for why bit 31 (the spec's "origin" flag) plays no
# part here.
_ResponseFlag = 0x40000000
_SequenceMask = 0x3FFFFFFF


class RconError(Exception):
    """Raised for any RCON failure -- couldn't connect, the connection
    dropped mid-exchange, or a malformed response."""


class RconAuthError(RconError):
    """Raised specifically when the server rejects the RCON password."""


def _encode_packet(sequence: int, *, is_response: bool, words: list[str]) -> bytes:
    header_flags = _ResponseFlag if is_response else 0
    word_bytes = b""
    for word in words:
        encoded = word.encode("utf-8")
        word_bytes += struct.pack("<I", len(encoded)) + encoded + b"\x00"
    total_size = 12 + len(word_bytes)
    return (
        struct.pack("<III", sequence | header_flags, total_size, len(words)) + word_bytes
    )


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RconError("Connection closed while reading a response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recv_packet(sock: socket.socket) -> tuple[int, bool, list[str]]:
    raw_sequence, total_size, word_count = struct.unpack("<III", _recv_exact(sock, 12))
    is_response = bool(raw_sequence & _ResponseFlag)
    sequence = raw_sequence & _SequenceMask
    body = _recv_exact(sock, total_size - 12)
    words = []
    offset = 0
    for _ in range(word_count):
        (word_len,) = struct.unpack_from("<I", body, offset)
        offset += 4
        words.append(body[offset : offset + word_len].decode("utf-8", errors="replace"))
        offset += word_len + 1  # + trailing NUL
    return sequence, is_response, words


class FrostbiteRconClient:
    """A short-lived connection to a Frostbite/Plasma RCON server (VU,
    BF3/BF4): connect(), then one or more command() calls, then
    close() -- or use as a context manager. Not safe to share across
    threads."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._next_sequence = 0

    def connect(self) -> None:
        """Open the TCP connection and log in via the 2-step hashed
        password procedure (see module docstring). Raises
        RconAuthError if either step is rejected, or RconError for any
        other connection/protocol failure."""
        try:
            self._sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as e:
            raise RconError(f"Could not connect to {self.host}:{self.port}: {e}") from e

        try:
            salt_words = self.command("login.hashed")
        except RconError:
            self.close()
            raise
        if not salt_words or salt_words[0] != "OK" or len(salt_words) < 2:
            self.close()
            reason = salt_words[0] if salt_words else "no response"
            raise RconAuthError(
                f"RCON salt request to {self.host}:{self.port} was rejected ({reason})"
            )

        try:
            salt = bytes.fromhex(salt_words[1])
        except ValueError as e:
            self.close()
            raise RconError(f"RCON server sent a malformed salt: {e}") from e
        password_hash = (
            hashlib.md5(salt + self.password.encode("utf-8")).hexdigest().upper()
        )

        try:
            words = self.command("login.hashed", password_hash)
        except RconError:
            self.close()
            raise
        if not words or words[0] != "OK":
            self.close()
            reason = words[0] if words else "no response"
            raise RconAuthError(
                f"RCON authentication to {self.host}:{self.port} was rejected ({reason})"
            )

    def command(self, *words: str) -> list[str]:
        """Send one command (a list of words) and return the server's
        response words. Must be called after a successful connect()
        (the login commands themselves, sent from connect(), are the
        one exception)."""
        if self._sock is None:
            raise RconError("Not connected -- call connect() first")
        sequence = self._next_sequence
        self._next_sequence += 1
        try:
            self._sock.sendall(
                _encode_packet(sequence, is_response=False, words=list(words))
            )
            while True:
                response_sequence, is_response, response_words = _recv_packet(
                    self._sock
                )
                if is_response and response_sequence == sequence:
                    return response_words
                # Either a server-originated, unsolicited event packet
                # (e.g. a chat message, if admin.eventsEnabled is on --
                # this client never turns that on itself, but another
                # RCON client sharing the same admin password could),
                # or a stale response to some other, already-abandoned
                # request -- neither is ours; discard and keep waiting
                # for our own command's actual response (see module
                # docstring for why events aren't acknowledged here).
        except (OSError, struct.error) as e:
            raise RconError(f"RCON command failed: {e}") from e

    def close(self) -> None:
        if self._sock is not None:
            try:
                # An abortive (RST) close instead of the default graceful
                # FIN-based one -- see support/rcon_client.py's
                # RconClient.close() for why (same fix, same reasoning,
                # for VU's dedicated RCON port instead of Source RCON's).
                self._sock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                )
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self) -> "FrostbiteRconClient":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def run_rcon_command(
    command: list[str],
    *,
    enabled: bool,
    host: str,
    port: int,
    password: str,
    timeout: float = 5.0,
) -> str:
    """Validate that RCON is actually usable and, if so, connect, log
    in, and send `command` (already split into words) -- mirrors
    support.rcon_client.run_rcon_command()'s role for Source RCON.

    A `host` of "0.0.0.0" (listen on all interfaces) is connected to
    as "127.0.0.1" instead, since sgsl only ever hosts local servers.

    Raises RuntimeError if RCON isn't usable (disabled, no password
    set), or RconError if the connection/command itself fails."""
    if not enabled:
        raise RuntimeError("RCON is disabled -- enable it first")
    if not password:
        raise RuntimeError("No RCON password configured -- set one first")
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with FrostbiteRconClient(connect_host, port, password, timeout=timeout) as client:
        return " ".join(client.command(*command))
