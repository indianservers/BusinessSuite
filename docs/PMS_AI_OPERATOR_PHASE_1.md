# PMS AI operator — phase 1

Follow-up: [phase 2 background execution, revisions and new tools](PMS_AI_OPERATOR_PHASE_2.md) is implemented. The text below records the original phase 1 behavior.

Implemented in the working tree on 24 October 2026. This is a bounded, reviewed task operator, with persistent runs and atomic synchronous execution. It is not yet the background workflow engine described in the longer-term audit.

## Use it

1. Apply the deployment migration through the existing PostgreSQL migration workflow. The new head is `pg_20261023_009`; from `backend`, the existing command is `venv/Scripts/python.exe -m alembic upgrade head`. A mirrored legacy migration is included, but `backend/alembic.ini` selects the PostgreSQL chain. Do not switch migration chains.
2. Open PMS Settings and choose OpenAI / ChatGPT, Gemini or Claude. Direct routes: `/pms/settings/ai/openai`, `/pms/settings/ai/gemini`, `/pms/settings/ai/claude`. The existing AI configuration and copilot provider settings screens link to these connections.
3. Select the correct workspace scope. Workspace projects use workspace connections. Legacy projects use company connections when a company is available; otherwise connections are private to the current user. There is no shared null-tenant credential fallback.
4. An AI administrator configures the provider API key, an actual model ID available to that API account, maximum output tokens, enabled state and permission to send task context. Run the saved connection test. The test makes a small real provider request and records telemetry. Ordinary use requires `ai_assistant` or `settings_manage`, project task-management access, an enabled planning agent and enabled PMS AI controls.
5. Open `/pms/operator`, or use **AI operator · voice / text** on a task. Select up to 25 tasks from one project, choose a configured provider, then type or dictate the command.
6. Review the proposed steps and frozen selection. **Approve and execute this plan** invokes the existing AI approval executor. Inspect the returned record receipts. A rejected, cancelled or stale plan cannot be applied.

Example: “Set these tasks to High priority, assign them to owner@example.com, add a QA review checklist item, and move them to Sprint 4.” Ambiguous/unsupported requests should produce a clarification, not a guessed action. Edit the command and request a new preview. Exact speech/model interpretation still needs evaluation with real models and realistic commands.

## Implemented business tools

- `update_task`: task status, priority and replacement multi-assignee list.
- `add_checklist`: create a named checklist item.
- `move_to_sprint`: move to an eligible sprint in the same project.

These call shared canonical PMS operations extracted from the existing task-update, checklist-create and sprint-move HTTP handlers. HTTP behavior keeps its normal commit/broadcast path. Operator tools defer commits until the complete plan succeeds; they do not make loopback HTTP requests or duplicate assignment/automation validation.

Plan steps execute in their displayed order, up to 75 steps. Every task ID must be in the frozen authorized selection. Database row locks and task/checklist fingerprints detect stale previews. A nested transaction rolls back all business changes if any step fails; receipt, run status and approval execution state commit together. Repeating an already completed approval returns its stored result. Commands have per-user idempotency keys, and reusing a key with different input returns 409.

Normal task automation and recurrence effects remain part of canonical PMS updates. They are disclosed in the preview UI; the operator does not bypass them. Deferred operator writes do not broadcast uncommitted intermediate changes. Other open PMS views currently require refresh after execution; an after-commit event outbox is future work.

## Provider integration

- OpenAI uses the Responses REST API with JSON output and local plan-schema validation.
- Gemini uses `generateContent`, JSON MIME type and `responseJsonSchema`.
- Claude uses the Messages API with a forced `submit_plan` tool and local schema validation.

All adapters normalize to the same typed, allowlisted task plan. Unknown tools/fields, out-of-selection targets, invalid assignees, unavailable sprints, truncated responses and invalid JSON cannot execute. Endpoints use fixed provider hosts with redirects disabled and bounded timeouts. No vendor SDK upgrade is required.

Provider keys are encrypted at rest with a Fernet key derived using a separate context from the deployment's `SECRET_KEY`. Keep that deployment secret stable and protected; changing it requires re-entering provider keys. Saved keys are never returned by read/update APIs; omitting a key on save preserves it. Existing redaction runs before business context is sent to a provider. API logs contain metadata rather than prompts, responses, provider error bodies or keys. Run records retain the user's command and plan for review, so they should be covered by the deployment's data-retention policy.

Official API references used: [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [Gemini content generation](https://ai.google.dev/api/generate-content), [Claude Messages](https://platform.claude.com/docs/en/api/messages/create).

These connections currently serve the new PMS operator. Existing legacy copilot mock settings and the older OpenAI-only agent chat path are not silently rerouted. Unifying those consumers is subsequent work.

## Voice

Push-to-talk uses browser SpeechRecognition where available. It starts only after the user clicks Dictate, shows recording state, offers stop, and produces an editable transcript. Partial speech does not submit commands or approve actions. Both voice and text use the same command, plan-validation and approval APIs.

This phase does not implement provider audio streaming, server-side transcription, spoken responses, voice approval or meeting capture. Browser speech services may process audio; their availability and accounting are separate from the three LLM API connections. Text remains available if microphone access or speech recognition fails. Voice support is explicitly detected in the UI.

## Current operator APIs

All paths use `/api/v1/ai-operator`:

- `GET /providers` — sanitized connection status in the authorized scope.
- `PUT /providers/{provider}` — admin configuration; optional key rotation.
- `POST /providers/{provider}/test` — real saved-key/model connection test with telemetry.
- `GET /capabilities` — supported tools and execution bounds.
- `POST /commands` — generate and persist a preview or clarification; no task writes.
- `GET /runs?project_id=...` and `GET /runs/{run_id}` — the user's authorized run history/detail.
- `POST /runs/{run_id}/approve` — hash-bound approval through the existing approval executor.
- `POST /runs/{run_id}/cancel` — cancel a pending/planning run and its pending approval.
- `GET /analytics` — administrator usage aggregates and latest request logs, scoped by optional `workspace_id` and `days`.

The existing `/api/v1/ai-agents/approvals/{approval_id}/approve` and `/reject` also work with these plans. Rejection now checks ownership and locks the approval; rejecting an operator approval cancels its run. Access and AI emergency disablement are rechecked before execution. Operator routes are registered with PMS and covered by its module gate.

## Analytics and logs

The settings pages display provider/model/status request counts, reported input/output tokens, average latency, optional estimated USD costs and the latest 200 request metadata records. Logs include purpose, initiating user, run, provider request ID where available, HTTP status and sanitized error code. Failed API calls and connection tests are recorded too. Unknown token usage and costs remain null rather than falsely appearing as zero.

Cost estimates use optional administrator-supplied USD rates per million tokens, captured at request time. They are not provider invoices, and may not reflect cache discounts, reasoning-token pricing or other contract-specific charges. Existing AI audit logs also record provider updates, plans, cancellations and approval execution. Speech recognition does not produce provider-token usage in this phase.

## Validation

Backend integration tests cover three normalized provider formats, encrypted keys and rotation, workspace/private scope isolation, authorized assignment/sprint execution, frozen selection, stale previews, duplicate commands and approvals, rejected/cancelled plans, shared approval endpoints, emergency disablement, malformed output, provider failure telemetry and rollback after a later-step failure. These use mocked provider HTTP responses, not real API credits. The generic HTTP-audit middleware is isolated in this suite because it otherwise opens the deployment database independently of the test DB; operator-specific audit and telemetry execute normally.

PMS access and migration-chain regression tests run alongside the new suite. Browser tests cover text plan/review/execution, editable voice transcripts with no automatic submission, hidden stored credentials and provider analytics. TypeScript is checked separately.

Live vendor credentials/model access and the actual PostgreSQL deployment were not exercised by these tests. The migration files are validated through the existing isolated migration test, not applied to a configured live database during implementation.

## Next phase

Add durable background workers and resumable step graphs, after-commit progress/events, follow-up conversational plan revisions, dependency/date tools, project-setup atomic plans and capacity-aware scheduling. Current cancellation is for pending plans; a short synchronous transaction is serialized, not interruptible between externally visible steps. A planning process crash can leave a run in `planning`; cancel it and create a fresh preview. Failed local execution can be replanned, while a lost successful response is safely retried through the stored approval receipt.
