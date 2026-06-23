"""Transport layer for the Azur 851 client.

Uses Home Assistant's ``serialx`` library, whose ``open_serial_connection`` URL
handles local ports, ``socket://`` bridges (ser2net/socat) and ESPHome serial
proxies transparently -- so this module does not care which is in use.

Because the 851 protocol is push-based (the device emits group-4 frames on every
state change), the connection runs a background read loop and pushes each
complete frame to ``on_frame``; writes are fire-and-forget.

The initial open (``async_open``) raises on failure so setup can report it. Once
opened, an unexpected drop triggers a background reconnect with exponential
backoff, and ``on_connection_state`` reports availability transitions.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

import serialx

from .exceptions import Azur851ConnectionError
from .protocol import TERMINATOR

_LOGGER = logging.getLogger(__name__)

# Frames are terminated by a carriage return (0x0D).
_TERMINATOR_BYTES: bytes = TERMINATOR.encode("ascii")

# Reconnect backoff bounds (seconds).
_RECONNECT_INITIAL_DELAY: float = 2.0
_RECONNECT_MAX_DELAY: float = 60.0

# serialx platforms to enumerate for the config-flow port picker: local hardware
# and (when Home Assistant has registered it) ESPHome serial proxies.
_DISCOVERY_PLATFORMS = (serialx.Platform.DEVICE, serialx.Platform.ESPHOME)


@dataclass(frozen=True)
class DiscoveredPort:
    """A serial port offered to the user, with a friendly label."""

    device: str  # the URL/path to pass to serialx
    label: str


def _describe(port: serialx.SerialPortInfo) -> str:
    """Build a human-friendly label for a discovered port."""
    name = " ".join(p for p in (port.manufacturer, port.product) if p)
    name = name or port.description or port.device
    return f"{name} ({port.device})" if name != port.device else port.device


async def async_discover_ports() -> list[DiscoveredPort]:
    """Enumerate available serial ports (local + ESPHome proxies).

    Best-effort: a platform with no registered handler (e.g. ``esphome://`` when
    not running under Home Assistant) is skipped rather than raising.
    """
    found: list[DiscoveredPort] = []
    seen: set[str] = set()
    for platform in _DISCOVERY_PLATFORMS:
        try:
            ports = await serialx.async_list_serial_ports(platform)
        except Exception as err:  # noqa: BLE001 - discovery must never break setup
            _LOGGER.debug("Port discovery for %s skipped: %s", platform, err)
            continue
        for port in ports:
            if port.device in seen:
                continue
            seen.add(port.device)
            found.append(DiscoveredPort(port.device, _describe(port)))
    return found


class Azur851Connection:
    """Async serial transport with a background read loop and auto-reconnect.

    ``on_frame`` is invoked (in the event loop) with each complete raw frame,
    including the trailing terminator. ``on_connection_state`` is invoked with
    ``True`` when the link comes up and ``False`` when it drops. Writes are
    serialized behind ``_lock``.
    """

    def __init__(
        self,
        url: str,
        baudrate: int,
        *,
        reconnect_initial: float = _RECONNECT_INITIAL_DELAY,
        reconnect_max: float = _RECONNECT_MAX_DELAY,
    ) -> None:
        """Store connection parameters. The link is opened by ``async_open``."""
        self._url = url
        self._baudrate = baudrate
        self._reconnect_initial = reconnect_initial
        self._reconnect_max = reconnect_max
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: serialx.SerialStreamWriter | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._closing = False
        self.on_frame: Callable[[bytes], None] | None = None
        self.on_connection_state: Callable[[bool], None] | None = None

    @property
    def is_open(self) -> bool:
        """Return True if the transport is currently open."""
        return self._writer is not None

    async def async_open(self) -> None:
        """Open the serial link, raising on failure. Starts the read loop."""
        if self.is_open:
            return
        self._closing = False
        await self._connect()

    async def _connect(self) -> None:
        """Open the underlying serialx connection and start the read loop."""
        try:
            self._reader, self._writer = await serialx.open_serial_connection(
                self._url, baudrate=self._baudrate
            )
        except (serialx.SerialException, OSError, ValueError) as err:
            raise Azur851ConnectionError(f"Could not open {self._url}: {err}") from err
        self._read_task = asyncio.create_task(self._read_loop())
        if self.on_connection_state is not None:
            self.on_connection_state(True)

    async def _read_loop(self) -> None:
        """Read complete frames and dispatch them; reconnect when the link drops."""
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
        self._handle_disconnect()

    def _handle_disconnect(self) -> None:
        """React to the read loop ending: mark down and schedule a reconnect."""
        self._reader = None
        self._writer = None
        if self.on_connection_state is not None:
            self.on_connection_state(False)
        if not self._closing and self._reconnect_task is None:
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff until it succeeds or we close."""
        delay = self._reconnect_initial
        try:
            while not self._closing:
                await asyncio.sleep(delay)
                if self._closing:
                    return
                try:
                    await self._connect()
                except Azur851ConnectionError as err:
                    _LOGGER.debug("Reconnect to %s failed: %s", self._url, err)
                    delay = min(delay * 2, self._reconnect_max)
                else:
                    _LOGGER.info("Reconnected to %s", self._url)
                    return
        finally:
            self._reconnect_task = None

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
        """Stop reconnecting and the read loop, then close the transport."""
        self._closing = True
        for task in (self._reconnect_task, self._read_task):
            if task is not None:
                task.cancel()
        self._reconnect_task = None
        self._read_task = None
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (serialx.SerialException, OSError):
                pass
            self._writer = None
            self._reader = None
