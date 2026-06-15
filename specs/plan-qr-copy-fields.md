# Plan: Pairing QR Copy Fields

## Goal

Allow an admin to copy the pairing server URL and sync token while the pairing QR code is displayed, without exposing the sync token in clear text on screen.

## Scope

- Update the admin pairing dialog only.
- Preserve the existing QR payload, participant creation flow, token rotation flow, and backend pairing QR endpoint.
- Do not persist or re-fetch sync tokens after the pairing moment.

## Implementation Tasks

1. Extend `minutemetrics/src/minutemetrics/static/admin.html`.
   - Add readonly server URL and sync token controls inside the existing pairing dialog.
   - Add one copy button per field.
   - Use `type="password"` for the sync token display.
   - Add a small status region for copy feedback.

2. Update `minutemetrics/src/minutemetrics/static/admin.js`.
   - Capture the new dialog elements in `els`.
   - In `showPairingQR`, compute the server URL once, use it for QR generation, and populate both display fields.
   - Keep the sync token available only in the in-memory dialog field during the pairing moment.
   - Add copy handlers that copy the exact field value through `navigator.clipboard.writeText`.
   - Provide success and failure feedback without logging or displaying the unmasked token.
   - Clear pairing field values and feedback when the dialog closes.

3. Update `minutemetrics/src/minutemetrics/static/styles.css`.
   - Add compact pairing-field layout styles that fit the current modal width.
   - Keep the QR code visually primary and ensure long server URLs or tokens do not overflow on narrow screens.

4. Add focused tests where practical.
   - If there is no frontend test harness, add or update backend/static smoke coverage only if it can verify the changed markup without brittle browser behavior.
   - Rely on manual browser verification for clipboard behavior if automated clipboard permissions are not already available.

## Verification

- Run the Python test suite with `pytest`.
- Start the local app if needed and verify the admin dialog in a browser:
  - Creating or rotating a participant still displays a QR code.
  - The server URL field displays the configured value and copies it.
  - The sync token field is masked and copies the exact unmasked token.
  - Closing and reopening the dialog clears stale values.
  - Layout remains usable at desktop and mobile widths.

## Risks

- Browser clipboard APIs can fail outside secure contexts or without permission; the UI should report failure rather than silently succeeding.
- The sync token must not be inserted into visible text, status messages, console logs, URLs, or persistent storage.
