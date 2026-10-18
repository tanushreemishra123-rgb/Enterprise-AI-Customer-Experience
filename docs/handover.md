# Customer-team handover

## Business problem and design

The service desk must answer account and connectivity questions from authoritative systems while protecting subscriber records and making support actions auditable. The supplied starter's keyword answer path has been retained as the HTTP entry point concept and extended into an explicit workflow. Gemini classifies a bounded request; deterministic services handle identity, access, enterprise calls, validation and actions.

## Components

- `starter-solution/server.py`: HTTP boundary, server-generated session cookies, support-only operations routes, and static UI delivery.
- `cx/ai.py`: constrained Gemini API interpretation and deterministic reviewer/degraded classifiers.
- `cx/engine.py`: clarifications, inquiry/diagnostics routing, confirmed action state, and safe escalation.
- `cx/security.py`: synthetic login, server-side identity sessions, expiry, account ownership and support-agent role checks.
- `cx/enterprise.py`: validated REST adapters, bounded retries, idempotent case creation, and legacy XML normalization.
- `cx/telemetry.py`: redacted JSONL events, trace lookup and event-derived metrics.
- `starter-solution/ui/`: browser chat, sign-in, operations metrics, traces and escalation view.

## Add a new tool or change routing

Add an enumerated intent and JSON-schema field only if necessary, then map it to a narrow function that validates identifiers and response shape. Put authorization ahead of the adapter. Define confirmation and idempotency requirements for any consequential write. Emit start/result/failure events with a trace ID, and add a reviewer scenario plus tests. Never let model text decide whether access is allowed.

## Diagnose a request

Sign in as `support.agent`, open the operations panels, locate the trace ID returned to the customer, and follow ordered events by trace. Check auth and authorization outcomes first, then adapter events and escalation reason. `events.jsonl` and `escalations.jsonl` are local development evidence and must not be treated as durable production stores.

## Known limits and roadmap

The app uses process memory for sessions, local JSONL for telemetry, a synthetic identity service, and a single Python HTTP server. The live Gemini adapter is implemented but needs participant credentials and a recorded execution. Recommended sequence: persist workflow and idempotency state, add distributed trace export, deploy behind an authenticated gateway on Cloud Run, then run security and load reviews with approved synthetic data.
