"""Exceptions for the Azur 851 client library."""

from __future__ import annotations


class Azur851Error(Exception):
    """Base error for the Azur 851 client."""


class Azur851ConnectionError(Azur851Error):
    """Raised when the transport cannot reach the device."""


class Azur851NoResponseError(Azur851ConnectionError):
    """Raised when the port opens but the device does not answer a probe.

    Usually wiring (TX/RX swapped, wrong cable), the wrong port, or a baud-rate
    mismatch -- the link to the serial adapter/proxy itself is fine.
    """


class Azur851ProtocolError(Azur851Error):
    """Raised when a frame cannot be parsed."""


class Azur851CommandError(Azur851ProtocolError):
    """Raised when the device returns a group-5 error frame.

    The ``number`` attribute holds the device's error command number, e.g.
    ``07`` (unknown group), ``08`` (unknown command), ``09`` (data error).
    """

    def __init__(self, number: int, message: str | None = None) -> None:
        """Store the error number from the device's group-5 reply."""
        self.number = number
        super().__init__(message or f"Device returned error #5,{number:02d}")
