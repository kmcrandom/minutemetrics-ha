# Plan: Security Hardening Defaults And Sync Bounds

## Source Specs

This plan implements the security hardening updates in:

- [API and Data Model Spec](api-data-model.md)
- [Home Assistant App Spec](home-assistant-app.md)
- [Dashboard Spec](dashboard.md)
- [Product Requirements](product-requirements.md)
- [Verification Plan](verification.md)

## Goal

Close the reportable security findings from the deep Codex Security scan while preserving the current trust-based participant sync model for the initial release.

## Decisions

- Participant sync remains trust-based. Possession of a participant sync token authorizes that participant's HealthKit-derived values.
- This change adds plausibility and request-size bounds, not cryptographic attestation or anti-cheat proof.
- Participant-scoped dashboard reads keep showing scoreboard data, but redact Home Assistant identity metadata.
- Full dashboard contexts keep access to Home Assistant identity metadata for admin and Home Assistant integration use.

## Proposed Runtime Limits

- Maximum sync days per request: `400`.
- Maximum declared sync date span: `400` days inclusive.
- Maximum exercise minutes for one local day: `1440`.
- Maximum `timezone_identifier` length: `128` characters.
- Maximum device `name`, `app_version`, and `ios_version` length: `128` characters each.

These limits allow full-year and leap-year resyncs with operational slack, while preventing unbounded parsing, SQLite write amplification, and implausible daily totals.

## Implementation Tasks

1. Harden admin token configuration.
   - Add a shared placeholder-token constant in `minutemetrics/src/minutemetrics/config.py`.
   - Add a shared minimum admin-token length of `32` characters.
   - Trim surrounding whitespace before validating and storing the admin token.
   - Reject missing, blank, placeholder, or shorter-than-32-character admin tokens during settings loading or app initialization.
   - Preserve environment-variable overrides for local development when they are non-placeholder and at least 32 characters.
   - Update docs that currently instruct users to replace the default token, if runtime behavior changes require clearer wording.

2. Bound participant sync payloads.
   - Update `minutemetrics/src/minutemetrics/schemas.py` with field constraints for device metadata, timezone, day count, date span, day membership, and daily minute maximum.
   - Ensure invalid payloads fail Pydantic validation before `Store.sync_exercise_days` writes anything.
   - Keep valid full-year sync behavior unchanged.

3. Redact participant-scoped Home Assistant identity metadata.
   - Add a response projection path for participant-scoped dashboard access in `minutemetrics/src/minutemetrics/app.py` or `Store`.
   - Preserve full dashboard/admin/ingress responses with `home_assistant_user_id` and `home_assistant_person_entity_id`.
   - Redact those fields for all participants when the caller is participant-scoped.

4. Update tests.
   - Add tests proving placeholder and short admin tokens cannot authorize admin endpoints or create an app successfully.
   - Add tests for valid full-year sync near the configured limit.
   - Add tests rejecting too many days, too-wide date range, out-of-range day entries, oversized metadata strings, and more than 1,440 minutes.
   - Add tests proving rejected sync payloads do not partially write rows.
- Add tests proving participant-scoped dashboard responses redact Home Assistant identity fields while full dashboard access still includes them.

5. Keep specs current.
   - If implementation reveals a better limit or redaction rule, update the relevant spec before continuing.

## Likely Files

- `minutemetrics/src/minutemetrics/config.py`
- `minutemetrics/src/minutemetrics/app.py`
- `minutemetrics/src/minutemetrics/schemas.py`
- `tests/test_config.py`
- `tests/test_api.py`
- `README.md`
- `minutemetrics/README.md`
- Specs listed above, if plan details change.

## Verification

Run focused and full backend checks:

```bash
.venv/bin/python -m pytest -q tests/test_config.py tests/test_api.py
.venv/bin/python -m pytest -q
```

Manual review:

- Confirm the default Home Assistant app config still shows the placeholder as a setup prompt, but the runtime fails closed until changed to a token of at least 32 characters.
- Confirm the dashboard still renders participant-visible standings after redaction.
- Confirm full dashboard access still exposes Home Assistant identity metadata where existing Home Assistant sensor/admin workflows need it.

## Risks And Compatibility

- Failing closed on placeholder or short admin tokens can break any test or development workflow that relied on weak local values. Tests and local docs must set an explicit non-placeholder token of at least 32 characters.
- Existing installations that never changed the placeholder token, or changed it to a short weak token, will need to update configuration before admin APIs work. This is intended security behavior.
- Payload limits may reject unusual historical resyncs longer than 400 days. A later spec can add pagination or server-negotiated sync windows if needed.
- Participant metadata redaction can affect clients that used participant-scoped dashboard responses to inspect Home Assistant user/person IDs. That data remains available through full dashboard/admin contexts.
