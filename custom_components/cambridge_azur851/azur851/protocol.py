"""Frame encoding/decoding for the Cambridge Audio Azur 851 RS-232 protocol.

The Azur 851 series uses a command/response protocol over RS-232. Commands are
grouped (e.g. power, source, volume) and the device replies with status frames.

TODO: Implement against the official "Azur 851 RS-232 control" documentation.
Fill in the framing details below:
  - frame delimiter / terminator (e.g. carriage return)
  - command group + command number layout
  - response/status frame layout and how unsolicited updates look
  - error/NACK responses
"""

from __future__ import annotations

from dataclasses import dataclass

# Frame terminator used by the protocol. TODO: confirm.
TERMINATOR: bytes = b"\r"


@dataclass(frozen=True)
class Command:
    """A command to send to the device (group + command + optional data)."""

    group: int
    number: int
    data: tuple[int, ...] = ()


@dataclass(frozen=True)
class Response:
    """A parsed response/status frame from the device."""

    group: int
    number: int
    data: tuple[int, ...]


def encode(command: Command) -> bytes:
    """Encode a Command into an on-the-wire frame.

    TODO: implement the real framing once the protocol spec is encoded.
    """
    raise NotImplementedError


def decode(frame: bytes) -> Response:
    """Decode a raw response frame into a Response.

    TODO: implement parsing, including validation and error/NACK detection.
    """
    raise NotImplementedError
