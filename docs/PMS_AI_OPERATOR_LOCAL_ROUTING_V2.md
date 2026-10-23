# Local PMS commands — TensorFlow.js model v2

Current expansion: [model v3 actions and follow-ups](PMS_AI_OPERATOR_LOCAL_ROUTING_V3.md), with 945 examples and 36 intent classes. This document preserves the v2 baseline.

Updated 24 October 2026. The operator now loads a **standard TensorFlow.js Layers model** using `loadLayersModel`:

- `frontend/public/models/operator/model.json`: topology, weights manifest and versioned vocabulary/intent metadata.
- `frontend/public/models/operator/weights.bin`: binary float32 weights and biases (18,048 bytes in this release).

The custom `router-v1.json` format has been removed. The model and weights are served from this application, with CPU inference in a lazy browser Web Worker. No provider or model CDN is involved in local inference. [TensorFlow.js serialization documentation](https://www.tensorflow.org/js/guide/save_load) describes the standard topology/manifest/binary format.

## Training

The release corpus contains **512 curated examples across 24 intents**. The classifier covers priorities, statuses, checklists, sprints, unassignment, scheduling, project/task/subtask creation, assignment, dependency creation/removal, clarification replies, help, cancellation, confirmation and fallback. Several intents share execution tools; the count is not 512 distinct business actions.

Run from `frontend`:

```powershell
npm run train:operator
```

This expands the curated command templates, trains a seeded softmax classifier, and saves `model.json` and `weights.bin` through TensorFlow.js serialization. The script reloads those exact files and checks prediction equivalence. It refuses to publish a model below 98% corpus accuracy. The current corpus fit is 100%; this is training accuracy, not a claim of universal command understanding. Independent browser tests exercise the saved model and unseen titles, keys and dates.

Edit `src/lib/operator/commandCorpus.json` for additional examples and `scripts/expand-operator-corpus.mjs` for built-in template changes. New executable actions also require a strict parser, scoped context resolution, server validation and tests. The script retrains from scratch; it does not silently fine-tune on private command history or on accepted LLM responses. The standard artifact can also be loaded with TensorFlow.js and compiled for further training with the same feature and label contract.

## Supported local commands

Select the destination project first for task operations. Project creation uses the currently selected workspace, or company/personal scope when no workspace project is selected. Titles containing spaces should be quoted in a complete command. Missing titles and keys are collected through follow-up questions.

```text
create project "Website launch" key WEB
create task "Fix checkout" key WEB-21
create subtask "Test payment" under WEB-1 key WEB-22
create task "Review API" key WEB-23 assigned to "alice@example.com"
create task "Release checks" key WEB-24 due tomorrow
assign tasks to "alice@example.com"
assign selected tasks to "Alice"
add dependency from WEB-1 to WEB-2
make WEB-2 depend on WEB-1
WEB-1 blocks WEB-2
remove dependency 4
set due date to tomorrow
set start date to next Monday
set due date to in 3 business days
schedule tasks for next week
set priority to high
mark tasks done
add checklist item "QA review"
```

Creation commands can include `key`, `under`, `assigned to` and `due` fields. A parent is always validated against the destination project. Assignment to a new project's collaborators is deliberately a separate operation after the project exists. Dependencies currently use the existing default Finish To Start type and zero lag; richer types/lag require existing PMS APIs or cloud planning. Dependency commands show both resolved endpoints in the frozen review selection.

The existing multi-step parser still supports up to three compatible task-update clauses, such as `set priority to high and then add checklist item "QA review"`. Arbitrary mixtures of creation and existing-task changes in one sentence require cloud planning. Model uncertainty or unsupported grammar triggers cloud fallback in automatic mode; Local only mode stops without a provider request.

## Follow-up questions

Example local dialogue:

```text
User: create task
Assistant: What should the task be called?
User: Fix checkout
Assistant: What unique key should I use?
User: WEB-21
Assistant: [reviewed task creation preview]
```

Assignment ambiguity produces numbered collaborator options. Reply with an option number, `the second one`, or an exact listed email. Missing dependency endpoints produce blocker/target questions. Missing or invalid dates produce date questions. Unknown task keys or duplicate task keys ask for a valid replacement. Context is refreshed from the authenticated project and only exposes authorized task/collaborator candidates, with truncation flags.

`help` explains supported commands. `cancel` discards the current local draft. `yes` cannot approve or execute work; the existing approval button is required. Voice answers use the same editable transcript and dialogue state as typed answers. Draft state stays in browser memory and clears when the project changes or the page reloads. It is not a durable cross-device conversation history.

Supported follow-up revisions on an existing task run include `make it urgent`, `mark them done`, `due tomorrow` and complete supported commands. They create a new reviewed run with the same frozen selection; the old pending approval is invalidated by the server. Revisions of active work must wait or cancel as before. A local creation workflow cannot broaden a frozen task revision; start a new command for that work.

## Relative-date rules

- `today` and `tomorrow` use the session's IANA timezone.
- `next Friday` means the next occurrence strictly after today, including seven days later if today is Friday.
- `next week` means next Monday, shown as an explicit ISO date in the preview.
- `in N days`, `in N weeks`, and `in N business days` support positive counts up to 999. Business days exclude Saturday/Sunday; organization holidays and leave are not deducted.
- Calendar arithmetic handles month/year boundaries without depending on the execution host timezone. A pending local dialogue retains the original command time/timezone, so a date does not silently shift while answering missing fields.
- Vague dates such as `sometime soon`, holidays, and staffing-based date optimization need clarification or cloud reasoning.

## Server execution and API changes

All local output is untrusted input. Existing role/module controls, assignment eligibility, same-project checks, dependency-cycle/date validation and mandatory approvals remain in force.

- `GET /api/v1/ai-operator/local-context?project_id=...` supplies bounded authorized project/task/collaborator context for local resolution. No provider is called.
- `POST /setup/preview` accepts an optional typed `local_plan`. It reuses scoped `OperatorProposal` records and shared approval execution without provider credentials or calls. Tasks support `existing_parent_task_id` and `assignee_user_ids`. Existing parents are fingerprinted and rechecked during execution; canonical PMS operations recheck assignment permissions. Project/task/subtask creation and receipts commit atomically and replay safely.
- `POST /commands` accepts local plans for validated parent revisions. Parent selection, hash and ownership checks are unchanged, and new approvals bind the revised plan.
- Setup previews record their planning source in AI audit metadata. Provider API logs continue to record actual calls only. Existing `local_plans` analytics counts task-run previews; setup proposals are separately auditable and are not included in that task-run count.

These changes add no new database schema beyond the earlier operator migrations. Apply those migrations before using operator proposals. Live provider calls, production migration and deployment were not performed during this change.
