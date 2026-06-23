"""Transport layer for the Azur 851 client.

Uses Home Assistant's ``serialx`` library, whose ``open_serial_connection`` URL
handles local ports, ``socket://`` bridges (ser2net/socat) and ESPHome serial
proxies transparently -- so this module does not care which is in use.

Because the 851 protocol is push-based (the device emits group-4 frames on every
state change), the connection runs a background read loop and pushes each
complete frame to ``on_frame``; writes are fire-and-forget.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import serialx

from .exceptions import Azur851ConnectionError
from .protocol import TERMINATOR

_LOGGER = logging.getLogger(__name__)

# Frames are terminated by a carriage return (0x0D).
_TERMINATOR_BYTES: bytes = TERMINATOR.encode("ascii")


class Azur851Connection:
    """Async serial transport with a background read loop.

    ``on_frame`` is invoked (in the event loop) with each complete raw frame,
    including the trailing terminator. Writes are serialized behind ``_lock``.
    """

    def __init__(self, url: str, baudrate: int) -> None:
        """Store connection parameters. The link is opened by ``async_open``."""
        self._url = url
        self._baudrate = baudrate
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: serialx.SerialStreamWriter | None = None
        self._read_task: asyncio.Task[None] | None = None
        self.on_frame: Callable[[bytes], None] | None = None

    @property
    def is_open(self) -> bool:
        """Return True if the transport is currently open."""
        return self._writer is not None

    async def async_open(self) -> None:
        """Open the serial link and start the background read loop."""
        if self.is_open:
            return
        try:
            self._reader, self._writer = await serialx.open_serial_connection(
                self._url, baudrate=self._baudrate
            )
        except (serialx.SerialException, OSError, ValueError) as err:
            raise Azur851ConnectionError(f"Could not open {self._url}: {err}") from err
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Read complete frames and dispatch them to ``on_frame``."""
        assert self._reader is not None
        while True:
            try:
                frame = await self._reader.readuntil(_TERMINATOR_BYTES)
            except asyncio.IncompleteReadError:
                break  # EOF: link closed
            except (serialx.SerialException, OSError, asyncio.LimitOverrunError) as err:
                _LOGGER.debug("Serial read loop stopped: %s", err)
                break
            if self.on_frame is not None:
                self.on_frame(frame)

    async def async_write(self, frame: bytes) -> None:
        """Write a command frame to the device."""
        if self._writer is None:
            raise Azur851ConnectionError("Connection is not open")
        async with self._lock:
            try:
                self._writer.write(frame)
                await self._writer.drain()
            except (serialx.SerialException, OSError) as err:
                raise Azur851ConnectionError(f"Write failed: {err}") from err

    async def async_close(self) -> None:
        """Stop the read loop and close the transport."""
        if self._read_task is not None:
            self._read_task.cancel()
            self._read_task = None
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (serialx.SerialException, OSError):
                pass
            self._writer = None
            self._reader = None
