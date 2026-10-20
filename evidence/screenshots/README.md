# Screenshot evidence index

These screenshots were supplied by the participant on 2026-10-19 and copied here as received. The images include a few yellow annotations/crops. Use the corresponding requirement-to-evidence row in `docs/requirement-to-evidence.md` for implementation and test references.

| File | What the screenshot shows | Evidence note |
|---|---|---|
| `reviewer-scn002-clarification-and-service-resume.png` | Customer reports a service issue, receives a targeted home-internet clarification, then gets a service-status response after replying | Shows clarification and resumed work. A later repeated `home internet` message returns to the greeting, so avoid presenting that later turn as another successful resume. |
| `reviewer-scn003-service-status-support-trace.png` | Support-agent page after a home-internet outage/status question, with operations metrics and the expanded recent trace | Shows the customer-facing status answer and support view. The trace displays a hashed `sess-` reference. |
| `reviewer-scn004-case-created.png` | Customer requests a case, confirms, and receives a verified case reference | Shows confirmation and successful case creation. It does not show an idempotent retry. |
| `reviewer-scn004-case-created-and-scn005-denial.png` | Longer conversation showing a successful case creation and a later cross-customer access denial | Supports the case action and denial behavior; the visible yellow markup obscures a small area. |
| `reviewer-scn005-cross-customer-denial-trace.png` | Cross-customer account request is denied; support-agent operations trace shows authorization denial | Shows an authorization-denial trace; yellow markup is present. |
| `reviewer-scn006-subscriber-status-customer.png` | Customer asks for subscriber status and receives a normalized degraded-status answer | Customer-facing legacy status result. |
| `reviewer-scn006-subscriber-status-support-trace.png` | Support-agent view showing the subscriber-status trace and escalation area | Expanded trace is visible; session reference is `system`, not a user cookie value. |
| `reviewer-scn007-case-service-unavailable.png` | Case request is confirmed while the mock case service is unavailable; the UI says it cannot confirm creation and support will review | Shows safe failure without false success. It does not show the support-agent escalation record. |

## Optional extra screenshots

The screenshots below would make the submission easier to review, but the challenge does not require these exact images. The existing automated test and scenario results provide evidence for duplicate-action protection and outage handling; the green GitHub Actions run is also visible in GitHub.

- A UI view showing an identical confirmed case request returns the existing case.
- A support-agent view showing the escalation record for the simulated case-service outage.
- A link or screenshot of the successful GitHub security workflow.

## Demo video

The 3–5 minute demo is recorded and linked from the [root README](../../README.md): [Watch the Resolution Desk demo on Loom](https://www.loom.com/share/6fac5a07027c4e4ba582d31f8a02fdb9). Confirm that reviewers can open the Loom link without requesting permission.

Do not include API keys, passwords, browser cookies, or raw session IDs in any new screenshot. The session-reference fix uses hashed `sess-` references in trace data; old pre-fix `events.jsonl` logs should not be submitted.
