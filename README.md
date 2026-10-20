# Gemini CX Resolution Desk

Productionization of the supplied Topcoder starter. The original starter package, contracts, synthetic data, failure controls, and scenarios are retained. `starter-solution/server.py` is the HTTP entry point for the modular `starter-solution/cx/` engine.

## Requirements

- Python 3.10 or later
- Install the pinned XML security dependency from the project root:

```powershell
py -3 -m pip install -r requirements.txt
```

The legacy XML adapter uses `defusedxml`. Do not skip the dependency installation.

### Third-party dependencies and licenses

| Package | Version | Purpose | License |
|---|---:|---|---|
| `defusedxml` | 0.7.1 | Safe parsing of legacy XML responses | Python Software Foundation License (PSFL) |

The rest of the application and test suite use the Python standard library. The Gemini integration uses HTTPS directly and does not require the optional Google SDK.

## Run locally

Open two PowerShell windows. In each, go to the project root:

```powershell
cd E:\top-coder\gemini-cx-productionized
```

In PowerShell window 1, start the supplied mock enterprise service and leave it running:

```powershell
py -3 mock-services/server.py
```

In PowerShell window 2, start the app in reviewer mode and leave it running:

```powershell
$env:AI_MODE = "reviewer"
py -3 starter-solution/server.py
```

Open `http://localhost:8080` in a browser. Use one of the synthetic accounts:

| Username | Password | Account / role |
|---|---|---|
| `alex.morgan` | `ReviewerPass-1001` | Customer, `ACC-2001` |
| `jordan.lee` | `ReviewerPass-1002` | Customer, `ACC-2002` |
| `support.agent` | `ReviewerPass-3001` | Support agent; can access operations views |

Try a plan inquiry, `My service is not working` followed by `home internet`, or a support-case request followed by `CONFIRM`. A customer signed in as Alex must be denied access to `ACC-2002` before account lookup. Sign in as `support.agent` to view operations metrics, traces, and escalations.

Stop either process with **Ctrl+C** in its PowerShell window.

## AI modes

AI mode is selected by the app's environment configuration; it is independent of the signed-in role. A support agent can use reviewer, live, or degraded mode. Set the mode in the same PowerShell window used to start the app. Stop and restart the app when switching modes.

The app exposes its mode at `http://localhost:8080/mode`. The customer conversation also includes the mode used for a request, and traces record Gemini success or failure and fallback classification.

### Gemini integration and orchestration

`starter-solution/cx/ai.py` sends a bounded, redacted customer message to Gemini with a structured JSON schema for intent, service, account reference, and summary. The app validates the response before using it. `starter-solution/cx/engine.py` owns conversation state and selects narrow enterprise adapters; authentication, account ownership, confirmation, and action permissions are enforced by deterministic application code, not by Gemini. The adapters call the supplied account, billing, network, case, and legacy XML mock services, validate and normalize their responses, and provide verified facts for the customer reply. Provider or service failures are traced and safely degraded or escalated.

### Reviewer mode

Reviewer mode is the default and requires no Gemini credentials. It uses deterministic request classification but exercises the same authentication, authorization, enterprise adapters, action confirmation, escalation, and telemetry workflows as live mode. Reviewers can use this mode to run all mandatory scenarios without paid credentials.

```powershell
$env:AI_MODE = "reviewer"
py -3 starter-solution/server.py
```

The mode endpoint and app indicator should report `reviewer`. The reviewer classifier is deterministic and intentionally limited; it is not a replacement for the live Gemini integration.

### Live Gemini mode

Live mode calls the Gemini API for constrained request interpretation. A participant can demonstrate this using their own API key. Reviewers are not expected to provide a key. Never commit or share the key, and do not include it in screenshots or recordings.

```powershell
$env:AI_MODE = "live"
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
py -3 starter-solution/server.py
```

Replace the placeholder locally with your key. Send a customer request, verify that `/mode` reports `live`, and inspect the trace for a successful Gemini classification event. The model receives a bounded, redacted request and returns structured intent data; application code validates the output. Authentication, authorization, ownership, confirmation, and protected actions remain deterministic application controls.

Capture a redacted live execution for submission. Do not expose the API key, password, cookie, or other secret. Record the capture date, model, scenario, trace ID, and result in `docs/live-evidence.md`. Reviewers should not need credentials to repeat the mandatory workflows.

### Degraded fallback mode

Degraded mode occurs when `AI_MODE=live` is selected but Gemini credentials are unavailable or the provider fails. To demonstrate the missing-key fallback, stop the app and start it without a Gemini key:

```powershell
$env:AI_MODE = "live"
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
py -3 starter-solution/server.py
```

Open or refresh the app and send a request. The app should identify degraded mode at `/mode` or in the request trace and use deterministic classification. The workflow's authentication, authorization, enterprise controls, and telemetry remain active. The Gemini failure and fallback should be recorded in the trace.

If the visible mode indicator, `/mode`, and request trace disagree, capture the behavior and report it as an implementation issue; the examiner should be able to identify which mode handled the request.

## Tests and mandatory scenarios

From the project root, run the unit tests:

```powershell
py -3 -m unittest discover -s starter-solution/tests -v
```

The latest saved result is 29 tests passing (`OK`); the exact count may change if tests are added. Then run the supplied scenario evaluator. It starts its own mock service, so do not start another mock service for this command:

```powershell
py -3 starter-solution/eval/run_scenarios.py
```

The expected result is `8/8 scenarios passed`, with `SCN-001` through `SCN-008` listed as `PASS`. Save the output or a screenshot as execution evidence. Rerun both commands after code changes and update evidence only with results from the current code.

## Configuration

The application reads environment variables directly; it does not load `.env` automatically.

| Variable | Default | Purpose |
|---|---|---|
| `AI_MODE` | `reviewer` | `reviewer` uses deterministic classification; `live` calls Gemini |
| `GEMINI_API_KEY` | unset | Secret for the Gemini Generative Language API; never commit it |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model identifier |
| `MOCK_API_BASE` | `http://localhost:8090` | Supplied enterprise mock service |
| `APP_HOST` | `127.0.0.1` | Local app bind address |
| `APP_PORT` | `8080` | Local app port |

Mock failure controls are set in the mock service process: `MOCK_AUTH_MODE=expired|unavailable`, `MOCK_LEGACY_MODE=timeout|unavailable|malformed`, `MOCK_CASE_MODE=unavailable`, and `MOCK_BILLING_MODE=unavailable|malformed`.

## Operations and evidence

- `/health`: application health and configured mode
- `/mode`: current AI mode indicator
- `/metrics`, `/traces`, `/trace/<traceId>`, `/escalations`: support-agent-only operations APIs, backed by workflow events
- The operations view derives failure counts by integration and average Gemini latency from emitted events, alongside request, failure, escalation, retry, and tool-call metrics.
- `starter-solution/events.jsonl`: sanitized local event stream
- `starter-solution/escalations.jsonl`: local support handoffs
- `scenarios/SCN-001.json` through `scenarios/SCN-008.json`: mandatory scenario definitions

Store test output, redacted screenshots, live Gemini evidence, and the demo link in the submission evidence package. The captured scenario screenshots are indexed in [`evidence/screenshots/README.md`](evidence/screenshots/README.md), and the requirement-to-evidence matrix is in [`docs/requirement-to-evidence.md`](docs/requirement-to-evidence.md). The demo video may be included in the submission ZIP or linked from the README; ensure a link is accessible without requesting permission. Never store active credentials, session cookies, or real customer data in the evidence package.

**Demo video:** [Watch the Resolution Desk demo on Loom](https://www.loom.com/share/6fac5a07027c4e4ba582d31f8a02fdb9). Ensure the Loom link is accessible to reviewers without requesting permission. The 3–5 minute demo shows a grounded inquiry, clarification, protected action confirmation, authorization denial, legacy processing, a simulated failure and escalation, traces and event-derived metrics, reviewer mode, and live-mode evidence.

## Architecture, security, and handover

See [docs/architecture.md](docs/architecture.md) for the written design and [open the visual architecture diagram](docs/architecture.html). Also see [docs/deployment.md](docs/deployment.md), [docs/handover.md](docs/handover.md), [docs/live-evidence.md](docs/live-evidence.md), [docs/requirement-to-evidence.md](docs/requirement-to-evidence.md), [docs/summary-of-changes.md](docs/summary-of-changes.md), [docs/known-gaps.md](docs/known-gaps.md), and [docs/security-expectations.md](docs/security-expectations.md).

The Gemini model never receives authentication tokens. Account ownership is checked in application code before protected retrieval. Consequential actions require server-side confirmation and use idempotency keys. The legacy XML adapter uses `defusedxml` and normalizes responses before workflow use. The local mock backend, in-memory sessions, and JSONL telemetry are demonstration choices, not production persistence.

## Limitations and production considerations

This PoC uses synthetic customer data and local mock services only. Sessions and workflow state are held in process memory; telemetry and escalations are written to local JSONL files. The supplied mock APIs do not provide production enterprise authentication or full support-case retrieval. The deployment guide maps the design to Google Cloud services, but no Google Cloud environment is provisioned by this repository.

Before production, replace local state and files with managed durable services, use workload identity and a secret manager, add CSRF protection and rate limits, set secure cookies behind TLS, and export traces and metrics to Cloud Logging, Cloud Trace, and Cloud Monitoring. See `docs/known-gaps.md` and `docs/deployment.md` for the documented roadmap.
