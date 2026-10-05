# Validation — 2026-10-05

## Passed in this workspace

- 8 unit tests: nested credential/PII redaction, agent completion when telemetry
  setup/update/cleanup fails, preservation of business exceptions, offline/error
  scenario, random secret initialization without overwrite, LAN URL updates that
  preserve existing secrets and custom ports.
- Offline demo: successful agent output and simulated tool-error fallback.
- YAML parsing after local environment expansion (PyYAML, not Docker Compose).
- Static configuration checks: six services with healthchecks, matched Langfuse
  release tags, Web/API and media on LAN, Worker/MinIO console on localhost,
  databases/Redis without published ports, valid LAN public/internal media URLs,
  required generated secrets present, bounded container log options.
- ClickHouse XML, Python syntax and PowerShell AST parsing.
- Detected physical Ethernet: `10.0.10.150`, gateway `10.0.10.1`, mask `255.255.254.0`.
- Docker Desktop/backend processes are running on the host.

## Not yet verified live

This execution shell cannot access Docker CLI in the user's Docker Desktop install.
`stack.ps1 -Action validate` fails at CLI discovery; this does not mean Docker is
missing or stopped. No containers were created or started by this implementation.

- Docker Compose schema validation, image pulls and successful service startup.
- Real Python SDK import/export and project authentication (SDK is not installed here).
- Trace ingestion and UI display, token usage, error span and redacted payloads.
- Trace/account persistence after stack restart.
- Real exporter outage while agent completes; unit tests only simulate telemetry failures.
- Windows Firewall rules (script created, not applied; requires Administrator).
- UI/API and S3/media access from another LAN machine.

## Finish live verification on the host

In a terminal with working Docker CLI, from this project directory:

```powershell
docker compose config --quiet
docker compose up -d --wait --wait-timeout 600
python scripts/health.py
```

In Administrator PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/allow_lan.ps1
```

Then follow README for account/project creation, Python dependencies and smoke
trace; test from a second LAN machine using `http://10.0.10.150:3000`.

Static checks are not a substitute for these runtime checks.
