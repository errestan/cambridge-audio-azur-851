# Azur 851 RS-232 Protocol — Reference Notes

Working notes on the Cambridge Audio Azur 851 serial control protocol, distilled
from the official documents and used to implement `custom_components/cambridge_azur851/azur851/`.

## Sources

- **851A Serial Control Protocol V1.0** (PDF):
  <https://www.cambridgeaudio.com/sites/default/files/compliance/doc/Azur%20851A%20Serial%20Protocol%20V1.0.pdf>
- **851E Serial Control Protocol V2.0** (PDF):
  <https://www.cambridgeaudio.com/sites/default/files/compliance/doc/Azur%20851E%20RS232%20Protocol.pdf>
- **851D Serial Control Protocol v1.0** (PDF, 2014; on Cambridge's support
  archive, which sits behind a browser check):
  <https://supportarchive.cambridgeaudio.com/hc/en-us/article_attachments/360000079398>
- Per-model RS232 code pages (support portal):
  [851A](https://techsupport.cambridgeaudio.com/hc/en-us/articles/200945322-Azur-851A-RS232-Codes) ·
  [851C](https://techsupport.cambridgeaudio.com/hc/en-us/articles/201716511-Azur-851C-RS232-Codes) ·
  [851N](https://techsupport.cambridgeaudio.com/hc/en-us/articles/202566031-Azur-851N-RS232-Codes)

> The 851A V1.0 spec is itself based on the Azur 840A/840E protocol, so other
> Azur models are often close but **not identical** — always confirm per model.

## Serial port settings

Accessed via the rear-panel RS-232C port (COM1). 8 data bits, no parity, 1 stop
bit, no handshake. Baud rate is **model-dependent**:

| Model | Baud | Volume range | Notes |
|-------|------|--------------|-------|
| 851A  | 9600 | `00`–`96` | Has speaker select, bass, treble, A-BUS |
| 851E  | 115200 (default; also 38400 / 9600) | `00`–`91` | Pre-amp; no tone controls |
| 851D  | 9600 | `000`–`096` attenuation (`000` = 0 dB, loudest) | DAC / preamp; its own command set — see [851D](#851d--a-separate-command-set) |
| 851W / 851N / 851C | TBD | TBD | Separate command sets — consult their code pages |

## Frame format

All frames are ASCII, one per line:

```
#<group>,<NN>,<data><CR>
```

| Field | Bytes | Notes |
|-------|-------|-------|
| Header | 1 | `#` (0x23) |
| Group | 1 | single digit, `1`–`5` |
| Separator | 1 | `,` |
| Command number | 2 | zero-padded, e.g. `01`, `13` |
| Separator | 1 | `,` |
| Data | 0–10 | optional; **may contain commas** (e.g. `3,iPod`) |
| Footer | 1 | `CR` = `0x0D` |

Examples: `#1,11,0\r` (standby), `#1,13,10\r` (volume → 10), `#4,12,1\r` (mute-on update).

> Some 851E examples omit the trailing separator when there is no data
> (`#1,09\r`). The decoder tolerates this; the encoder always emits both
> separators per the 851A frame table.

## Command groups

| Group | Direction | Meaning |
|-------|-----------|---------|
| 1 | → device | Control commands |
| 2 | → device | Setup commands (queries / config) |
| 3 | ← device | Replies to setup commands |
| 4 | ← device | Replies to control commands **and unsolicited state updates** |
| 5 | ← device | Error messages |

## Group 1 — control commands (851A)

| # | Command | Data |
|---|---------|------|
| 01–07 | Main input select (1–7) | opt. `1` = balanced, `0` = unbalanced (dual-socket inputs only — 851A: 1 & 2; 851E: 1–3). No data = unbalanced on the 851A but **toggle** on the 851E |
| 08 | Tape monitor | `0` off / `1` on |
| 09 / 10 | Input up / down | — |
| 11 | Power | `0` standby / `1` on |
| 12 | **Mute** | `0` = **mute ON**, `1` = **mute OFF** ⚠️ inverted |
| 13 | Set volume | `00`–`96` |
| 14 / 15 / 16 | Volume up / down / stop | — (ramps until stop) |
| 17 | Set balance | `00`–`16` (`08` = centre) |
| 18 / 19 | Balance right / left | — |
| 20 | LCD brightness | `0` off / `1` dim / `2` bright |
| 21 | Speaker select | `0` A / `1` AB / `2` B (851A only) |
| 24 | Set bass | `00`–`30` (`15` = neutral) (851A only) |
| 25 | Set treble | `00`–`30` (`15` = neutral) (851A only) |
| 26 | Set direct | `0` off / `1` on |

## Group 2 — setup commands

| # | Command | Data |
|---|---------|------|
| 01 | Get software version | — → `#3,01,X.Y` |
| 02 | Get protocol version | — → `#3,02,X.Y` |
| 03 | Set input name | `<1–8>,<name>` |

## Group 4 — replies / unsolicited updates

Mirror the control commands and are emitted **whenever state changes** (e.g. via
the front panel or remote), not only in response to our commands.

| # | Update | Data |
|---|--------|------|
| 01–07 | Input changed | as per select |
| 11 | Power changed | `0` standby / `1` on |
| 12 | **Mute changed** | `0` = mute OFF, `1` = mute ON ⚠️ (opposite of the #12 *control* encoding) |
| 13 | Volume changed | `00`–`96` |
| 16 | Volume stopped (at) | `00`–`96` |
| 17 | Balance changed | `00`–`16` |
| 20 | LCD brightness changed | `0/1/2` |
| 22 | Headphones in/out | `0` out / `1` in |
| 23 | A-BUS input changed | `1`–`8` |
| 24 / 25 | Bass / treble changed | `00`–`30` |
| 26 | Direct changed | `0/1` |

## Group 5 — errors

`07` unknown command group · `08` unknown command number · `09` data error.
851A also reports hardware faults: `01` overload · `02` DC offset · `03`
over-temperature · `04` clipping · `05` mains fail · `06` speaker fail.

## 851D — a separate command set

The 851D shares the frame format but little else. Implemented in
`azur851/commands_851d.py` and `DacCommandSet` in `azur851/command_sets.py`.

- **Groups:** 1 control, 2 setup, **3 control replies**, **4 setup replies**,
  5 errors. (The amps reply to control commands on group 4.)
- **Errors:** `01` unknown group · `02` unknown command number · `03` data
  error. (The document's table says `04`, its example `#5,03`.)

| # | Command | Data | Reply |
|---|---------|------|-------|
| 01 | Select source | `1`–`8` | `#3,01,x` |
| 02 / 03 | Next / previous source | – | `#3,01,x` |
| 04 / 05 | Get input word width / sample rate | – | `#3,04,xx` / `#3,05,xx` |
| 12 | Get volume | – | `#3,12,xxx` |
| 13 | Set volume | `000`–`096` | `#3,13,xxx` |
| 14 | Power | `0` standby / `1` on | `#3,14,x` |
| 15 | LCD brightness | `0` off / `1` dim / `2` bright | `#3,15,x` |
| 22 | Headphones (reply only) | `0` out / `1` in | `#3,22,x` |
| 40 | Select filter | `x[,y]`: `1` linear / `2` minimum / `3` steep; `y` `0` normal / `1` inverted phase (omit to keep) | `#3,41,x,y` |
| 41 | Get filter | – | `#3,41,x,y` |
| 42 / 43 | Volume up / down | – | `#3,42,xxx` / `#3,43,xxx` |
| 44 / 45 | Mute / unmute | – | `#3,44,` / `#3,45,` |
| 46 | Set balance | `00`–`16` | `#3,46,xx` |
| 47 / 48 | Balance right / left | – | `#3,47,xx` / `#3,48,xx` |
| 49 | Trigger out | `0` low / `1` high | `#3,49,x` |
| 50 / 52 / 53 | Get headphone volume / up / down | – | `#3,5x,xxx` |

Setup (group 2, replies on group 4): `01` software version, `02` DSP version,
`04` set source name (`x,name`, 8 chars), `05` get source name.

Sources: 1–4 Input 1–4, 5 BNC, 6 AES/EBU, 7 Bluetooth, 8 USB.

Unlike the amps, volume and filter **can be read back** (`#1,12,` and
`#1,41,`), so both are requested on every (re)connect. Power, mute, source,
balance and brightness have no "get" and are learned from replies as on the
amps. Setting the phase needs the current filter, since one command carries
both.

**Real-851D behaviour (tested on hardware):**

- It sends replies **unprompted** when power, source or filter change from the
  front panel or remote, so it is push-capable like the amps.
- Filter changes are reported as `#3,40,x,y`, not `#3,41,x,y` as documented.
  Both are handled.
- The filter and phase are **remembered per input**: after every source change
  it reports the new input's filter (`#3,40,x,y`, twice).
- It sometimes sends a NUL byte before a frame (`\x00#3,14,0`); the decoder
  strips it.

## Implementation implications

- **Push, not poll.** There is no "read all state" command — current values are
  learned only from group-4 updates, so the integration holds the serial link
  open and a read loop in `connection.py` feeds unsolicited frames to
  `Azur851Client.apply_update()` (`iot_class: local_push`).
- **Learning state on connect.** Only volume can be read on demand: *Volume
  stop* (`#1,16,`) is a no-op when no ramp is running and is answered with
  `#4,16,<level>`. It is sent on every (re)connect. Power, mute and source stay
  unknown until the device reports a change — we never send a command that would
  change them just to learn their value.
- **Balanced inputs are separate sources.** Dual-socket inputs appear twice in
  the source list ("Input 1", "Input 1 (Balanced)") and are always selected
  with explicit data (`0`/`1`), never with no data, which would silently pick
  the unbalanced socket (851A) or toggle it (851E). Updates report the socket
  as `#4,01,1` (balanced) or `#4,01,` (unbalanced).
- **Settings are push-only too.** Balance, speakers, display brightness,
  Direct and tape monitor are learned from their `#4` updates. On power-on a
  real 851A sends `#4,20` (brightness) and `#4,21` (speakers) unprompted, so
  those two become known whenever the amp is switched on. Until one arrives, the
  entity shows its pre-restart value as an assumed state (`RestoreEntity`).
  Balance is shown centred on zero (device value − 8).
- **Bass/treble (#24/#25) don't work on a real 851A.** It answers both with
  `#5,08` (unknown command number) and never sends `#4,24`/`#4,25`, despite
  the V1.0 document listing them. They are not exposed.
- **No-data frames keep the trailing separator**: e.g. `#1,16,\r`, `#2,01,\r`,
  as in the official examples.
- **Mute inversion** differs between the control command (#12, `0` = on) and the
  update (#12, `1` = on). Handled in `commands.mute()` and `Client.apply_update()`.
- **Per-model baud & volume range** live in `azur851/models.py`, keyed by model.
- **Data may contain commas** (Set Input Name), so the decoder splits with
  `maxsplit=2`.
