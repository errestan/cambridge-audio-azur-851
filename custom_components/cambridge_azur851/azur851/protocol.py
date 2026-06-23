"""Frame encoding/decoding for the Cambridge Audio Azur 851 RS-232 protocol.

Frame format (all ASCII, one frame per line)::

    #<group>,<NN>,<data><CR>

  - ``#``    header (0x23)
  - group    single digit (see ``commands.Group``)
  - ``,``    field separator (0x2C)
  - NN       two-digit, zero-padded command number
  - ``,``    field separator
  - data     optional, command-dependent; may itself contain commas
             (e.g. the "Set Input Name" command ``#2,03,3,iPod``); max 10 chars
  - <CR>     carriage return terminator, 0x0D

Commands are sent on group 1 (control) / group 2 (setup). The device answers on
group 3 (setup replies), group 4 (control replies + unsolicited updates) and
group 5 (errors). See ``docs/protocol.md`` for the full command reference.
"""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import Azur851ProtocolError

HEADER: str = "#"
SEPARATOR: str = ","
TERMINATOR: str = "\r"
ENCODING: str = "ascii"

# Group reserved for error replies (kept here to avoid a commands<->protocol cycle).
_ERROR_GROUP: int = 5

# A frame has at least group+number, and at most group+number+data.
_MIN_FIELDS: int = 2
_MAX_FIELDS: int = 3


@dataclass(frozen=True)
class Command:
    """A command to send to the device."""

    group: int
    number: int
    data: str = ""


@dataclass(frozen=True)
class Response:
    """A parsed frame received from the device (reply, update, or error)."""

    group: int
    number: int
    data: str = ""

    @property
    def is_error(self) -> bool:
        """Return True if this is a group-5 error frame."""
        return self.group == _ERROR_GROUP


def encode(command: Command) -> bytes:
    """Encode a :class:`Command` into an on-the-wire frame."""
    frame = (
        f"{HEADER}{command.group}{SEPARATOR}"
        f"{command.number:02d}{SEPARATOR}{command.data}{TERMINATOR}"
    )
    return frame.encode(ENCODING)


def decode(frame: bytes | str) -> Response:
    """Decode a raw frame into a :class:`Response`.

    Tolerant of a missing trailing data separator (some models omit it when
    there is no data) and preserves commas inside the data field.
    """
    text = frame.decode(ENCODING) if isinstance(frame, bytes | bytearray) else frame
    text = text.strip("\r\n")

    if not text.startswith(HEADER):
        raise Azur851ProtocolError(f"Frame missing '{HEADER}' header: {text!r}")

    # maxsplit=2 keeps any commas that belong to the data field.
    parts = text[len(HEADER) :].split(SEPARATOR, _MAX_FIELDS - 1)
    if len(parts) < _MIN_FIELDS:
        raise Azur851ProtocolError(f"Frame missing group/number: {text!r}")

    try:
        group = int(parts[0])
        number = int(parts[1])
    except ValueError as err:
        raise Azur851ProtocolError(f"Non-numeric group/number: {text!r}") from err

    data = parts[2] if len(parts) == _MAX_FIELDS else ""
    return Response(group=group, number=number, data=data)
