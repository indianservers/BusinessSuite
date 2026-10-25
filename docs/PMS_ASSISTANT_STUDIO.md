# Assistant workspace: all 19 feature areas

Open `/pms/assistant`, or use **Open your assistant workspace** in the floating
assistant. The existing operator remains available at `/pms/operator`. The new
workspace uses real authorized PMS records; its empty states do not contain
invented project metrics. Screenshots under `docs/qa/assistant-studio-*.png` use
the explicitly mocked browser-test fixture.

## Feature coverage

1. **Interactive plan editor:** edit supported task actions, priorities, statuses,
   assignments, titles, estimates, dates, checklist items, dependencies, sprints
   and comments. Add, remove or reorder steps while preserving prerequisite
   positions. A changed pending run becomes a new hash-bound revision.
2. **Targeted follow-ups:** reuse the local planning conversation and missing-field
   parser. Deadline/person/project questions expose answer chips; the user can
   edit an answer before submitting it.
3. **Persistent memory:** owner/project/scope-bound facts, decisions, terminology
   and constraints can be created, corrected with revision checks, or forgotten.
   Current memory is fetched on each brain turn. Local prompts rank relevant
   memories and expose truncation rather than silently claiming complete context.
4. **Undo/recovery:** new operator runs retain private before-state evidence and
   completion fingerprints. A successful supported run can prepare an inverse
   plan, which needs its own approval. Changed records reject recovery. Comments,
   clearing nullable fields, removed checklist identity/order, recurring completion
   and other unsupported inverses require manual recovery; the UI explains this.
5. **Execution tracker:** durable run status, step receipts and cursor-based events;
   cancel remaining work, resume paused runs and inspect completed work. Atomic
   and checkpointed execution reuse the existing worker.
6. **Voice conversations:** microphone capture, editable transcripts, spoken
   follow-up replies and explicit plan read-back. Browser speech recognition can
   use the browser vendor's service; text and plan controls remain available.
7. **Contextual references:** selected task context, a person in focus and a
   previous-project switch. Ambiguous people remain questions. A project switch
   is explicit; conversational references do not override authorization.
8. **Dependency/calendar scheduling:** estimates rounded to working days, all four
   dependency relationships, calendar-day lag, configured weekdays and holidays.
   Cycles and missing external-blocker dates produce errors. Finish To Start
   conservatively begins on the next working day. Suggestions need review.
9. **Workload-aware assignment:** available-capacity ranking, explicit skill
   filtering and away status. Choosing a person creates an editable assignment
   plan for selected tasks. Existing capacity assumptions are shown; calendars
   from external leave systems are not silently inferred.
10. **Project kickoff:** a local editable work-breakdown wizard builds project,
    milestone, task, subtask and blocker drafts. Creation uses the existing atomic
    setup proposal and approval implementation. Parent/blocker keys come first.
11. **Impact preview:** current before/after values, selected actions and downstream
    dependency records. Suggestions never silently reschedule downstream work.
12. **Natural-language search:** bounded local filters for overdue, blocked/blocking,
    high/urgent, completed and personally assigned work, plus title/key words.
    Results link to authoritative tasks. Complex phrasing can use the existing
    model conversation rather than being represented as arbitrary search support.
13. **Proactive delivery alerts:** existing durable monitors watch overdue, blocked
    and unassigned tasks. The dashboard refreshes visible insights every minute;
    delivery-watch creation is deduplicated. No external messages are sent.
14. **Playbooks:** save an explicit typed plan and prepare it repeatedly against
    current permissions/state. Task targets are explicit; invocation does not
    approve the proposed work.
15. **Event agents:** blocked, overdue, new-task and status-change rules observe
    project records through the durable worker. Baselines distinguish new events
    from deletion or unchanged state. Fingerprints/idempotency suppress duplicate
    proposals; revoked access or invalid plans pause the rule.
16. **Permission-aware autonomy:** disabled by default. An AI administrator can opt
    their own project agents into at most three status/priority update steps.
    Current role, project access, module settings and plan validity are checked
    again at execution. Automatic approvals bind the policy/rule revision; policy
    withdrawal or a rule pause stops queued automatic work. A fresh manually
    reviewed revision can continue permitted remaining work. Other actions continue through human approval. This is a
    bounded standing-consent policy, not unrestricted autonomous execution.
17. **Teaching queue:** submit a command paired with the corrected plan. Project
    administrators can review submitted examples and export approved examples.
    Owners' later edits reset approval. Exporting a dataset does not train or
    replace model weights automatically.
18. **Routing/cost dashboard:** local/cloud turn counts, fallback reasons, provider
    token usage, latency and priced/unknown costs. Metrics disclose sample limits
    and distinguish conversation metadata from billed provider records.
19. **Quality dashboard:** maintained evaluation cases, local-only evaluation runs,
    expected reply kinds/tool sets, validity checks, pass rates and latency.
    Explicit feedback tracks misunderstanding, repeated questions, incorrect
    plans/actions and rejected plans. Structural checks are not proof of semantic
    correctness; these scores are not a general model intelligence benchmark.

## Main implementation

- `backend/app/ai_operator/workbench.py`: authorization, artifacts, planning,
  scheduling, recovery, rules, reviewed teaching, evaluations and metrics.
- `backend/app/ai_operator/workbench_models.py`: owner/project-scoped artifacts
  and idempotent quality signals.
- Existing operator command, execution and worker code records recovery evidence
  and evaluates event rules. The brain context reads authorized project memory.
- `frontend/src/apps/project-management/pages/AssistantStudio.tsx` and its scoped
  stylesheet provide the responsive workspace. The floating assistant retains
  its existing invoice workflows and gains voice capture/workspace navigation.

## Added API routes

All routes below start with `/api/v1/ai-operator/workbench`:

- `GET/POST /items`; `PUT/DELETE /items/{id}` for typed persistent artifacts.
- `POST /plans/preview`; `POST /impact`; `POST /schedule`.
- `GET /insights`; `GET /search`; `GET /metrics`.
- `POST /runs/{id}/undo-preview`.
- `POST /items/{id}/run` for playbook proposals.
- `GET /teaching/review`; `POST /items/{id}/approve-teaching`;
  `GET /teaching/export` for administrator review/export.
- `POST /items/{id}/evaluate`; `POST /feedback`.

## Deployment and checks

Migration `20261024_010` / `pg_20261024_010` creates the two new tables after the
existing workspace-archive migration. Use the normal migration pipeline, e.g.
from `backend`: `python -m alembic upgrade head`. Development startup also runs
the migration when `DATABASE_AUTO_MIGRATE` is enabled. No destructive migration
or production reset is required. Application rollback retains execution evidence.

Run the existing worker (`python scripts/run_ai_operator_worker.py`) for durable
executions, delivery monitors and event rules. Rules never call a cloud provider;
their saved typed plans go through the canonical execution/approval APIs. Do not
start multiple unrelated user-owned development servers to demonstrate the UI.

Keep the previously prepared TensorFlow.js model assets in the frontend build.
Model/provider settings and cloud consent continue to use the existing settings
pages. No Ollama service is added.

Verification covers the real isolated database lifecycle, role boundaries,
memory scope/revisions, reviewed teaching, event deduplication, bounded auto
approval, working calendars, recovery/staleness, existing invoice chat and
browser flows. Screenshots are inspected at desktop and mobile widths; data in
these screenshot fixtures is test data, not the user's live project.

Latest verification: 94 isolated backend tests, 18 browser tests and the production
TypeScript/Vite build passed. The opt-in large pretrained-model smoke test is
skipped in the normal UI suite; its previous real WASM inference verification is
documented in `PMS_AI_OPERATOR_TFJS_BRAIN.md`. No paid provider call or production
database migration is needed to run the isolated regression suite.
