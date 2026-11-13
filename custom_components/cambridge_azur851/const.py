"""Constants for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "cambridge_azur851"

MANUFACTURER: Final = "Cambridge Audio"

# --- Config entry keys -----------------------------------------------------
CONF_MODEL: Final = "model"
# A serialx URL: a local path (/dev/ttyUSB0), a socket:// bridge, or an
# esphome:// serial proxy. Passed straight to serialx.open_serial_connection.
CONF_SERIAL_URL: Final = "serial_url"
# Optional ESPHome API encryption key (Noise PSK), folded into an esphome:// URL
# as the `key=` query parameter. Ignored for non-esphome URLs.
CONF_KEY: Final = "encryption_key"

# --- Defaults --------------------------------------------------------------
# Baud is model-dependent (851A=9600, 851E=115200, ...); the authoritative
# per-model values live in azur851/models.py. This is only a fallback for
# unknown models. All models use 8 data bits, no parity, 1 stop bit, no
# handshake.
DEFAULT_BAUDRATE: Final = 9600

# --- Supported models ------------------------------------------------------
# Only models whose command map has been checked against Cambridge Audio's
# official serial protocol documents are offered during setup. The 851W/N/C/D
# use separate command sets that are not implemented yet (see docs/protocol.md).
MODEL_851A: Final = "851A"
MODEL_851E: Final = "851E"

SUPPORTED_MODELS: Final = [MODEL_851A, MODEL_851E]
