"""Transport tests: read loop, push callbacks, and auto-reconnect.

These drive a fake serialx link and do not require real hardware.
"""

from __future__ import annotations

import asyncio

import pytest
import serialx
from custom_components.cambridge_azur851.azur851 import Azur851Client
from custom_components.cambridge_azur851.azur851.connection import Azur851Connection
from custom_components.cambridge_azur851.azur851.exceptions import (
    Azur851ConnectionError,
    Azur851NoResponseError,
)


class _FakeWriter:
    """Minimal stand-in for serialx's stream writer."""

    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass


@pytest.fixture
def fake_serial(monkeypatch: pytest.MonkeyPatch):
    """Patch serialx.open_serial_connection to hand out controllable readers."""
    readers: list[asyncio.StreamReader] = []
    calls = {"count": 0}

    def _open(url: str, baudrate: int | None = None):
        async def _connect():
            calls["count"] += 1
            reader = asyncio.StreamReader()
            readers.append(reader)
            return reader, _FakeWriter()

        return _connect()

    monkeypatch.setattr(serialx, "open_serial_connection", _open)
    return readers, calls


async def test_read_loop_delivers_frames(fake_serial) -> None:
    """Complete frames are pushed to on_frame."""
    readers, _ = fake_serial
    frames: list[bytes] = []
    conn = Azur851Connection("fake://x", 9600)
    conn.on_frame = frames.append

    await conn.async_open()
    readers[-1].feed_data(b"#4,13,15\r")
    await asyncio.sleep(0.02)
    await conn.async_close()

    assert frames == [b"#4,13,15\r"]


async def test_reconnect_after_drop(fake_serial) -> None:
    """A dropped link is detected and reconnected, toggling connection state."""
    readers, calls = fake_serial
    states: list[bool] = []
    conn = Azur851Connection(
        "fake://x", 9600, reconnect_initial=0.01, reconnect_max=0.02
    )
    conn.on_connection_state = states.append

    await conn.async_open()
    assert calls["count"] == 1

    readers[-1].feed_eof()  # simulate the link dropping
    await asyncio.sleep(0.08)

    assert calls["count"] >= 2
    assert conn.is_open
    assert states[0] is True and False in states and states[-1] is True

    await conn.async_close()


async def test_close_stops_reconnect(fake_serial) -> None:
    """Deliberate close must not schedule further reconnects."""
    readers, calls = fake_serial
    conn = Azur851Connection(
        "fake://x", 9600, reconnect_initial=0.01, reconnect_max=0.02
    )
    await conn.async_open()
    await conn.async_close()

    count_after_close = calls["count"]
    await asyncio.sleep(0.05)

    assert conn._closing is True
    assert conn.is_open is False
    assert calls["count"] == count_after_close


async def test_open_wraps_non_serial_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any open failure (e.g. ESPHome not loaded yet) becomes a connection error."""

    async def _open(url: str, baudrate: int | None = None):
        raise RuntimeError("ESPHome has not loaded yet")

    monkeypatch.setattr(serialx, "open_serial_connection", _open)
    conn = Azur851Connection("esphome-hass://esphome/abc?port_name=851A", 9600)

    with pytest.raises(Azur851ConnectionError):
        await conn.async_open()
    assert conn.is_open is False


@pytest.mark.parametrize(
    "reply",
    [b"#3,02,2.4\r", b"#5,08\r"],
    ids=["protocol-version", "error-frame"],
)
async def test_test_connection_succeeds_on_reply(
    fake_serial, monkeypatch: pytest.MonkeyPatch, reply: bytes
) -> None:
    """Any valid frame (even a group-5 error) proves the device is there."""
    readers, _ = fake_serial
    # The "device" answers whatever is written to it.
    monkeypatch.setattr(
        _FakeWriter, "write", lambda self, data: readers[-1].feed_data(reply)
    )
    client = Azur851Client(Azur851Connection("fake://x", 9600), "851A")

    await client.async_test_connection()

    assert client.is_open is False  # the probe link is closed afterwards


async def test_test_connection_no_response(fake_serial) -> None:
    """A silent device raises Azur851NoResponseError and the link is closed."""
    client = Azur851Client(Azur851Connection("fake://x", 9600), "851A")

    with pytest.raises(Azur851NoResponseError):
        await client.async_test_connection(response_timeout=0.05)
    assert client.is_open is False
