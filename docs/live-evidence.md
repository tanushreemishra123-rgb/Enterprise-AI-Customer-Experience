# Live Gemini execution evidence

Reviewers will not supply `GEMINI_API_KEY` or paid Google Cloud credentials. They can run all mandatory workflows through reviewer mode. The live integration is reviewed from code/configuration/schema validation and a participant-captured live execution trace. This package does not currently contain that capture because no participant credential was available in this session.

## Capture procedure

1. Configure a valid Gemini API key locally as `GEMINI_API_KEY`; keep it in the process environment and never in source, screenshots, logs, or the submission archive.
2. Start the supplied mock services and app with `AI_MODE=live`.
3. Sign in as `alex.morgan` and ask `What internet plan am I currently using?`. Confirm `/mode` reports `live` and the answer cites the account-service evidence.
4. Sign in as `support.agent`, open `/ops`, and record the correlated trace events showing `intent.classified` with component `gemini` and successful enterprise workflow activity.
5. Save a redacted screenshot or short screen recording showing the configured model name, mode, customer-visible response, and trace ID. Do not expose the key, cookie, or password.
6. Add a brief evidence note with capture date, model identifier, scenario, trace ID, and expected/observed result. Do not present reviewer-mode traces as live Gemini evidence.

The challenge allows the recommended 3–5 minute demo video to be placed in the ZIP or shared as an accessible link. The package has not yet recorded a video; capture it after live evidence and reviewer scenarios are complete.
