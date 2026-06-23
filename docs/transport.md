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
| ESPHome serial proxy | `esphome://<host>:6053/?port_name=<name>` |

For the ESPHome proxy, `6053` is the Native API port and `port_name` matches the
`name:` of the `serial_proxy:` block in the ESPHome YAML. Authentication
(API encryption key / password) is carried as additional URL parameters.

> ⚠️ The exact ESPHome-proxy query-parameter names (auth key etc.) should be
> confirmed against the serialx docs for the version bundled with the target HA
> release before relying on them in production.

### ESPHome side (proxy device YAML)

```yaml
uart:
  - id: device_uart
    tx_pin: GPIO4
    rx_pin: GPIO5
    baud_rate: 9600   # match the model: 851A=9600, 851E=115200

api:

serial_proxy:
  - id: device_serial
    uart_id: device_uart
    name: 851A           # -> ?port_name=851A
    port_type: TTL
```

## How this integration uses it

- The config flow takes a single **Serial URL** (any of the forms above) plus the
  model; `Azur851Client.from_config` builds the connection with the model's baud.
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

## Remaining work

- **Config-flow selector:** use `async_list_serial_ports()` to offer a dropdown of
  discovered local/proxied ports instead of a free-text URL.
- **Auth params:** confirm and document the ESPHome proxy auth URL parameters.
