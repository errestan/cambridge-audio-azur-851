# Transport — serialx & Home Assistant serial proxies

How the integration actually moves bytes to the device, and the research behind it.

## Background

Home Assistant **2026.5** migrated serial handling to a new async-first library,
[`serialx`](https://github.com/puddly/serialx) (by puddly), and added **serial
proxy** support: an ESPHome device wired to the equipment's RS-232 port relays the
serial link over the network via the ESPHome Native API. Home Assistant also
gained a UI selector for both local and remote serial ports.

This means the equipment no longer needs to be physically attached to the Home
Assistant host — it can sit anywhere on the network behind an ESPHome proxy (or a
`ser2net`/`socat` bridge).

Sources:
- HA 2026.5 release notes: <https://www.home-assistant.io/blog/2026/05/06/release-20265/>
- Dev blog "Serious about serial: migrating from pyserial to serialx":
  <https://developers.home-assistant.io/blog/2026/04/27/pyserial-to-serialx/>
- serialx: <https://github.com/puddly/serialx>
- ESPHome `serial_proxy` component: <https://esphome.io/components/serial_proxy/>

## serialx API (verified against serialx 1.8.2)

```python
import serialx

# Async: returns an asyncio (StreamReader, SerialStreamWriter) pair.
reader, writer = await serialx.open_serial_connection(url, baudrate=9600)

writer.write(b"#1,11,1\r")
await writer.drain()
frame = await reader.readuntil(b"\r")

writer.close()
await writer.wait_closed()
```

- `serialx.open_serial_connection(url, **kwargs)` — async; the URL selects the
  backend transparently. This is what `azur851/connection.py` uses.
- `serialx.serial_for_url(url, baudrate=...)` — synchronous equivalent.
- `serialx.SerialException` — error type (caught alongside `OSError`).
- `serialx.async_list_serial_ports()` / `list_serial_ports()` — enumerate ports
  (local + proxied); useful for a future config-flow selector.

## URL forms

| Connection | URL example |
|------------|-------------|
| Local serial port | `/dev/ttyUSB0`, `/dev/serial/by-id/...` |
| Network bridge (ser2net/socat) | `socket://192.168.1.50:4001` |
| ESPHome serial proxy (via HA) | `esphome-hass://esphome/<esphome_entry_id>?port_name=<name>` |
| ESPHome serial proxy (direct) | `esphome://<host>[:6053]/?port_name=<name>[&key=<noise_psk>]` |

**Use `esphome-hass://` under Home Assistant.** Home Assistant's ESPHome
integration registers this scheme with serialx: it opens the proxy over HA's
*existing* ESPHome API connection for that config entry, so it is already
authenticated. HA's `SerialPortSelector` returns these URLs for proxy ports. The
raw `esphome://` form opens a **second** API connection; against a device with
API encryption (e.g. a Home Assistant Connect AUX-2) it fails with "Connection
requires encryption" unless the `key=` is supplied. Until the ESPHome integration
has loaded, the `usb` integration's stub handler raises `ConfigEntryNotReady`.

ESPHome proxy URL parameters, verified from the serialx source
(`serialx/platforms/serial_esphome.py`, v1.8.2):

| Part | Meaning |
|------|---------|
| `<host>` | ESPHome device hostname/IP (required) |
| port | Native API port; defaults to **6053** if omitted |
| `port_name` | the `name:` of the `serial_proxy:` block in the ESPHome YAML |
| `key` | **API encryption key (Noise PSK)** — the auth parameter; `noise_psk` is an accepted alias |
| `password` | legacy API password (deprecated in ESPHome; prefer `key`) |

So an encrypted proxy is addressed as:

```
esphome://192.168.1.42:6053/?port_name=851A&key=<base64-noise-psk>
```

This direct form is only needed outside Home Assistant (or for a proxy HA does
not manage); under HA prefer the `esphome-hass://` URL from the port selector.

### ESPHome side (proxy device YAML)

```yaml
uart:
  - id: device_uart
    tx_pin: GPIO4
    rx_pin: GPIO5
    baud_rate: 9600   # match the model: 851A=9600, 851E=115200

api:
  encryption:
    key: !secret api_encryption_key   # this value goes in the `key=` URL param

serial_proxy:
  - id: device_serial
    uart_id: device_uart
    name: 851A           # -> ?port_name=851A
    port_type: TTL
```

## How this integration uses it

- The config flow takes a single **Serial URL** (any of the forms above) plus the
  model; `Azur851Client.from_config` builds the connection with the model's baud.
  Before creating the entry it **probes the device**: it sends *Get protocol
  version* (`#2,02`) and waits up to 2 s for any valid frame. If the port opens
  but nothing answers, the flow shows **no_response** (distinct from
  **cannot_connect**) -- that points at wiring, the wrong port, or the wrong
  model/baud rather than at the serial proxy.
- `Azur851Connection` opens the link with `open_serial_connection`, then runs a
  **background read loop** (`reader.readuntil(b"\r")`) that pushes each complete
  frame to the client. This matches the push nature of the protocol (group-4
  updates arrive unsolicited). See [`protocol.md`](protocol.md).
- The client decodes frames, updates `DeviceState`, and fires `on_update`; the
  coordinator turns that into `async_set_updated_data` (hence `iot_class:
  local_push`, no polling interval).

## Reconnection

The initial `async_open()` raises on failure so setup can report `cannot_connect`.
Once open, if the read loop ends unexpectedly (EOF or I/O error) the connection:

1. clears the reader/writer and fires `on_connection_state(False)` — the
   coordinator calls `async_set_update_error`, so entities go **unavailable**;
2. starts a background reconnect task that retries with **exponential backoff**
   (2s, doubling, capped at 60s) until it succeeds or the entry is unloaded;
3. on success, restarts the read loop and fires `on_connection_state(True)`, so
   entities become available again.

A deliberate `async_close()` sets a closing flag and cancels both the read and
reconnect tasks, so unloading never triggers a reconnect.

## Port selection (config flow)

The config flow uses Home Assistant's built-in `SerialPortSelector` (as core
RS-232 integrations such as `denon_rs232` do), which lists local ports and
ESPHome serial proxy ports. The manifest depends on `usb`, which provides the
selector's backend and the `esphome-hass://` stub handler.

## Changing the connection later

The integration supports Home Assistant's **reconfigure** flow (the entry's
"Reconfigure" menu): the same form is shown pre-filled with the current model and
URL, so the serial port or model can be changed and re-validated
without removing and re-adding the device.
