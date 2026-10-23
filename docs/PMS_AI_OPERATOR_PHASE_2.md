# PMS AI operator — phase 2

Follow-on implementation: [browser TensorFlow.js routing, project setup and monitors](PMS_AI_OPERATOR_LOCAL_ROUTING.md). This document records the earlier execution-foundation phase; consult the follow-on document for current additions and remaining roadmap limits.

Implemented 24 October 2026. This phase adds durable background planning/execution, resumable checkpoints, follow-up plan revisions, progress events, and date/dependency tools. Gemini, OpenAI and Claude continue to use the phase 1 provider settings and telemetry.

## Deploy and run

1. Apply the normal migration chain from `backend`: `venv/Scripts/python.exe -m alembic upgrade head`. New head: `pg_20261024_001`, following `pg_20261023_009`. A matching legacy migration is included; keep using the PostgreSQL chain selected by `alembic.ini`.
2. Start a worker against the same database, deployment secret, and enabled modules as the API. Choose either:
   - Standalone worker: `venv/Scripts/python.exe scripts/run_ai_operator_worker.py`. It polls the durable database queue; Redis is not required. `--once --batch-size 20` drains a bounded batch for maintenance or a process scheduler.
   - Existing Celery deployment: run its worker and beat services with `app.worker.celery_app`. Beat invokes `app.worker.process_operator_queue` every five seconds. Redis remains configured through the existing broker settings.
3. Use `/pms/operator`. The UI now submits background commands by default and polls committed progress. The page can be closed and reopened; select the run from Recent commands to reconnect.

The web process does not silently launch a worker or make model calls after returning a queued command. A configured worker must be running. For a serverless web deployment, host the standalone/Celery worker separately with access to the same PostgreSQL database. Migration and live worker deployment have not been performed against the user's configured database during this implementation.

Existing synchronous API clients remain compatible: `background` defaults to false and `execution_mode` to `atomic`. Existing pre-upgrade previews should be recreated because task fingerprints now include dates and dependency links.

## Execution modes

**All-or-nothing is the default.** Planning runs in the background; after approval, the entire local PMS plan executes in one transaction. A later failure rolls back the earlier actions. Progress receipts become visible together after commit. Failed execution pauses for explicit review/retry.

**Checkpointed is opt-in.** Each step's business effects, receipt, refreshed task fingerprints, progress event and next queue state commit together. A later failure pauses the run while preserving earlier effects. Cancellation stops future checkpoints and preserves committed receipts. There is no promise of universal undo. The UI discloses this before approval.

Steps have persistent one-based positions, inputs, dependency positions and receipts. Dependencies may refer only to earlier steps; an omitted dependency list defaults to all preceding steps. Execution is sequential and stops on failure, including for otherwise independent steps. This is a persisted ordered dependency graph, not parallel execution or an arbitrary code runner.

## Durable queue and recovery

`ai_operator_jobs` stores planning/execution jobs with unique run/kind keys. Claims use a compare-and-set update, PostgreSQL skip-locked row selection, a random fencing token and a 120-second lease. Each step revalidates the current lease, initiating user, PMS access, agent settings, approval and record fingerprints.

- Workers commit the claim before model I/O and release record locks during the model call.
- Expired claims can be recovered. A replaced worker cannot publish through a newer fencing token.
- A checkpoint receipt and its business change commit in the same database transaction. Reclaiming a job skips already completed steps, including after a lost worker response.
- Transient failures use bounded backoff and stop after three consecutive failures. Permission, stale-plan, invalid-input and approval conflicts pause immediately rather than repeatedly attempting writes.
- A successful checkpoint resets consecutive failures. Expired worker leases count toward the retry budget.
- `Resume remaining steps` requires the same approved plan hash, current permissions and matching task fingerprints. Stale records require a new preview. Planning failures can be revised or submitted as a new command.
- Model requests are at-least-once during planning recovery: a crash after a provider accepts a request may cause another billed planning attempt. Business step writes are protected by transactional receipts; provider billing is not claimed to be exactly once.

Worker invocation time budgets stop new claims; they cannot interrupt an in-flight provider call. Cancellation is cooperative between committed steps. An all-or-nothing transaction completes or rolls back as a unit.

## Follow-up voice and text commands

Choose **Reply / revise plan**, then type or dictate a refinement such as “Only the urgent tasks,” “Use Sprint 5,” or “Keep those dates and add QA review.”

- The server binds the follow-up to the owned parent run, original project, frozen selection and expected plan hash. A new revision receives a new run ID and approval.
- Pending or paused work is superseded and its remaining job cancelled. An old approval cannot execute the revised plan.
- A queued/running/retrying plan must be cancelled or finish before revision. Completed runs retain their outcome; a follow-up starts new reviewed work based on their recorded receipts.
- Up to eight previous turns, the prior plan, committed receipts and current authorized task context are supplied to planning. Context is redacted through the existing service.
- The session timezone and local timestamp are explicit. Resulting ISO dates appear in the preview.
- Follow-ups cannot broaden the original selection. Start a new command to add other tasks. Clarifications and refinements remain subject to model interpretation and human review.

Speech remains editable browser dictation; this phase does not add real-time audio streaming, voice approval, meeting recording or spoken responses.

## New task tools

- `schedule_task`: update explicit start/due dates through the canonical PMS scheduling operation. Partial date updates retain the other date; clearing dates is not offered in this tool.
- `add_dependency`: link selected source and target tasks in the same project, with one of the four existing dependency types and bounded lag days. Both endpoints must be in the frozen selection.

Plan validation checks task/date ranges, proposed graph cycles including existing project edges, duplicate edges, and final dependency/date conflicts. Canonical PMS operations validate again during execution. This is constraint checking for a proposed schedule, not a capacity optimizer or automatic project-wide date propagation. Dependency removal is not included.

The original assignment, status, priority, checklist and sprint tools remain available. Existing PMS HTTP endpoints preserve their normal commit behavior; operator calls share the same logic with commits deferred to the enclosing transaction.

## Progress and API additions

All paths are relative to `/api/v1/ai-operator`:

- `POST /commands` now accepts `background`, `execution_mode` (`atomic` or `checkpointed`), `timezone`, and server-validated parent context. Background submissions return a persisted `queued_planning` run immediately; API status remains 200 for compatibility.
- `POST /runs/{run_id}/revise` accepts a follow-up command, expected `plan_hash`, input mode and idempotency key. It creates a new background revision.
- `POST /runs/{run_id}/resume` accepts the approved `plan_hash` and resumes an authorized paused execution.
- `GET /runs/{run_id}/steps` returns persisted inputs, dependency positions, status, error codes and receipts.
- `GET /runs/{run_id}/events?after_id=...&limit=...` returns ordered durable events, cursor, pagination flag and current run state. Clients replay by ID and deduplicate; the UI reconnects with this contract.
- Existing approve/cancel endpoints also handle background plans. Shared AI approval endpoints queue these plans through the same review authority rather than executing on the HTTP request thread.

Events form a transactional outbox: a step event and its task effects become visible together after commit. UI polling does not publish or execute work. This phase uses authenticated cursor polling rather than SSE. It does not add cross-process WebSocket broadcast to every other PMS screen; refresh those views to see committed task changes.

Typical states: `queued_planning → planning → awaiting_approval | needs_clarification → queued → executing → succeeded`. Additional states include `retrying`, `paused`, `cancelled`, `superseded` and terminal planning `failed`. Cancelled/partial outcomes retain receipts.

## Analytics and controls

Provider/model usage, tokens, latency, optional cost estimates and sanitized failures remain in the existing operator analytics page. Every planning retry is a separate API telemetry entry. Background planning, approval, completion, retries and pauses also produce existing AI audit records; event and step endpoints show execution detail without logging credentials or raw provider errors.

PMS and AI module gates, current user/role access, agent availability, workspace scope, emergency disablement and approval validity apply to worker execution as well as web requests. Polling, revision and resume APIs enforce run ownership and current project access. Workers do not run with unrestricted superuser authority.

## Validation and remaining work

Automated tests cover atomic/checkpointed background execution, duplicate approval, expired lease fencing, restart recovery, cancellation before planning and after partial progress, paused-step resume, stale records, bounded provider retries and telemetry, revision context and invalidated approval, date/dependency tools, cycle rejection, access revocation, event ownership/cursors and repeatable upgrade of the phase 1 schema. Browser tests cover reconnecting progress, partial receipts and follow-up review in addition to the phase 1 flows. Provider responses are mocked; live model credentials and PostgreSQL deployment are not certified by these tests.

Subsequent product work: source-to-project setup, richer semantic entity resolution, dependency removal, resource/calendar/leave-aware optimization, recurring goal monitors, external communication tools, retention controls and real-time audio. These are outside this execution-foundation phase.
