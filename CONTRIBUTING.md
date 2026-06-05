# Contributing

MinuteMetrics uses spec-driven development. Update the relevant spec in `specs/` in the same change as any behavior, packaging, setup, or UI update.

## Local Checks

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

HealthKit behavior must be validated on a physical iPhone. Simulator data is useful for build checks only.

## Pull Requests

- Keep participant names, tokens, local IPs, and local filesystem paths out of committed files.
- Use configurable participants instead of household-specific assumptions.
- Update specs before or with implementation changes.
- Include focused tests when changing API, storage, or aggregation behavior.
