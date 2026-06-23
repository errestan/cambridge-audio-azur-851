# Contributing

Thanks for your interest in improving the Cambridge Audio Azur 851 integration!

## Development setup

Requires **Python 3.14+** (the pinned Home Assistant test release needs it).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
pre-commit install        # run the hooks automatically on each commit
```

## Day-to-day

```bash
pre-commit run --all-files   # ruff (lint+format), mypy, file hygiene
pytest                       # full test suite (coverage report included)
```

Both also run in CI (`.github/workflows/ci.yml`); `hassfest` and the HACS
action run in `.github/workflows/validate.yml`.

## Project layout

- `custom_components/cambridge_azur851/azur851/` — the **standalone protocol
  library** (no Home Assistant imports): framing, commands, models, the serialx
  transport, and the client. Fully unit-testable on its own.
- `custom_components/cambridge_azur851/` (the rest) — the Home Assistant glue:
  config/reconfigure flow, coordinator, entity, and platform.
- `docs/` — protocol and transport reference notes.
- `tests/` — pure-library tests plus HA-harness tests
  (`pytest-homeassistant-custom-component`).

## Conventions

- Keep the `azur851/` package free of Home Assistant imports so it stays
  independently testable.
- The 851 is **push-based** (no bulk status query); device state is built from
  unsolicited group-4 frames. See [`docs/protocol.md`](docs/protocol.md).
- Per-model differences (baud rate, volume range, sources) live in
  `azur851/models.py`. When adding a model, verify it against the official
  RS-232 document and add a capability entry plus tests.
- Add or update tests with any behaviour change; keep `pre-commit` green.

## Commit / PR

- Use focused commits with clear messages.
- Ensure `pre-commit run --all-files` and `pytest` pass before opening a PR.
- Update `docs/` and the README roadmap when behaviour changes.
