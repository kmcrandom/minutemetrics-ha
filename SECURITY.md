# Security Policy

MinuteMetrics handles health-derived exercise data. Treat participant sync tokens and admin tokens as secrets.

## Supported Versions

The project is pre-release. Security fixes target the current `main` branch until versioned releases begin.

## Reporting a Vulnerability

Open a private security advisory on GitHub if available. If not, open an issue that describes the affected area without including real tokens, health records, local IP addresses, or screenshots containing private data.

## Secrets

- Do not commit Home Assistant option files from a live install.
- Do not commit SQLite databases.
- Rotate participant sync tokens if they are shared accidentally.
- Change the placeholder admin token before starting the app. The runtime rejects `change-me-before-use`.
