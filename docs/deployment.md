# Deployment plan

## Local / containerized run

Run the mock service and app as separate processes using the root README. A container image can use Python 3.12 slim, copy the project, run as a non-root user, expose 8080, and use `/health` for liveness/readiness. The current default binds to loopback for local use; set `APP_HOST=0.0.0.0` only inside a container with a controlled network boundary.

The challenge forum confirms that local in-memory session/workflow state and file-based telemetry/idempotency evidence are acceptable for the PoC. The current mock service owns case idempotency in process memory and the app stores events/escalations as JSONL. The production mapping below replaces these process-local stores so state survives restart and scale-out.

## Google Cloud mapping

- Cloud Run: stateless web/API container, minimum instances as required, request concurrency set conservatively for synchronous provider calls.
- Vertex AI Gemini: preferred enterprise model access and IAM-based authentication; replace the Generative Language API key adapter after tenant/project enablement.
- Secret Manager: provider credentials until workload identity is available; never build secrets into images.
- Identity Platform or the CSP identity gateway: replace the supplied synthetic login.
- API Gateway / Apigee: customer API boundary, quotas and request validation.
- Cloud SQL or Firestore: durable session, workflow, action-idempotency and escalation state.
- Pub/Sub: decouple telemetry and escalation events from the customer response path.
- Cloud Logging, Trace and Monitoring: structured logs, distributed traces, SLO dashboards and alerts.
- Cloud Build and Artifact Registry: reproducible build, vulnerability scan and promotion.

## Reliability and operations

External calls have bounded timeouts. Idempotent reads retry transient transport failures and selected 429/5xx responses within a small cap. Case create has one retry only after an unavailable response and reuses the same idempotency key. Sessions and JSONL persistence are process-local demonstration choices and must be replaced before horizontal scaling. Use readiness checks for dependencies, controlled rollout, revision rollback, and a documented recovery path for durable pending actions.

Current local timeout/retry defaults are configurable through the process environment:

| Setting | Default | Behavior |
|---|---:|---|
| `ENTERPRISE_TIMEOUT` | 4 seconds | Timeout for ordinary enterprise HTTP calls |
| `LEGACY_TIMEOUT` | 4 seconds | Timeout for legacy XML calls |
| `MAX_RETRIES` | 1 | Retry cap for eligible idempotent calls; clamped to 0–3 |
| Gemini request timeout | 8 seconds | Fixed timeout in the live Gemini adapter |

The app reads these variables from the environment; `.env.example` is a reference file and is not loaded automatically.

## Security and cost

Enforce TLS, secure cookies, CSRF controls, request limits, per-customer rate limits, least-privilege service identities, VPC egress policy, and log redaction. Avoid sending enterprise records to the model unless a reviewed grounding design specifically needs them. Monitor model token use, latency, request volume and retries; use reviewer mode for repeatable CI and demos. Budget limits should alert before they block the service. Roll back by shifting Cloud Run traffic to the previous known-good revision while preserving compatible database schema.
