"""
frostbite_rcon_client.py

A minimal client for the Frostbite "Plasma" RCON protocol used by
Venice Unleashed's dedicated server (the same protocol Battlefield 3/4
servers use for remote admin) -- a different, word-based binary
protocol from Valve's Source RCON (see support/rcon_client.py, used by
cs2/csgo), sent over VU's own dedicated RCON port (-RemoteAdminPort /
ConfigIndex.LISTEN_PORT_RCON) rather than the game's main listen port.

Packet format (all integers little-endian uint32):
    sequence (bit 31 set => this is a response; bit 30 set => the
        packet originated from the server, e.g. an unsolicited event)
    total packet size, including this 12-byte header
    word count
    for each word: word length, word bytes (UTF-8), one trailing NUL

A command is a list of words, e.g. ["login.plainText", "<password>"];
the response is likewise a list of words, whose first word is "OK" on
success or an error code (e.g. "InvalidPassword") otherwise.

NOTE: this implementation is based on the publicly documented
Frostbite/Plasma RCON protocol (as used by BF3/BF4 admin tools, which
VU's own RCON is modeled on) -- it has not been verified against a
live Venice Unleashed server. In particular, VU has no config item of
its own for a dedicated RCON password; this client logs in with
ConfigIndex.SERVER_PASSWORD (vars.gamePassword), matching Frostbite's
usual single-password remote-admin convention -- if VU actually
expects something else, that's the one place to change (see
VUGame.send_rcon_command()).
"""

import socket
import struct
from typing import Optional

_ResponseFlag = 0x80000000
_ServerOriginatedFlag = 0x40000000
_SequenceMask = 0x3FFFFFFF


class RconError(Exception):
    """Raised for any RCON failure -- couldn't connect, the connection
    dropped mid-exchange, or a malformed response."""


class RconAuthError(RconError):
    """Raised specifically when the server rejects the RCON password."""


def _encode_packet(sequence: int, is_response: bool, words: list[str]) -> bytes:
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
        """Open the TCP connection and log in with the plain-text
        password. Raises RconAuthError if the password is rejected, or
        RconError for any other connection/protocol failure."""
        try:
            self._sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as e:
            raise RconError(f"Could not connect to {self.host}:{self.port}: {e}") from e

        try:
            words = self.command("login.plainText", self.password)
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
        (the login command itself, sent from connect(), is the one
        exception)."""
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
                # Anything else is a server-originated, unsolicited
                # event packet (e.g. a player join notification) --
                # this client never subscribes to those, but skip
                # (rather than choke on) one if it shows up anyway,
                # and keep waiting for our own command's response.
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
