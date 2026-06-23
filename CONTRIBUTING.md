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

- Use focused commits, and write messages as
  [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`,
  `docs:`, `refactor:`, `test:`, `chore:` (a `feat!:` / `BREAKING CHANGE:` footer
  bumps the major version). This drives automated releases (see below).
- Ensure `pre-commit run --all-files` and `pytest` pass before opening a PR.
- Update `docs/` and the README roadmap when behaviour changes.

## Releases

Releases are automated with
[release-please](https://github.com/googleapis/release-please-action)
(`.github/workflows/release-please.yml`):

1. Merging Conventional-Commit changes to `main` opens/updates a **release PR**
   that bumps the version, updates `CHANGELOG.md`, and syncs the `version` in
   `manifest.json` (via `release-please-config.json`).
2. Merging that release PR tags the commit and publishes a **GitHub Release** —
   which is what HACS and the "Latest release" badge read.

No manual version editing is needed; release-please owns `manifest.json`'s
`version` and `.release-please-manifest.json`.
