# Live Gemini execution evidence

Reviewers will not supply `GEMINI_API_KEY` or paid Google Cloud credentials. They can run all mandatory workflows through reviewer mode. The live integration is reviewed from code/configuration/schema validation and a participant-captured live execution trace. A participant-captured live run is included in this package. Reviewers can inspect the screenshots below; no API key, password, cookie, or session identifier is included.

## Captured execution evidence

Captured 2026-10-19 using the Gemini live integration. The customer asked, “What internet plan am I currently using?” The UI showed live mode and returned the grounded Fiber 500 account response. The support-agent view showed one Gemini call and zero Gemini failures. The inspected event was gemini.completed, with model gemini-2.5-flash. The post-fix trace screenshot has been redacted to hide the session value; new trace screenshots in the reviewer scenario set show the stable hashed `sess-` reference or `system` marker, not a cookie value.

- Customer-facing live response: evidence/screenshots/live-customer-response.png
- Live support operations and metrics: evidence/screenshots/live-operations-overview.png
- Redacted trace showing gemini.completed and model: evidence/screenshots/live-gemini-completed-trace-redacted.png
- Reviewer-mode customer response: evidence/screenshots/reviewer-customer-response.png
- Reviewer-mode support operations; session identifier redacted: evidence/screenshots/reviewer-operations-view-redacted.png
- Degraded-mode customer response: evidence/screenshots/degraded-fallback-response.png

These screenshots demonstrate the observed local proof of capability. They are not a substitute for rerunning the scenario in a fresh environment.
## Capture procedure

1. Configure a valid Gemini API key locally as `GEMINI_API_KEY`; keep it in the process environment and never in source, screenshots, logs, or the submission archive.
2. Start the supplied mock services and app with `AI_MODE=live`.
3. Sign in as `alex.morgan` and ask `What internet plan am I currently using?`. Confirm `/mode` reports `live` and the answer cites the account-service evidence.
4. Sign in as `support.agent`, open `/ops`, and record the correlated trace events showing `intent.classified` with component `gemini` and successful enterprise workflow activity.
5. Save a redacted screenshot or short screen recording showing the configured model name, mode, customer-visible response, and trace ID. Do not expose the key, cookie, or password.
6. Add a brief evidence note with capture date, model identifier, scenario, trace ID, and expected/observed result. Do not present reviewer-mode traces as live Gemini evidence.

The 3–5 minute demo video is recorded and linked from the [root README](../README.md): [Watch the Resolution Desk demo on Loom](https://www.loom.com/share/6fac5a07027c4e4ba582d31f8a02fdb9). Confirm that reviewers can open the Loom link without requesting permission.
