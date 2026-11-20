"""Constants for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "cambridge_azur851"

MANUFACTURER: Final = "Cambridge Audio"

# --- Config entry keys -----------------------------------------------------
CONF_MODEL: Final = "model"
# A serialx URL as returned by Home Assistant's serial port selector: a local
# path (/dev/ttyUSB0), an ESPHome serial proxy (esphome-hass://...), or a typed
# socket:// / esphome:// URL. Passed straight to serialx.open_serial_connection.
CONF_SERIAL_URL: Final = "serial_url"

# --- Defaults --------------------------------------------------------------
# Baud is model-dependent (851A/851D=9600, 851E=115200); the authoritative
# per-model values live in azur851/models.py. This is only a fallback for
# unknown models. All models use 8 data bits, no parity, 1 stop bit, no
# handshake.
DEFAULT_BAUDRATE: Final = 9600

# --- Supported models ------------------------------------------------------
# Only models whose command map has been checked against Cambridge Audio's
# official serial protocol documents are offered during setup. The 851W/N/C
# use separate command sets that are not implemented yet (see docs/protocol.md).
MODEL_851A: Final = "851A"
MODEL_851E: Final = "851E"
MODEL_851D: Final = "851D"

SUPPORTED_MODELS: Final = [MODEL_851A, MODEL_851E, MODEL_851D]
