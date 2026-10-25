# Gemini business-suite operator

Open `/ai-agents/operator` from **AI operator** in the shared top bar. The PMS
floating assistant also links here. Choose the workspace, the authorized sources
to read, and either **Summary only** or **Answer or prepare actions**. Gemini is
the only provider used by this new operator; OpenAI and Claude remain pending.

## Connected APIs

- **HRMS:** directory, your leave requests/balances and leave types; submit your
  own leave request or create an HR helpdesk ticket. Personal actions require an
  employee-linked user. Manager approval of leave remains a separate HR workflow.
- **CRM:** visible leads, deals and tasks; create follow-up tasks and update task
  titles, descriptions, priorities, status and due dates.
- **SRM:** sales dashboard, authorized invoices and inventory; prepare manual
  invoice drafts with explicit customer, currency and line values. No invoice
  issuance, delivery, collection, transfer or external message tool is exposed.
- **FAM:** accounting dashboard, vouchers, ledgers, voucher types and cost centers;
  create cost centers and draft vouchers. Posting and financial approvals remain
  in the finance workflow.
- **PMS:** accessible workspace projects and tasks; create projects and tasks.
  The existing PMS Assistant Studio retains its richer task tools, scheduling,
  memory, playbooks and recovery.

The registry is `backend/app/ai_operator/suite_tools.py`. Each tool fixes the API
path, method and permitted fields. The model cannot choose arbitrary endpoints,
tenant IDs, permissions, credentials or provider hosts. Specialized legacy AI
Copilot pages and FAM accounting advisor buttons are separate interfaces; this
change adds the shared suite operator rather than replacing those interfaces.

## Workspace configuration

The existing encrypted Gemini settings now have **Allow owned/company workspaces
to inherit Gemini settings**. This is enabled on the configured Gemini source in
the local PMS. Existing and future matching workspaces resolve it dynamically;
keys are not copied into workspace rows.

A workspace-specific setting always takes precedence, including a disabled
override. Inheritance requires membership and matching company ownership or an
explicit workspace Owner's opted-in configuration. Unrelated private workspaces
cannot borrow another user's key. Ambiguous ownership requires an explicit
workspace override. OpenAI/Claude inheritance is not enabled.

The workspace selects provider billing scope and confines PMS targets. HRMS,
CRM, SRM and FAM keep their existing employee/company/role visibility; selecting
a workspace does not grant access to those modules or turn their records into
workspace-owned records.

## Approval and execution

Requests are persisted in `ai_suite_runs`. Reads use canonical APIs and send
only selected, minimized fields to Gemini: at most six sources and 50 records
per source. Summaries are bounded samples, not necessarily exhaustive reports.
Summary-only requests omit the action catalog and cannot contain writes.

Up to 12 actions can form a plan. A later step may use an earlier receipt's ID
with `{"$step":1,"field":"id"}`. Unknown tools, forward references, missing
fields, injected tenant IDs and unsupported payload fields are rejected.

Business writes require owner approval of the exact plan hash within 30 minutes.
Withdrawn or changed approvals cannot be overwritten. The existing operator
worker dispatches each approved step through the canonical FastAPI router with
the initiating user/session. Existing dependencies, permissions, tenancy and
domain validation therefore run again. Known update targets have preview hashes
to reject intervening changes.

Execution is **checkpointed**. Completed steps remain committed if a later step
stops. Receipts record the tool, position and saved record ID. Cancellation stops
remaining work after an in-flight step finishes. A crash or uncertain write
outcome becomes `needs_reconciliation`; that write is never automatically replayed.
This is not cross-module atomic rollback or unrestricted autonomous execution.

## Usage, logs and rollout

The existing provider analytics include module, workspace usage scope and suite
run ID alongside actual tokens, latency, request ID, estimated cost and sanitized
failure codes. The suite UI links to scoped usage logs. Per-step completion audit
events reuse the AI audit service. Keys, raw provider responses and prompts are
excluded from provider usage logs; private request text remains owner-bound in
the run record.

Migration `pg_20261024_014_suite` (SQLite `20261024_014_suite`) adds durable runs,
explicit inheritance and usage attribution. It is applied to the local configured
database. The backend and existing operator worker have been restarted.

## Verification

- Real Gemini produced a four-action plan that the live worker executed through
  CRM, FAM, SRM and PMS APIs after approval: task, cost center, invoice draft and
  workspace project.
- A separate employee-linked, minimally permissioned QA user created a real HRMS
  ticket through Gemini and the worker. That synthetic user was disabled afterward.
- A real five-module summary and scoped usage logs were verified. A transient
  provider timeout remains in the logs; summary-only requests use a smaller
  output schema and avoid sending the action catalog.
- The final five-module summary was recovered from its persisted run after a
  client timeout. Retrying an unchanged message in the UI retains the same
  idempotency key, and a still-planning run is polled instead of regenerated.
- Live browser verification covers inherited configuration, a real Gemini
  summary, completed receipts, usage logs, desktop and mobile layout. Final browser
  run had no page errors or failed HTTP responses.
- Backend tests cover role withdrawal, ownership, session binding, module reads,
  frozen approvals, stale records, idempotent execution, lost-response handling,
  workspace isolation, inheritance and data minimization.
- Validation: **113 backend regression tests**, **8 browser regression tests**,
  **1 opt-in real-Gemini browser test**, and the production frontend build passed.

Evidence lives in `docs/qa/suite-operator-2026-10-24/`. The live verifier is
`backend/scripts/verify_suite_operator_live.py`; it makes metered calls and creates
labelled QA records. The browser test is opt-in with `PMS_SUITE_LIVE=1`.

## Provider-independent PMS agent tools

The suite execution layer now supports all seven PMS capability groups through
the existing canonical PMS APIs. Gemini is the currently configured LLM;
OpenAI and Claude remain pending. This does not replace the browser's existing
local-first command/model routing in Assistant Studio.

Select a workspace and project in **AI agents → Connected operator**, then select
up to 25 tasks for references such as “this task”. The PMS local-brain panel also
links to this operator while preserving the project and workspace. Project context
includes authorized tasks, collaborators, sprints, private memory, working calendar,
playbooks, monitors, bounded autonomy policy and the latest execution receipts.
Follow-up requests retain their original project and selected tasks server-side.
Revising a draft supersedes its approval and retires its staged PMS proposals.

The new approved action adapters are:

- `pms.kickoff`: complete work breakdown, milestones, tasks, subtasks and blockers;
  `/ai-operator/setup/preview` and `/proposals/{id}/approve`.
- `pms.task_plan`: all nine existing task tools, including task fields, assignments,
  estimates, points, scheduling, sprint moves, dependencies, comments and checklists;
  `/workbench/plans/preview`, `/workbench/impact`, `/runs/{id}/approve`.
- `pms.schedule`: resolve relative start dates in the request timezone, then use
  `/workbench/schedule` for working days, holidays, estimates and dependencies.
  The resulting actual dated plan is frozen in the approval, not recalculated later.
- `pms.remember`, `pms.save_playbook`, `pms.event_rule`: validated private project
  artifacts using `/workbench/items`.
- `pms.run_playbook`: prepare the saved plan against fresh records using
  `/workbench/items/{id}/run`; the actual plan is frozen before approval.
- `pms.undo`: `/workbench/runs/{id}/undo-preview`; only supported inverse actions
  with unchanged current records can proceed, with manual recovery notices disclosed.
- `pms.watch`: delivery monitoring through `/ai-operator/monitors`.

Task execution yields the suite worker in `waiting_pms`, allowing the same worker
to run canonical PMS jobs without blocking itself. Parent receipts retain the PMS
run ID and individual task receipts. Failed checkpoints expose partial progress;
`POST /ai-operator/suite/runs/{id}/resume` resumes only an unchanged, approved PMS
checkpoint after canonical snapshot and permission checks. Cancellation stops
remaining work without reversing committed effects. Generic uncertain writes still
require reconciliation and are never retried automatically.

An LLM cannot create or expand administrator autonomy consent. Autonomous event
rules require prior explicit opt-in; actual automatic execution remains limited by
the existing policy to at most three status/priority updates. Other actions require
approval. Separate preflight snapshots may become stale after earlier approved
steps change the same task; consolidate related task edits into one task plan,
and schedule again after changing estimates when the schedule must use them.

The UI includes editable voice transcripts, natural-language plan revision,
readable impact previews, background status, cancellation, checkpoint recovery and
usage logs. Physical microphone capture remains deferred by the user; browser
speech-recognition integration is tested with simulated input.

Live evidence for the new tools is `pms-agent-live.json` in the QA directory:
real Gemini prepared priority/estimate/story-point/checklist actions and a separate
relative-date calendar schedule, both executed by the worker after approval.
Canonical task reads verified the saved effects. Both calls recorded provider
request IDs, tokens and cost estimates. `verify_pms_agent_live.py` reproduces this
metered QA with labelled records; `pms-agent-live.spec.ts` inspects those completed
runs in desktop/mobile UI without another model call.

Final verification for this extension: **125 backend tests**, **10 browser checks**
(including the real backend desktop/mobile review) and the production frontend
build passed. A cancellation-during-enqueue regression verifies that a cancelled
parent cannot reactivate its queued PMS child. Gemini remains the only enabled
provider; OpenAI, Claude and physical microphone testing are still pending.
