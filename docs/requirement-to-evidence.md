# Requirement-to-evidence matrix

| Requirement | Implemented capability | Code / evidence | Supporting test | Scenario | Coverage / limitation |
|---|---|---|---|---|---|
| Gemini use and output validation | Structured JSON intent classification; enum and type validation; degraded mode | `starter-solution/cx/ai.py` | `test_workflows.InterpretationTests`; live evidence capture remains pending | SCN-008 | Live run requires participant key |
| Reviewer mode | Deterministic interpreter uses same workflow and adapters | `cx/ai.py`, `cx/engine.py` | workflow tests and `eval/run_scenarios.py` | SCN-001–008 | Covered; reviewer classifier is intentionally limited |
| Authentication | Synthetic login service, expiry check, random server-side session, HttpOnly cookie | `cx/security.py`, `starter-solution/server.py` | authorization tests | SCN-001, SCN-004 | Local process session only |
| Authorization / isolation | Ownership/role guard before account retrieval and response ownership check | `cx/security.py`, `cx/engine.py` | cross-account denial test | SCN-005 | Mock role model only |
| Clarification/context | Targeted service question, pending state and follow-up routing | `cx/engine.py` | clarification-resume test | SCN-002 | In-memory state |
| Grounded inquiry | Validated account/billing data and explicit source in answer | `cx/enterprise.py`, `cx/engine.py` | grounded response test | SCN-001 | Uses supplied synthetic APIs |
| Legacy integration | XML call, parse, identity match, normalize, map codes | `cx/enterprise.py::legacy` | adapter/scenario runner | SCN-003, SCN-006 | Supplied mock only |
| Consequential action | Summary, confirmation, authorization, idempotent create, verified response | `cx/engine.py`, `cx/enterprise.py` | confirmation/failure tests | SCN-004, SCN-007 | No production case backend |
| Failure and escalation | Bounded retry, malformed/provider failures produce qualified response and handoff | `cx/enterprise.py`, `cx/engine.py` | failure tests | SCN-007, SCN-008 | JSONL evidence is local |
| Telemetry and traces | Correlated redacted event stream; event-derived metrics and support-only operations APIs | `cx/telemetry.py`, `starter-solution/server.py` | telemetry tests | All | Local append-only files; no distributed trace exporter |
| Deployment / handover | GCP map, runbook, architecture, roadmap | `docs/deployment.md`, `docs/handover.md` | manual reviewer procedure | All | Deployment not actually provisioned |

## Summary of changes

Retained the supplied API, data, failure controls, scenarios, and mock services. Replaced keyword-only answer handling with controlled routing, added live Gemini adapter plus reviewer/degraded modes, session authentication and deterministic authorization, account/billing/network/legacy adapters, confirmed idempotent case creation, escalation, structured telemetry, an operations endpoint, automated tests, and deployment/handover documentation. Remaining limitations are listed in the root README and deployment guide.
