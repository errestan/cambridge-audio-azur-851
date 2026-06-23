"""Transport tests: read loop, push callbacks, and auto-reconnect.

These drive a fake serialx link and do not require real hardware.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from types import SimpleNamespace

import pytest
import serialx
from custom_components.cambridge_azur851.azur851.connection import (
    Azur851Connection,
    async_discover_ports,
    build_serial_url,
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


async def test_discover_ports_dedup_and_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery merges platforms, dedups by device, and builds labels."""
    device = SimpleNamespace(
        device="/dev/ttyUSB0",
        resolved_device="/dev/ttyUSB0",
        manufacturer="FTDI",
        product="FT232R",
        description="ttyUSB0",
    )
    proxy = SimpleNamespace(
        device="esphome://1.2.3.4:6053/?port_name=851A",
        resolved_device="esphome://1.2.3.4:6053/?port_name=851A",
        manufacturer=None,
        product=None,
        description="851A",
    )

    async def _list(platform):
        if platform is serialx.Platform.DEVICE:
            return [device, device]  # duplicate to exercise dedup
        if platform is serialx.Platform.ESPHOME:
            return [proxy]
        return []

    monkeypatch.setattr(serialx, "async_list_serial_ports", _list)
    ports = await async_discover_ports()

    assert [p.device for p in ports] == [
        "/dev/ttyUSB0",
        "esphome://1.2.3.4:6053/?port_name=851A",
    ]
    assert ports[0].label == "FTDI FT232R (/dev/ttyUSB0)"
    assert ports[1].label == "851A (esphome://1.2.3.4:6053/?port_name=851A)"


async def test_discover_ports_swallows_platform_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A platform with no registered handler is skipped, not fatal."""

    async def _list(platform):
        if platform is serialx.Platform.DEVICE:
            return [
                SimpleNamespace(
                    device="/dev/ttyS0",
                    description="ttyS0",
                    manufacturer=None,
                    product=None,
                )
            ]
        raise serialx.SerialException("no handler for this scheme")

    monkeypatch.setattr(serialx, "async_list_serial_ports", _list)
    ports = await async_discover_ports()

    assert [p.device for p in ports] == ["/dev/ttyS0"]


def _query(url: str) -> dict[str, str]:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


def test_build_serial_url_adds_key_to_esphome() -> None:
    """An ESPHome URL gains the key as a query parameter, keeping port_name."""
    url = build_serial_url("esphome://1.2.3.4:6053/?port_name=851A", "SECRET_PSK")
    query = _query(url)
    assert query == {"port_name": "851A", "key": "SECRET_PSK"}
    assert url.startswith("esphome://1.2.3.4:6053/")


def test_build_serial_url_no_key_is_unchanged() -> None:
    """A blank/absent key leaves the URL alone."""
    url = "esphome://1.2.3.4:6053/?port_name=851A"
    assert build_serial_url(url, None) == url
    assert build_serial_url(url, "") == url


def test_build_serial_url_ignores_non_esphome() -> None:
    """The key only applies to esphome:// URLs."""
    for url in ("/dev/ttyUSB0", "socket://192.168.1.50:4001"):
        assert build_serial_url(url, "SECRET_PSK") == url


def test_build_serial_url_preserves_existing_key() -> None:
    """An explicit key already in the URL is not overwritten."""
    url = "esphome://1.2.3.4/?port_name=851A&key=INLINE"
    assert _query(build_serial_url(url, "OTHER"))["key"] == "INLINE"
