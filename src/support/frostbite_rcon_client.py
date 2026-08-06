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

Packet format (all integers little-endian uint32), per the BF3 PC
Server Remote Administration Protocol spec (the protocol VU's RCON is
modeled on):
    sequence: bit 31 set => this request/response pair originated on
        the client (vs. the server, e.g. an unsolicited event); bit 30
        set => this packet is a response (vs. a request); bits 29..0
        => sequence number, unique per connection
    total packet size, including this 12-byte header
    word count
    for each word: word length, word bytes (UTF-8), one trailing NUL

A command is a list of words, e.g. ["login.plainText", "<password>"];
the response is likewise a list of words, whose first word is "OK" on
success or an error code (e.g. "InvalidPassword") otherwise.

Every request -- including an unsolicited one the server itself sends
(e.g. a player-join event, only if admin.eventsEnabled was turned on
for this connection) -- must be acknowledged with a response, or the
server may close the connection without warning; command() acks any
such event with a bare "OK" as it drains them while waiting for its
own request's actual response.
"""

import socket
import struct
from typing import Optional

# Bit 31: 1 = this request/response pair originated on the client
# (this class only ever originates requests, so every request it sends
# has this set; a response echoes back whatever the original request
# had, and an unsolicited server-originated event has it clear).
_ClientOriginatedFlag = 0x80000000
# Bit 30: 1 = this packet is a response (vs. a request).
_ResponseFlag = 0x40000000
_SequenceMask = 0x3FFFFFFF


class RconError(Exception):
    """Raised for any RCON failure -- couldn't connect, the connection
    dropped mid-exchange, or a malformed response."""


class RconAuthError(RconError):
    """Raised specifically when the server rejects the RCON password."""


def _encode_packet(
    sequence: int, *, client_originated: bool, is_response: bool, words: list[str]
) -> bytes:
    header_flags = (_ClientOriginatedFlag if client_originated else 0) | (
        _ResponseFlag if is_response else 0
    )
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


def _recv_packet(sock: socket.socket) -> tuple[int, bool, bool, list[str]]:
    raw_sequence, total_size, word_count = struct.unpack("<III", _recv_exact(sock, 12))
    client_originated = bool(raw_sequence & _ClientOriginatedFlag)
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
    return sequence, client_originated, is_response, words


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
                _encode_packet(
                    sequence, client_originated=True, is_response=False, words=list(words)
                )
            )
            while True:
                (
                    response_sequence,
                    client_originated,
                    is_response,
                    response_words,
                ) = _recv_packet(self._sock)
                if is_response:
                    if client_originated and response_sequence == sequence:
                        return response_words
                    # A response to some other, already-abandoned
                    # request (e.g. a stale one from before a timeout) --
                    # not ours, keep waiting for the real one.
                    continue
                # Anything else is a server-originated, unsolicited
                # event packet (e.g. a player join notification, only
                # if admin.eventsEnabled was turned on for this
                # connection) -- this client never subscribes to those,
                # but every request must still be acknowledged or the
                # server may close the connection (see module
                # docstring), so ack it with a bare "OK" and keep
                # waiting for our own command's actual response.
                self._sock.sendall(
                    _encode_packet(
                        response_sequence,
                        client_originated=client_originated,
                        is_response=True,
                        words=["OK"],
                    )
                )
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
