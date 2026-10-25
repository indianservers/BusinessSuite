# Live operator verification — 24 October 2026

**Latest follow-up:** Gemini is now configured and passed the live checks below.
The user explicitly deferred OpenAI, Claude and physical microphone testing.
The original run and its limitations are retained below as historical evidence.

## Gemini follow-up: real provider verified

- Model: `gemini-3.5-flash-lite`, selected after the account's live models listing
  and a generation response indicating 2.5 Flash-Lite is unavailable to new users.
- Key saved encrypted through the existing settings API; settings responses and
  evidence contain only `has_key`, never the credential.
- Five checks passed: saved configuration, connectivity, a real two-step plan
  through the worker, cloud fallback with a follow-up question, and usage/logs.
- Run **13**, task **8**: Gemini proposed High priority plus one checklist item.
  The verifier checked exact targets/tool payloads before approval. The running
  worker completed both steps and retained receipts. Replaying the command's
  idempotency key reused its run and produced no additional generation call.
- Conversation **3**: explicit `unsupported` local fallback called real Gemini,
  returned a valid deadline question and persisted cloud routing metadata.
- Final verification requests: **7,791 input tokens**, **193 output tokens**,
  **$0.00281980 estimated USD** across connectivity, planning and fallback.
  Actual latency was 10.8–13.2 seconds per request in this final run.
- Estimates use published standard text rates of **$0.30 input / $2.50 output per
  million tokens**, configured in PMS. Free-tier credits, discounts and invoices
  are not reconciled. [Pricing source](https://ai.google.dev/gemini-api/docs/pricing.md).
- Prior real 404, 400 and temporary 503 failures remain in analytics with sanitized
  error codes, HTTP statuses and latency; unavailable token/cost fields stay null.
  The 503 fallback was followed by a successful fresh verification run.
- Fixed Gemini's rejected compound constrained-decoding schema by using JSON
  mode with the full schema in the instruction. Full Pydantic and domain
  validation remain required before approval/execution; unsupported actions are
  rejected. [Schema limitations](https://ai.google.dev/gemini-api/docs/structured-output).
- Gemini output usage now includes thinking tokens when reported; its response ID
  is retained when the HTTP request-ID header is absent. Regression tests check
  both valid and invalid model output, billed token math and absence of effects
  before approval.
- **56 regression tests passed** across operator, brain, jobs and workbench.
- Evidence: `gemini-results.json` and `gemini-history.json`. Reusable live verifier:
  `backend/scripts/verify_operator_provider_live.py --provider gemini --project 2`.
  It makes metered calls and modifies only its newly labelled QA task.

## Deferred real microphone test

The real Chrome tab is kept open at the local PMS sign-in page. Authentication
is required before the assistant can load. No fake audio device, generated audio,
or injected recognition callback counts as a physical voice test.

When ready:

1. Sign in, then open `http://127.0.0.1:5191/pms/assistant?project=2&task=8`.
2. Open **Conversation**. Clear a previous conversation if it has a pending
   question, so this is a fresh command test.
3. Click the microphone, allow access in Chrome, and say **“Set priority to low
   and add checklist item voice verification.”**
4. Confirm the actual recognized transcript is correct, then send it. Review the
   two-step plan, approve it, and wait for worker receipts. Confirm API run
   provenance is `input_mode=voice`.
5. Enable spoken replies/read-back and confirm the output is audible.

Physical recording, recognition and audible output remain pending at the user's
request. OpenAI and Claude have not been configured or called in this follow-up.

## Original migration and verification run

Applied the PostgreSQL Alembic chain from `pg_20261022_002` through
`pg_20261024_010` on the configured PMS database. Both assistant workbench tables
exist. Migration 011 was not applied. Backend automatic migration was disabled
for this launch, and demo seeding was disabled.

Backend: `http://127.0.0.1:1534`; frontend: `http://127.0.0.1:5191`.
Open `/pms/assistant?project=2`. Dedicated records: project 2,
`AI Operator live QA 84F1FE`, and the separately labelled kickoff project 3.
Synthetic tasks, memories, teaching examples and receipts are retained for review.
QA event rules, delivery monitor and automatic policy were disabled after checks.

Worker is running as a hidden background process, launcher PID 30008 / worker
PID 34984. Backend launcher PID 14100 / server PID 26352. These are current
session processes, not installed Windows services. Startup logs and process IDs
are under ignored `.local/operator-live-qa/`; credentials remain there only.

## Checks against all 19 feature areas

1. **Plan editor — passed:** live UI adds an action and switches tools. Live API
   validates a multi-step draft; incorrect approval hash returns 409; correct
   approval queues real work. No business effects occur before approval.
2. **Follow-ups — passed:** real local command model asks for task title and key;
   answering both produces a creation proposal, approved through the live UI to
   create the task. No cloud request occurred. Real pretrained model independently
   generated a deadline question using TF.js WASM in 95.7 seconds.
3. **Persistent memory — passed:** create through API and browser, read in fresh
   brain context, correct with revision increment, reject stale revision with 409.
4. **Recovery — passed:** multi-step run 1 completed; inverse run 2 separately
   approved and completed by the running worker. Isolated regression checks also
   verify recovery rejects intervening changes.
5. **Execution tracking — passed:** real checkpointed execution, durable step
   receipts/events, successful worker jobs, and cancellation of a pending run.
6. **Voice — partial:** simulated Web Speech recognition supplies an editable
   transcript; real browser submission preserves `input_mode=voice`, requires
   approval and completes through the live worker. Physical microphone capture,
   real speech recognition and audible output were not verified.
7. **Contextual references — passed for selected task:** “schedule this task for
   next Monday” resolves the selected real task and executes after approval.
   Fixed a local-routing bug exposed by this test. This does not exhaust every
   ambiguous-person or previous-project conversation.
8. **Dependency/calendar scheduling — passed:** real blocker dependency execution;
   weekend and configured holiday skipped; dependent task starts the next working
   day. Local relative-date scheduling also executed. All four dependency types
   are additionally covered by isolated regression tests.
9. **Workload assignment — passed:** real collaborator capacity and available-hours
   results; approved assignment run 11 completes against the real task.
10. **Kickoff — passed:** real project/milestone/parent/subtask/blocker creation
    through setup preview and exact-plan approval, without provider calls.
11. **Impact preview — passed:** before/after details returned for the real
    multi-step plan before approval; execution and inverse receipts preserved.
12. **Search — passed:** scoped task matches returned with authoritative links.
    These are bounded supported filters, not unrestricted semantic search.
13. **Proactive alerts — passed:** running worker checks a real delivery monitor
    and persists findings/checked timestamp; no external messages were sent.
14. **Playbooks — passed:** stored real typed plan prepares an approval-required
    invocation, which was cancelled; autonomous rule uses the same playbook.
15. **Event agents — passed:** live worker observes blocked task and creates run 6;
    rule and run receipts persist. Rule disabled after verification.
16. **Autonomy — passed within supported bounds:** explicit one-step status/priority
    policy allows worker execution of the event plan. Isolated regression tests
    additionally verify withdrawal pauses queued work before effects and that
    non-administrators cannot configure standing consent.
17. **Teaching — passed:** unreviewed example absent from export; admin approval
    makes it exportable. Export does not retrain weights.
18. **Routing and API usage — partial:** live metrics return browser routing,
    execution outcomes and provider-usage structure. Gemini, OpenAI and Claude
    are unconfigured; all three cloud routes correctly return 409 unavailable.
    Real provider token billing, latency, cost and error telemetry require valid
    provider configuration and remain unverified.
19. **Quality — passed:** live UI runs the actual local parser for a saved priority
    case and records a passing result. API records feedback and structural plan
    validation results. This is not a general intelligence benchmark.

## Evidence and validation

- `api-results.json`: 14/14 grouped live API checks. No HTTP API mocks; standalone
  worker processes queued work. Some groups intentionally cover several features.
- `browser-results.json`: 16/16 live browser checks, all 11 tabs, follow-up task
  creation, memory, simulated voice execution, real local quality evaluation,
  desktop/mobile layout. No page errors or HTTP failures in the final run.
- `supplemental-results.json`: 3/3 selected-task/editor/assignment checks.
- `pretrained-results.json`: real downloaded pretrained weights, TF.js WASM,
  valid deadline follow-up output. No substituted model output.
- Screenshots: `live-desktop.png`, `live-mobile.png`, `live-conversation.png`.
- Regression: 15 backend workbench tests passed; 6 Assistant Studio browser
  regression tests passed (their API fixture is mocked and separate from live QA).
- Production frontend build passed. Existing deprecation, Browserslist and bundle
  size warnings remain.

Overall: 17 feature areas have passed the documented live paths; voice and paid
provider telemetry are partial. Complete end-to-end sign-off for all 19 requires
physical voice verification and configured provider credentials.
