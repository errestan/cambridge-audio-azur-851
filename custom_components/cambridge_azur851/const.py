"""Constants for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "cambridge_azur851"

MANUFACTURER: Final = "Cambridge Audio"

# --- Config entry keys -----------------------------------------------------
CONF_MODEL: Final = "model"
CONF_HOST: Final = "host"          # serial-proxy / network bridge host
CONF_PORT: Final = "port"          # serial-proxy / network bridge TCP port
CONF_SERIAL_URL: Final = "serial_url"  # alternative: explicit serial/socket URL

# --- Defaults --------------------------------------------------------------
# RS-232 line settings for the Azur 851 series.
# TODO: confirm against the official RS-232 documentation.
DEFAULT_BAUDRATE: Final = 9600
DEFAULT_PORT: Final = 4001
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 30
DEFAULT_TIMEOUT_SECONDS: Final = 5

# --- Supported models ------------------------------------------------------
MODEL_851A: Final = "851A"
MODEL_851E: Final = "851E"
MODEL_851W: Final = "851W"
MODEL_851N: Final = "851N"
MODEL_851C: Final = "851C"
MODEL_851D: Final = "851D"

SUPPORTED_MODELS: Final = [
    MODEL_851A,
    MODEL_851E,
    MODEL_851W,
    MODEL_851N,
    MODEL_851C,
    MODEL_851D,
]
