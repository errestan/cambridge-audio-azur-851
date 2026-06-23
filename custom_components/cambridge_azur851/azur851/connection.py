"""Transport layer for the Azur 851 client.

Abstracts *how* bytes reach the device so the protocol layer doesn't care whether
the link is a Home Assistant serial proxy, a raw TCP socket to a serial bridge, or
a local serial port.
"""

from __future__ import annotations

import asyncio


class Azur851Connection:
    """Async byte transport with a single-writer lock.

    Only one command/response exchange may be in flight at a time, so all I/O is
    serialized behind `_lock`.
    """

    def __init__(self) -> None:
        """Initialize the connection wrapper."""
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @classmethod
    def from_serial_proxy(cls, host: str, port: int) -> Azur851Connection:
        """Create a connection that uses Home Assistant's serial proxy.

        TODO: Confirm the serial-proxy connection API for the target HA release.
        Options to evaluate:
          - a TCP socket to the proxy endpoint (asyncio.open_connection), or
          - a serial URL handled by pyserial-asyncio (e.g. "socket://host:port").
        Pick one and document the required config keys in `const.py`.
        """
        raise NotImplementedError

    @classmethod
    def from_serial_url(cls, url: str, baudrate: int) -> Azur851Connection:
        """Create a connection from a pyserial URL (local port or socket://...)."""
        raise NotImplementedError

    async def async_open(self) -> None:
        """Open the transport."""
        raise NotImplementedError

    async def async_send(self, frame: bytes) -> bytes:
        """Send a command frame and return the raw response frame.

        Guarded by the lock so concurrent callers do not interleave I/O.
        """
        async with self._lock:
            raise NotImplementedError

    async def async_close(self) -> None:
        """Close the transport."""
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None
