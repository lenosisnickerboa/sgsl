"""
rcon_client.py

A minimal client for Valve's Source RCON protocol -- used by Source-
engine dedicated servers (CS2, and later re-usable by CS:GO) to accept
admin commands over a plain TCP connection on the game's own listen
port. See https://developer.valvesoftware.com/wiki/Source_RCON_Protocol.

RconClient is the low-level connection; run_rcon_command() is a
higher-level, still game-agnostic convenience wrapper that validates
RCON is actually configured (enabled, has a password) and connects/
sends/disconnects for a single command -- what a game's "RCON console"
UI action actually calls, each pulling its own enabled/host/port/
password out of its own Config.
"""

import socket
import struct
from dataclasses import dataclass
from typing import Optional

# Packet types (see the protocol page linked above). The client only
# ever sends AUTH/EXECCOMMAND and receives AUTH_RESPONSE/RESPONSE_VALUE
# -- SERVERDATA_EXECCOMMAND and SERVERDATA_AUTH_RESPONSE share the
# same wire value (2) by design of the original protocol.
_TypeResponseValue = 0
_TypeExecCommand = 2
_TypeAuthResponse = 2
_TypeAuth = 3


class RconError(Exception):
    """Raised for any RCON failure -- couldn't connect, the connection
    dropped mid-exchange, or a malformed response."""


class RconAuthError(RconError):
    """Raised specifically when the server rejects the RCON password."""


@dataclass
class _Packet:
    id: int
    type: int
    body: str


def _encode_packet(packet_id: int, packet_type: int, body: str) -> bytes:
    payload = struct.pack("<ii", packet_id, packet_type) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


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


def _recv_packet(sock: socket.socket) -> _Packet:
    (size,) = struct.unpack("<i", _recv_exact(sock, 4))
    payload = _recv_exact(sock, size)
    packet_id, packet_type = struct.unpack("<ii", payload[:8])
    # payload is <id><type><body>\x00\x00 -- strip the two trailing
    # null terminators (body's own, then the packet's).
    body = payload[8:-2].decode("utf-8", errors="replace")
    return _Packet(id=packet_id, type=packet_type, body=body)


class RconClient:
    """A short-lived connection to a Source RCON server: connect(),
    then one or more command() calls, then close() -- or use as a
    context manager. Not safe to share across threads."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._next_id = 1

    def connect(self) -> None:
        """Open the TCP connection and authenticate. Raises
        RconAuthError if the password is rejected, or RconError for
        any other connection/protocol failure."""
        try:
            self._sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as e:
            raise RconError(f"Could not connect to {self.host}:{self.port}: {e}") from e

        auth_id = self._next_request_id()
        try:
            self._sock.sendall(_encode_packet(auth_id, _TypeAuth, self.password))
            # The server sends an empty SERVERDATA_RESPONSE_VALUE
            # first (a quirk of the protocol) before the real
            # SERVERDATA_AUTH_RESPONSE -- skip it if present.
            response = _recv_packet(self._sock)
            if response.type == _TypeResponseValue:
                response = _recv_packet(self._sock)
        except (OSError, struct.error) as e:
            self.close()
            raise RconError(
                f"RCON handshake with {self.host}:{self.port} failed: {e}"
            ) from e

        if response.id == -1:
            self.close()
            raise RconAuthError(
                f"RCON authentication to {self.host}:{self.port} was rejected "
                "(wrong password?)"
            )

    # How long to wait for a *continuation* packet of a multi-packet
    # response, once the first one has already arrived -- short, since
    # by then the server has already started replying and any further
    # fragments should already be in flight/queued, not still being
    # computed. See command()'s comment on why this replaces the
    # protocol's documented "terminator packet" trick.
    _ContinuationTimeout = 0.2

    def command(self, command: str) -> str:
        """Send `command` and return the server's response text. Must
        be called after a successful connect()."""
        if self._sock is None:
            raise RconError("Not connected -- call connect() first")
        request_id = self._next_request_id()
        try:
            self._sock.sendall(_encode_packet(request_id, _TypeExecCommand, command))
            parts = [_recv_packet(self._sock).body]
            # A large response can be split across multiple packets.
            # The protocol wiki's documented workaround (send a
            # follow-up "terminator" packet and read until its own
            # distinctly-numbered reply comes back) depends on the
            # server understanding and echoing back that terminator --
            # not reliably true across every Source-engine-family
            # server (observed hanging indefinitely against CS2, which
            # never sends anything back for it), so instead just drain
            # whatever arrives within a short window after the first
            # packet -- if nothing more shows up, the response was
            # just the one packet, which covers the vast majority of
            # commands.
            self._sock.settimeout(self._ContinuationTimeout)
            try:
                while True:
                    parts.append(_recv_packet(self._sock).body)
            except (TimeoutError, OSError):
                pass
            finally:
                self._sock.settimeout(self.timeout)
            return "".join(parts)
        except (OSError, struct.error) as e:
            raise RconError(f"RCON command failed: {e}") from e

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _next_request_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id

    def __enter__(self) -> "RconClient":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def run_rcon_command(
    command: str,
    *,
    enabled: bool,
    host: str,
    port: int,
    password: str,
    timeout: float = 5.0,
) -> str:
    """Validate that RCON is actually usable and, if so, connect and
    send `command` -- shared by every game's RCON console action,
    which is responsible for pulling enabled/host/port/password out of
    its own Config (see e.g. CS2Game.send_rcon_command()).

    A `host` of "0.0.0.0" (listen on all interfaces) is connected to
    as "127.0.0.1" instead, since sgsl only ever hosts local servers.

    Raises RuntimeError if RCON isn't usable (disabled, no password
    set), or RconError if the connection/command itself fails."""
    if not enabled:
        raise RuntimeError("RCON is disabled -- enable it first")
    if not password:
        raise RuntimeError("No RCON password configured -- set one first")
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with RconClient(connect_host, port, password, timeout=timeout) as client:
        return client.command(command)
