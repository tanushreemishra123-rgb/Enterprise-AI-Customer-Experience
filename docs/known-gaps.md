# Current limitations and production work

This document replaces the starter package's original gap list. Those starter gaps are addressed by the implementation and test suite; the remaining limitations are specific to this proof of capability.

## Current limitations

- Customer identity and account data are synthetic. The login service is a local mock, not a production identity provider.
- Sessions, pending conversation state, and case idempotency are held in process memory. They are lost on restart and are not shared across app instances.
- Telemetry and escalations are written to local JSONL files. There is no distributed trace exporter or managed monitoring backend in this local PoC.
- Enterprise REST and legacy XML integrations call supplied mock services. Production credentials, network controls, service-level agreements, and real backend contracts have not been provisioned.
- Live Gemini uses the Gemini API through Google AI Studio and needs a participant-provided key to reproduce. Vertex AI and Gemini CX/Dialogflow CX are documented deployment mappings, not provisioned services.
- Reviewer classification is deterministic and intentionally supports a narrower set of wording than Gemini.
- The local app is a single-process Python HTTP server. It has not been deployed or load-tested on Google Cloud.
- Production controls such as managed secret rotation, rate limiting, CSRF protection, workload identity, and durable recovery are included in the deployment roadmap but are not fully implemented in this local demonstration.

## Production roadmap

1. Replace local mock identity with the CSP identity gateway or Google Cloud Identity Platform.
2. Move session, workflow, idempotency, and escalation state to Cloud SQL or Firestore.
3. Deploy the app to Cloud Run behind API Gateway or Apigee with TLS, CSRF protection, rate limits, and least-privilege service identity.
4. Use Vertex AI Gemini with workload identity and managed quotas.
5. Export structured events and traces to Cloud Logging, Cloud Trace, and Cloud Monitoring; use Pub/Sub where asynchronous processing is needed.
6. Run approved security, load, recovery, and operational-readiness reviews against synthetic data before any production use.
