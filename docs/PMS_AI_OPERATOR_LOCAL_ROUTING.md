# Browser command routing and operator extensions

**Superseded local-router details:** see [standard TensorFlow.js model v2, expanded commands and follow-ups](PMS_AI_OPERATOR_LOCAL_ROUTING_V2.md). The sections below retain the original v1 implementation history; the current artifact is `model.json` plus `weights.bin`.

Implemented 24 October 2026. `/pms/operator` now defaults to **Local first · LLM when needed** for new voice transcripts and text commands. Gemini, OpenAI and Claude remain available for contextual planning and follow-up revisions.

## TensorFlow.js routing

The checked-in model is trained on **226 curated example utterances across 14 classes**: four priorities, five statuses, clearing assignments, checklist creation, sprint selection, explicit date scheduling, and cloud fallback. This is 226 examples, not 226 independent capabilities. Training examples include negations and unsupported requests in the fallback class.

- The CPU TensorFlow.js runtime loads lazily in a dedicated Web Worker. Command inference and slot extraction run in the browser; model files are served by this application, without a third-party model CDN or provider call.
- The model is a trained softmax classifier over a versioned binary word vocabulary. A reproducible training script generates the compact weights artifact committed at `frontend/public/models/operator/router-v1.json`.
- Local acceptance requires classifier confidence at least 0.90, a margin of at least 0.35 over the second class, at least 90% vocabulary coverage, agreement with the slot parser, and complete grammar consumption. Confidence is a classifier score, not a calibrated guarantee of correctness.
- Strict parsing preserves quoted checklist content, validates ISO calendar dates and date ordering, and supports up to three sequential clauses joined by `and`, `and then`, `then` or semicolons. With 25 selected tasks, this produces at most 75 reviewed steps.
- Unsupported wording, conditional commands, negation, relative dates, named assignments, dependencies, new projects and conversation revisions use cloud planning. Local-only mode stops with an explanation and makes no provider request. Cloud mode explicitly bypasses local routing.
- A failed model download, worker failure or inference timeout routes to cloud in automatic mode. Local-only mode stops. A missing/disabled provider prevents cloud fallback and produces a useful configuration message.
- A local plan still goes to the application backend. The backend reauthorizes the project and frozen selection, validates the typed tools, records task fingerprints and creates the existing approval. It makes **zero LLM calls** for that preview. Approval, stale-plan checks, durable execution and receipt replay protection remain mandatory. Browser output is untrusted, including output from a modified client.
- Browser speech recognition remains the transcript source and may itself use the browser vendor's speech service. This change does not claim offline speech recognition or real-time provider audio.

Examples:

```
set priority to high
mark selected tasks as done
set due date to 2026-11-05
schedule tasks from 2026-11-01 to 2026-11-05
add checklist item "QA and release review"
set priority to urgent and then add checklist item "QA review"
```

Sprint numbers in local syntax are database sprint IDs, not fuzzy names or ordinal sprint numbers. They appear in the plan and are validated against the current project before approval. People must still be resolved by cloud planning or selected through normal PMS UI.

To extend training, edit `frontend/src/lib/operator/commandCorpus.json`, then run `npm run train:operator` from `frontend`. When adding an executable intent, also extend the strict parser and add independent browser routing tests. Increment corpus/model versions together when changing the feature vocabulary or class contract. Training uses only the curated corpus, never private commands, task data or automatically accepted provider responses. The shipped model does not silently learn from users. Standard browser HTTP caching applies; no sensitive commands or custom model weights are written to local storage or IndexedDB.

Training checks its corpus accuracy before producing an artifact; training accuracy is not a generalization benchmark. Playwright tests separately exercise real browser worker inference, unseen slot values, multi-step commands, negation, unsupported conditions, invalid dates, no-provider local previews and local-only fallback blocking. The frontend production build includes the worker and static weights. See [TensorFlow.js model documentation](https://www.tensorflow.org/js/guide/models_and_layers) for the underlying model API.

## API changes

- `POST /ai-operator/commands`: optional typed `local_plan` using the existing `TaskPlan` schema. Without it, provider planning remains unchanged. Local plans do not require configured provider credentials; the existing provider field remains the preferred provider for later cloud follow-ups. A local plan cannot be used as a conversation revision.
- `GET /ai-operator/capabilities`: advertises local-plan support and mandatory validation/approval.
- `GET /ai-operator/analytics`: adds scoped `local_plans`, counted from durable `plan.local` events. These are previews, not guaranteed executions or monetary savings. API logs continue to count actual provider calls only. The provider settings page shows both counts separately.

## Project setup and monitoring extensions

The same implementation slice adds a collapsible operator panel and these authenticated endpoints, all relative to `/api/v1/ai-operator`:

- `POST /setup/preview`: turn a bounded brief, pasted meeting/document text or authorized template into a reviewed work breakdown for a new or existing project. Uses the selected provider, scoped keys, redaction and API telemetry. Up to 50 tasks and 20 milestones; local keys resolve subtasks and blockers. Existing PMS creation operations now support deferred commits.
- `GET /proposals/{id}` and `POST /proposals/{id}/approve`: owner-only proposal retrieval and existing shared AI approval execution. Creates project, milestones, tasks, subtasks and dependencies in a single transaction, with transactional receipts and replay protection. The preview is hash-bound to its approval. This is create-only work; it does not overwrite existing project fields.
- `GET /resolve?project_id=...&q=...`: bounded literal task-key/title and collaborator-email candidates; explicit selection is required. This is scoped matching, not unrestricted semantic search.
- `GET /capacity?project_id=...&week_start=YYYY-MM-DD`: weekly PMS capacity overrides, multi-assignee allocation and estimated hours from authorized projects, with explicit assumptions and counts of unscheduled tasks. It is an advisory view; no automatic rescheduling is performed.
- `GET /portfolio`: authorized project health, billing state, recorded budget/cost and delivery findings. Recorded cost fields are not reconciled finance data or forecasts.
- `POST /monitors`, `GET /monitors?project_id=...`, `PUT /monitors/{id}`: recurring checks for overdue, blocked and unassigned tasks. Bounded 15-minute to 7-day interval, 50 monitors per owner. The existing operator worker checks due monitors; a new findings hash updates stored findings and creates an AI audit event. Unchanged findings stay quiet. Checks make no provider calls and do not execute task changes. Current access and AI settings are rechecked; access revocation pauses the monitor and clears findings.
- `POST /retention`: administrator-scoped preview/execute purge of API metadata logs older than 30–3650 days. `execute` defaults false. Execution is audited. Run commands, plans, approvals, receipts and monitor findings are preserved; this is not a complete PII-erasure policy.
- `remove_dependency` task tool: requires the selected target and blocker and an existing dependency ID; shares canonical PMS deletion logic and transactional task execution.

Apply the normal PostgreSQL Alembic chain through `pg_20261024_003` before using setup proposals or monitors. A mirrored legacy migration is included. No production migration or live model call was performed during implementation. Local routing itself adds no database columns/tables.

## Remaining roadmap scope

These changes do not complete every future phase from the original roadmap. Remaining work includes leave/holiday/shift-aware optimization, CRM/SRM source linking, verified client-safe external message drafts/delivery, full command/plan retention controls, richer multilingual semantic matching and server-backed real-time audio. The browser router saves provider calls for a deliberately bounded command vocabulary; it is not a replacement for a general reasoning model.
