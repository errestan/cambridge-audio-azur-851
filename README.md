# Cambridge Audio Azur 851 — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for controlling
**Cambridge Audio Azur 851 series** audio equipment over RS-232 serial.

> **Status:** project outline / template. The serial protocol layer and entity
> behaviour are stubbed and marked with `TODO`. See [Roadmap](#roadmap).

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

These devices expose a 3-wire RS-232 port. Rather than requiring the serial port to
be physically attached to the Home Assistant host, this integration connects through
**Home Assistant's serial proxy support** (network-shared serial ports). This lets the
hardware live anywhere on the network behind a serial-to-network bridge (e.g. an
ESPHome device, ser2net, or a USB-serial server).

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
(`socket://host:port`), or an ESPHome serial proxy
(`esphome://host:6053/?port_name=851A`). Because the device pushes state changes
unsolicited, the connection runs a background read loop and the integration is
`local_push`. See [`docs/transport.md`](docs/transport.md) and
[`docs/protocol.md`](docs/protocol.md).

## Architecture

```
custom_components/cambridge_azur851/
├── __init__.py          # Integration setup: config entry load/unload, platform forwarding
├── manifest.json        # Integration metadata & dependencies
├── const.py             # Domain, defaults, config keys
├── config_flow.py       # UI-driven setup (connection details, model selection)
├── coordinator.py       # DataUpdateCoordinator: polls device state, pushes updates
├── entity.py            # Shared base entity (device info, availability)
├── media_player.py      # MediaPlayerEntity: power, volume, mute, source select
├── strings.json         # UI strings
├── translations/
│   └── en.json
└── azur851/             # Standalone protocol library (no HA imports)
    ├── __init__.py      # Public client API
    ├── connection.py    # Transport: serial-proxy / serial I/O
    ├── protocol.py      # Frame encode/decode for the Azur RS-232 protocol
    ├── commands.py      # Command & response definitions (command groups)
    └── models.py        # Per-model capability maps
```

**Design principles**

- The `azur851/` package has **no Home Assistant imports** — it is a pure protocol
  client that can be tested and used independently.
- All device polling goes through a single `DataUpdateCoordinator` so the serial link
  is accessed serially (one in-flight request at a time).
- Per-model differences (which commands/sources exist) live in `models.py`, keyed by
  the model selected during config flow.

## Installation (planned)

### HACS (custom repository)
1. Add this repository as a custom repository in HACS (category: *Integration*).
2. Install **Cambridge Audio Azur 851**.
3. Restart Home Assistant.
4. *Settings → Devices & Services → Add Integration → Cambridge Audio Azur 851*.

### Manual
Copy `custom_components/cambridge_azur851/` into your Home Assistant `config/custom_components/` directory and restart.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
pytest
```

See [`CONTRIBUTING`](#) and the inline `TODO`s for the next implementation steps.

## Roadmap

- [x] Encode the official Azur 851 RS-232 protocol (`protocol.py`, `commands.py`) — see [`docs/protocol.md`](docs/protocol.md)
- [x] Per-model capability maps in `models.py` (851A/851E baud + volume verified)
- [x] Flesh out `media_player.py` (power, volume, mute, source, state mapping)
- [x] Protocol round-trip tests
- [x] Implement `connection.py` transport over `serialx` (open + read loop) — see [`docs/transport.md`](docs/transport.md)
- [x] Push model: unsolicited group-4 updates via a read loop + `local_push` coordinator
- [x] Reconnection / backoff when the serial link drops (entities go unavailable then recover)
- [x] Config-flow port selector (discovered local/proxy ports + free-text URL)
- [ ] Confirm ESPHome serial-proxy auth URL parameters
- [ ] Reauth/options flow to change the URL later
- [ ] Validate against real hardware
- [ ] Tests: config flow, coordinator
- [ ] HACS validation & GitHub Actions (hassfest, HACS action)

## License

MIT — see [`LICENSE`](LICENSE).

> Not affiliated with or endorsed by Cambridge Audio.
