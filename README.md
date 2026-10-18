# Gemini CX Resolution Desk

Productionization of the supplied Topcoder starter. Uses synthetic records and the supplied mock enterprise service. The original starter package, contracts, data, and scenarios are retained; `starter-solution/server.py` is the HTTP entry point over the modular `starter-solution/cx/` engine.

## Run locally

Requires Python 3.10+ and no third-party packages.

```powershell
python mock-services/server.py
```

In a second terminal:

```powershell
python starter-solution/server.py
```

Open `http://localhost:8080`. Sign in with a synthetic reviewer account:

| Username | Password | Account |
|---|---|---|
| `alex.morgan` | `ReviewerPass-1001` | `ACC-2001` |
| `jordan.lee` | `ReviewerPass-1002` | `ACC-2002` |
| `support.agent` | `ReviewerPass-3001` | Support role; can view `/ops` |

Try a plan inquiry, `My service is not working`, then `home internet`, or ask to create a support case and reply `CONFIRM`. Attempting `ACC-2002` while signed in as Alex must be denied before account lookup.
Sign in as `support.agent` to inspect the operations panels; those APIs are role-protected. Sign in as a customer to run customer workflows.

## Modes and configuration

Copy `.env.example` to `.env` and set variables in the shell (the app intentionally does not load dotenv files):

| Variable | Default | Purpose |
|---|---|---|
| `AI_MODE` | `reviewer` | `reviewer` uses deterministic intent classification; `live` calls Gemini |
| `GEMINI_API_KEY` | unset | Secret for the Gemini Generative Language API; never commit it |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model identifier |
| `MOCK_API_BASE` | `http://localhost:8090` | Supplied enterprise mock base URL |
| `APP_HOST` | `127.0.0.1` | Local bind address |
| `APP_PORT` | `8080` | Local app port |

PowerShell live mode: `$env:AI_MODE='live'; $env:GEMINI_API_KEY='...'; python starter-solution/server.py`. The live request asks Gemini only to return a constrained intent, service, account identifier, and short summary. Application validation rejects unsupported output. If Gemini is unavailable or no key is configured, the mode is visibly degraded and the deterministic controls remain active. Reviewers are not expected to provide credentials: reviewer mode must run the complete mandatory workflows. A participant must separately capture a credentialed live run as evidence; see [docs/live-evidence.md](docs/live-evidence.md). No live execution evidence or demo video is included yet.

Reviewer mode uses the same HTTP workflow, authentication, authorization, enterprise adapters, action confirmation, escalation and telemetry as live mode. It is not a static answer playback. The app uses Python's standard library only.

## Operations and evidence

- `/health`: process health and configured mode
- `/mode`: live, reviewer, or degraded indicator
- `/metrics`, `/traces`, `/trace/<traceId>`, `/escalations`: support-agent-only operations APIs, backed by actual workflow events
- `python starter-solution/eval/run_scenarios.py`: executes the eight supplied scenarios against the mock services
- `starter-solution/events.jsonl`: sanitized append-only event stream
- `starter-solution/escalations.jsonl`: support handoffs

Scenario data is in `scenarios/SCN-001.json` through `SCN-008.json`. Failure controls are set on the mock service process: `MOCK_AUTH_MODE=expired|unavailable`, `MOCK_LEGACY_MODE=timeout|unavailable|malformed`, `MOCK_CASE_MODE=unavailable`, and `MOCK_BILLING_MODE=unavailable|malformed`.

## Architecture, security, and handover

See [docs/architecture.md](docs/architecture.md), [docs/deployment.md](docs/deployment.md), [docs/handover.md](docs/handover.md), [docs/live-evidence.md](docs/live-evidence.md), and [docs/requirement-to-evidence.md](docs/requirement-to-evidence.md). The Gemini model never receives tokens. Account ownership is checked in application code before retrieval; tool actions require server-side confirmation state; case writes carry deterministic idempotency keys. The mock backend and in-memory session store are demonstration-only. A demo video may be included in the ZIP or linked from an accessible hosting service; no video has been recorded yet.

## Tests and limitations

Run `python -m unittest discover -s starter-solution/tests -v` and `python starter-solution/eval/run_scenarios.py` from this folder. All 28 unit/package tests passed in preparation; the end-to-end scenario runner was not run here because this environment blocks localhost service sockets. The implementation uses synthetic, local mock services only. For production, replace in-memory sessions and JSONL files with managed stores, use workload identity and a secret manager, add CSRF protections and rate limits, set `COOKIE_SECURE=1` behind TLS, and use Cloud Logging/Trace/Monitoring. The supplied mock APIs do not expose real enterprise authentication or full support-case retrieval.
