"""Transport tests: read loop, push callbacks, and auto-reconnect.

These drive a fake serialx link and do not require real hardware.
"""

from __future__ import annotations

import asyncio

import pytest
import serialx
from custom_components.cambridge_azur851.azur851.connection import Azur851Connection


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
