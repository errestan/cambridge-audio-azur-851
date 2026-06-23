"""Transport layer for the Azur 851 client.

Abstracts *how* bytes reach the device so the protocol layer doesn't care whether
the link is a Home Assistant serial proxy, a raw TCP socket to a serial bridge, or
a local serial port.

Construction stores connection parameters only; opening the link and the actual
byte I/O are left as TODOs (see ``async_open`` / ``async_send``).
"""

from __future__ import annotations

import asyncio


class Azur851Connection:
    """Async byte transport with a single-writer lock.

    Only one command/response exchange may be in flight at a time, so all I/O is
    serialized behind ``_lock``.
    """

    def __init__(self) -> None:
        """Initialize the connection wrapper."""
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._serial_url: str | None = None
        self._baudrate: int | None = None

    @classmethod
    def from_serial_proxy(cls, host: str, port: int) -> Azur851Connection:
        """Create a connection that reaches the device via a serial proxy.

        TODO: Confirm the serial-proxy connection scheme for the target HA
        release, then implement ``async_open``/``async_send`` accordingly.
        Likely either a TCP socket (``asyncio.open_connection``) or a
        ``socket://host:port`` serial URL.
        """
        conn = cls()
        conn._host = host
        conn._port = port
        return conn

    @classmethod
    def from_serial_url(cls, url: str, baudrate: int) -> Azur851Connection:
        """Create a connection from a pyserial URL (local port or socket://...)."""
        conn = cls()
        conn._serial_url = url
        conn._baudrate = baudrate
        return conn

    async def async_open(self) -> None:
        """Open the transport."""
        # TODO: establish self._reader / self._writer from the stored params.
        raise NotImplementedError

    async def async_send(self, frame: bytes) -> bytes:
        """Send a command frame and return the raw response frame.

        Guarded by the lock so concurrent callers do not interleave I/O.
        """
        async with self._lock:
            # TODO: write `frame`, then read until the CR terminator (0x0D).
            raise NotImplementedError

    async def async_close(self) -> None:
        """Close the transport."""
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None
