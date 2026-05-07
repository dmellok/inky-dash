# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 0 (v0.1.0).** Skeleton only — Flask boots, one route, pytest harness, CI green. See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the dev server
python -m app          # http://localhost:5555

# Run the checks
ruff check . && ruff format --check . && mypy && pytest
```

Python 3.11+ required.

## Layout

```
app/            Flask application package
docs/           Build brief + plugin contract
tests/          pytest suite
.github/        CI workflow (ruff + mypy + pytest on push and PR)
```

Plugins, the renderer, the MQTT bridge, and the admin UI all land in later milestones — see the brief.

## License

MIT.
