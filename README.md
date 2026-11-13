# Cambridge Audio Azur 851 — Home Assistant Integration

[![CI](https://github.com/errestan/cambridge-audio-azur-851/actions/workflows/ci.yml/badge.svg)](https://github.com/errestan/cambridge-audio-azur-851/actions/workflows/ci.yml)
[![Validate](https://github.com/errestan/cambridge-audio-azur-851/actions/workflows/validate.yml/badge.svg)](https://github.com/errestan/cambridge-audio-azur-851/actions/workflows/validate.yml)
[![Latest release](https://img.shields.io/github/v/release/errestan/cambridge-audio-azur-851?sort=semver)](https://github.com/errestan/cambridge-audio-azur-851/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/github/license/errestan/cambridge-audio-azur-851)](LICENSE)

A custom [Home Assistant](https://www.home-assistant.io/) integration for controlling
**Cambridge Audio Azur 851 series** audio equipment over RS-232 serial.

> **Status:** early but functional. The RS-232 protocol, the `serialx` transport
> (local / `socket://` / ESPHome proxy) with auto-reconnect, the `media_player`
> entity, and the config/reconfigure flows are implemented and unit-tested. Not
> yet validated against real hardware. See [Roadmap](#roadmap).

## Supported hardware (target)

The Azur 851 series shares a common RS-232 control protocol. Target devices:

| Model  | Type                 | Primary platform        |
|--------|----------------------|-------------------------|
| 851A   | Integrated amplifier | `media_player`          |
| 851E   | Preamplifier         | `media_player`          |
| 851W   | Power amplifier      | `media_player` (limited)|
| 851N   | Network player       | `media_player`          |
| 851C   | CD player            | `media_player`          |
| 851D   | DAC / preamplifier   | `media_player`          |

> Initial development targets the **851A** integrated amplifier. Other models are
> handled through per-model capability maps in `azur851/models.py`.

## How it connects

These devices expose a 3-wire RS-232 port. The integration can talk to it over a
**local serial port** or, using **Home Assistant's serial proxy support**
(HA 2026.5+), over the network — so the hardware can live anywhere behind a
serial-to-network bridge (e.g. an ESPHome device, ser2net, or a USB-serial server).

```
+----------------+        network         +------------------+    RS-232    +-----------+
| Home Assistant | <--- serial proxy ---> | serial bridge    | <----------> | Azur 851  |
| (this          |                        | (ser2net /       |              | hardware  |
|  integration)  |                        |  ESPHome / etc.) |              |           |
+----------------+                        +------------------+              +-----------+
```

The transport uses Home Assistant's [`serialx`](https://github.com/puddly/serialx)
library (HA 2026.5+), so a single **Serial URL** selects the backend
transparently — a local port (`/dev/ttyUSB0`), a network bridge
(`socket://host:port`), or an ESPHome serial proxy such as a Home Assistant
Connect AUX-2 (`esphome-hass://…`, picked from Home Assistant's serial port
selector). Because the device pushes state changes
unsolicited, the connection runs a background read loop and the integration is
`local_push`. See [`docs/transport.md`](docs/transport.md) and
[`docs/protocol.md`](docs/protocol.md).

## Architecture

```
custom_components/cambridge_azur851/
├── __init__.py          # Integration setup: config entry load/unload, platform forwarding
├── manifest.json        # Integration metadata & dependencies
├── const.py             # Domain, config keys, supported models
├── config_flow.py       # UI setup + reconfigure flow (serial port selector, model)
├── coordinator.py       # Push coordinator: owns the connection, fans out updates
├── entity.py            # Shared base entity (device info, availability)
├── media_player.py      # MediaPlayerEntity: power, volume, mute, source select
├── strings.json         # UI strings
├── translations/
│   └── en.json
└── azur851/             # Standalone protocol library (no HA imports)
    ├── __init__.py      # Public client API
    ├── connection.py    # serialx transport: read loop, auto-reconnect
    ├── protocol.py      # Frame encode/decode for the Azur RS-232 protocol
    ├── commands.py      # Command & response definitions (command groups)
    ├── models.py        # Per-model capability maps + device state
    └── exceptions.py    # Library exception types
```

**Design principles**

- The `azur851/` package has **no Home Assistant imports** — it is a pure protocol
  client that can be tested and used independently.
- **Push, not poll.** The device emits state changes unsolicited (group-4 frames),
  so a single connection owns the serial link with a background read loop; writes
  are serialized behind a lock. The coordinator turns pushed updates into entity
  state, and a dropped link auto-reconnects with backoff (`local_push`).
- Per-model differences (baud rate, volume range, sources) live in `models.py`,
  keyed by the model selected during config flow.

## Installation

### HACS (custom repository)
1. Add this repository as a custom repository in HACS (category: *Integration*).
2. Install **Cambridge Audio Azur 851**.
3. Restart Home Assistant.
4. *Settings → Devices & Services → Add Integration → Cambridge Audio Azur 851*.

### Manual
Copy `custom_components/cambridge_azur851/` into your Home Assistant `config/custom_components/` directory and restart.

When adding the integration, choose the model and pick the serial port from Home
Assistant's serial port selector. It lists local ports and ESPHome serial proxies
(e.g. a Home Assistant Connect AUX-2) — set the ESPHome device up in Home
Assistant first; the proxy then reuses that already-encrypted connection, so no
key is needed here. You can change either later via the entry's **Reconfigure**
menu.

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.14+
pip install -r requirements_dev.txt
pre-commit install
pytest
```

### Continuous integration

GitHub Actions workflows:

- **CI** (`.github/workflows/ci.yml`) — runs the pre-commit hooks (ruff, ruff-format,
  mypy, file hygiene) and the `pytest` suite on push and PR.
- **Validate** (`.github/workflows/validate.yml`) — runs Home Assistant **hassfest**
  and the **HACS** validation action.
- **Release Please** (`.github/workflows/release-please.yml`) — automates versioning
  and GitHub Releases from Conventional Commits (see
  [`CONTRIBUTING.md`](CONTRIBUTING.md#releases)).

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and the inline `TODO`s for the next implementation steps.

## Roadmap

- [x] Encode the official Azur 851 RS-232 protocol (`protocol.py`, `commands.py`) — see [`docs/protocol.md`](docs/protocol.md)
- [x] Per-model capability maps in `models.py` (851A/851E baud + volume verified)
- [x] Flesh out `media_player.py` (power, volume, mute, source, state mapping)
- [x] Protocol round-trip tests
- [x] Implement `connection.py` transport over `serialx` (open + read loop) — see [`docs/transport.md`](docs/transport.md)
- [x] Push model: unsolicited group-4 updates via a read loop + `local_push` coordinator
- [x] Reconnection / backoff when the serial link drops (entities go unavailable then recover)
- [x] Config flow uses Home Assistant's serial port selector (local ports + ESPHome proxies)
- [x] Reconfigure flow to change the serial port / model later
- [x] Tests: config flow, reconfigure, setup/coordinator/entity
- [x] CI: GitHub Actions (pre-commit lint/type, pytest, hassfest, HACS validation)
- [ ] Validate against real hardware

## License

MIT — see [`LICENSE`](LICENSE).

> Not affiliated with or endorsed by Cambridge Audio.
