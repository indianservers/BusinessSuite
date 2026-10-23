# PMS AI operator audit and roadmap — voice and text

Implementation follow-up: [phase 1 status, setup and limitations](PMS_AI_OPERATOR_PHASE_1.md). The findings below describe the pre-implementation audit; the regenerated API inventory also includes the new operator endpoints.

Next implementation: [phase 2 durable execution and follow-up commands](PMS_AI_OPERATOR_PHASE_2.md).

Reviewed 23 October 2026. Scope: competitor research and static inspection of the current working tree. No application changes, live database inspection, provider calls, or runtime certification were performed. Existing uncommitted work was preserved. Recommendations are proposed work, not implemented capabilities.

## Updated product objective

The target is a full PMS operator: users give objectives through voice or text; the operator resolves context, plans multiple dependent actions, asks only necessary clarifications, executes permitted work, and reports verified results. Summaries and writing assistance are supporting capabilities. This revision supersedes the original summary-first sequencing below.

**Current API inventory:** [human-readable list](PMS_AI_OPERATOR_API_INVENTORY.md) and [machine-readable source inventory](PMS_AI_OPERATOR_API_INVENTORY.json). The source snapshot contains **214 PMS routes, 39 AI-agent routes, 20 AI-copilot routes, and 4 adjacent scheduling routes**. Counts include aliases and the PMS WebSocket route; they are not counts of independent business capabilities or AI tools. Prefixes use the default `/api/v1`. Routes were parsed from source and PMS router inclusions, not exercised against a running deployment.

## Recommendation

Build one shared operator execution layer with voice and text as equal entry points. Reuse the existing agent registry, permission-scoped tools, approval executor, conversation UI, domain APIs, and audit infrastructure. Prioritize complete multi-step task operations and project setup; add background monitoring after durable execution works.

The LLM should interpret requests, draft content, and select approved tools. Deterministic services should calculate capacity, dates, dependency paths, costs, and permissions. Agents coordinate those services through bounded, observable runs. A chat window alone does not provide an operational project-management brain.

## Competitor findings: where AI is integrated

- **monday.com:** Sidekick provides conversational assistance with business context and actions. AI blocks operate inside board columns and workflows for summarization, categorization, extraction, and writing. Workflow action blocks can invoke Sidekick and configured CRM agents. Implication: integrate AI into fields and existing automation, as well as chat. Do not assume that every agent capability is available in every monday product or plan.
  Sources: [Sidekick](https://support.monday.com/hc/en-us/articles/26701503726610-Get-started-with-monday-sidekick), [AI blocks](https://support.monday.com/hc/en-us/articles/18433811274386-AI-blocks), [AI workflows](https://support.monday.com/hc/en-us/articles/11065311570066-Get-started-with-AI-workflows).
- **ClickUp:** Brain is exposed in the sidebar, tasks, Docs, comments, Chat, and project updates. Super Agents execute multi-step work with configurable tools, knowledge, and access. Implication: use the current record and workspace as context, and make agent work visible where people already collaborate.
  Sources: [Brain and agent feature catalog](https://clickup.com/features?gad=1), [Super Agents](https://help.clickup.com/hc/en-us/articles/31010910371991-What-are-Super-Agents).
- **Asana:** AI Studio embeds AI steps into workflows; AI Teammates can receive assigned tasks, use task context, and return work for human review. Implication: model an agent run as accountable work with an owner, inputs, result, and handoff.
  Sources: [AI overview and Teammates](https://help.asana.com/s/article/get-started-with-asana-ai), [AI Studio](https://help.asana.com/s/article/ai-studio).
- **Jira / Atlassian:** Rovo agents are available in chat, editing surfaces, automation, and work items. Agents can be assigned or triggered during workflow changes. Implication: attach runs and evidence to issues and delivery events, including backlog and release workflows.
  Sources: [Rovo agents](https://support.atlassian.com/rovo/docs/agents/), [Agents in work items](https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/).

These are documented product capabilities, not hands-on competitor tests. Availability varies by subscription, configuration, permissions, and rollout. No vendor pricing or ROI claims are assumed.

## Current PMS foundation: confirmed in code

1. **Four PMS agent definitions:** project status, task planning, deadline risk, and meeting notes. See `backend/app/ai_agents/services/registry.py:40`.
2. **Twelve registered PMS tools:** project/tasks/overdue tasks/milestones/comments/members/workload/dependencies, plus task/subtask/risk/report proposals. See `backend/app/ai_agents/tools/definitions.py:39`.
3. **Real LLM orchestration:** `services/orchestrator.py` runs a bounded tool loop, stores conversations, checks permissions and usage, records token cost, and invokes `services/openai_service.py`. Provider credentials are backend-side. Presence of code does not establish deployment configuration.
4. **Reviewed write actions:** `services/approval_executor.py` routes approved PMS task, subtask, and risk creation to `adapters/pms_ai_adapter.py`, with locking and permission checks. This is more advanced than the older AI README, which says approval only changes status.
5. **Frontend exists:** shared agent chat/configuration/approval components and `frontend/src/services/aiAgentsApi.ts` already exist. ProjectDashboard and TaskDetail use AskAiButton. TaskDetail includes summarize and next-step prompts.
6. **Useful domain foundation:** PMS has tasks, multi-assignee relationships, dependencies, milestones, sprints, time logs, reports, risks, files, Docs, portfolio views, and workspace automation. Each still needs a deliberately scoped AI tool contract.

## Gaps and risks to address first

- **High — planner is a prototype:** `routes.tsx:94` sends `/pms/ai-planner` to ImpactWorkHubPage. That page initializes hardcoded context assets and suggested tasks; accepting them updates React state. It does not establish durable LLM-generated plans. Replace this flow with real context retrieval, saved proposals, and reviewed persistence.
- **High — fragmented provider paths:** `app/ai_agents/services/openai_service.py` calls a real external model, while `app/apps/ai_copilot/services/provider.py` selects a mock adapter or an ExternalProviderAdapter that raises AIProviderNotConfigured. A provider settings screen cannot be taken as evidence of production connectivity. Choose one provider interface and connect both use cases to it.
- **High — task context is incomplete:** the registered PMS tools include project reads but no focused get-task tool. AskAiButton passes a task ID, while system_prompt_builder only tells the model to use tools for details. Add an authorized task-context resolver for task + parent project + comments + subtasks + dependencies; explicitly select the intended agent code rather than relying on the first active agent.
- **High — context truncation can distort conclusions:** task reads cap at 200, overdue reads at 100, comments at 100 with text truncation; tool results are sliced to 12,000 characters in the orchestrator. Return valid structured results with pagination, totals, as-of time, and explicit completeness flags. Compute aggregate metrics server-side.
- **High — AI writes need domain parity:** adapter task creation writes `assignee_user_id`, whereas current task models also expose PMSTaskAssignee relationships. Review synchronization, eligible membership, status/priority vocabularies, custom task types, and required fields against the normal create service. This is a compatibility concern requiring tests, not a confirmed runtime failure.
- **Medium — workload is too narrow for staffing decisions:** the AI adapter groups tasks within one project by legacy assignee and sums counts/points/hours. It does not establish cross-project availability, working calendars, leave, shared assignments, or skills. Use the canonical capacity service before recommending reassignment.
- **Medium — automation has no agent action in the reviewed surface:** AutomationAIPage offers task-created/status-changed triggers and set-priority/add-assignee actions. Add an explicit agent action backed by durable jobs, scoped permissions, deduplication, retry limits, and run history.
- **Medium — chat interrupts the workflow:** AskAiButton navigates to `/ai-agents/chat/...`. Add a reusable record-aware side panel and inline proposal review while retaining the shared conversation backend.
- **Medium — operational readiness is unverified:** deployment keys, actual model quality, latency, tenant isolation under adversarial inputs, scheduled-run behavior, and real connector access were not tested. Prompt scanning exists but cannot replace authorization or output validation.

## Where to integrate in PMS

### First release: reuse the foundation

1. **Task detail and task composer — Task Assistant.** Summarize discussion, draft descriptions and acceptance criteria, break work into subtasks, and suggest next steps. Retrieve focused task context; show source links and editable drafts. Persist only accepted changes. Primary owners: TaskDetail, CreateTaskModal, PMS adapter/tool definitions.
2. **Project dashboard and Reports — Status Agent.** Generate a weekly report with completed work, blockers, overdue items, milestones, and decisions needed. Compute metrics from complete authorized queries; let the LLM explain them. Show source records and reporting period. Start with manual generation and save draft reports before scheduled distribution.
3. **AI Planner / new project — Planning Agent.** Convert a brief into proposed tasks, milestones, dependencies, estimates, and clarification questions. Replace the local prototype. Users review a structured plan, edit it, then commit it atomically with a plan ID and idempotency key. Distinguish assumptions from source requirements.
4. **Risk register, Gantt, and Timeline — Delivery Risk Agent.** Calculate overdue/blocking paths with deterministic logic, then explain risk and propose mitigations. Show affected tasks and rules behind the finding. A model assessment is not a calibrated probability. Replanning and deadline changes require review.

### Second release: event-driven workflows

5. **Docs, Files, and collaboration — Meeting / Knowledge Agent.** Ingest permitted text or uploaded notes; extract decisions and action items with citations to source passages. Add document parsing and permission-aware retrieval. Audio transcription needs its own connector and retention policy; it is not provided by the current notes agent definition alone.
6. **Backlog and Sprints — Backlog Agent.** Identify duplicates and incomplete requirements, suggest task types and sprint candidates, and draft sprint reviews. Use actual velocity/capacity calculations. Never silently move items between sprints.
7. **Workload and resource planning — Capacity Agent.** Explain overload and propose redistribution using multi-assignee allocation, leave, calendars, skills, and cross-project work. Preview before/after capacity; manager accepts assignments.
8. **Automation — Agent workflow action.** Add classify request, summarize change, propose next action, and detect stalled work steps. Allow configured low-impact classifications to run automatically; route material record changes to approval. Prevent AI-generated events from recursively retriggering the same rule.
9. **Board, List, and Custom Fields — AI fields.** Offer opt-in summary, category, missing-information, and risk-reason fields. Recompute only when relevant inputs change, record provenance, and display usage limits. Separate generated suggestions from authoritative human-entered fields.

### Third release: BusinessSuite differentiation

10. **Portfolio / Command Center — Portfolio Agent.** Explain cross-project risks, resource conflicts, and pending decisions using permission-filtered aggregates and drill-down links. Add semantic search only after permission-aware indexing and revocation are designed.
11. **Project financials — Commercial Health Agent.** Combine authorized budgets, time, billing, procurement, and approved commercial scope. Calculate variance and burn in services; draft explanations and change-request proposals. Finance access remains independently enforced.
12. **CRM/SRM-to-PMS handoff — Delivery Intake Agent.** Turn approved commercial commitments into draft delivery plans and flag missing scope, owners, or deadlines. Keep each commitment linked to its source record and avoid granting access to unrelated CRM/finance/HR information.
13. **Client portal — Client Update Assistant.** Draft client-safe updates using an explicit external visibility policy. Internal comments, financials, and staff information must not leak into summaries. Require review before sending or publishing.

## Proposed shared architecture

PMS surface or domain event → authenticated context resolver → policy and budget checks → agent orchestrator → provider gateway → validated tools → draft/proposal → approval where required → canonical PMS service → durable run log and result in the originating screen.

- **Context:** derive tenant/workspace/project/task from server-authorized entities. Return facts with source IDs, timestamps, pagination, and completeness. Enforce read permissions during retrieval and again when opening a source.
- **Provider gateway:** unify the current paths; support only implemented adapters; configure model by use case; validate structured outputs; impose request deadlines, token budgets, and bounded retries. Cache only within the same authorized scope and data version.
- **Tools:** call canonical domain services instead of duplicating task creation logic. Validate dates, assignees, task types, dependencies, and required custom fields. Keep dependency and workload arithmetic outside the LLM.
- **Run lifecycle:** proposed model: queued → running → awaiting_review → succeeded / failed / cancelled. Store initiating user or service principal, tenant, policy version, sources, model/prompt version, tool results, cost, and approval linkage.
- **Background execution:** durable queue, event outbox, idempotent writes, bounded retries, cancellation, stale-data revalidation, and concurrency controls. Scheduled agents need scoped identities rather than unrestricted system access.
- **Knowledge:** begin with structured reads; add permission-aware document retrieval as a separate capability. Handle deletion, permission revocation, and index updates before presenting search as complete.
- **Human controls:** preview actions, edit/reject proposals, explain sources, cancel runs, and disable an agent per workspace. A reversible classification can use explicit workspace policy; sending updates and changing schedules should start with review.

## Validation and success measures

Use existing AI RBAC/context/action test suites as a starting point; their presence does not prove the proposed PMS flows work. Add meaningful coverage for task/project mismatch, unauthorized sources, stale proposals, assignment compatibility, duplicate execution, dependency cycles, partial context, provider failure, and malicious instructions embedded in business content.

Evaluate representative PMS scenarios with human review: factual correctness, source support, valid plans, accepted versus rejected suggestions, time saved, latency percentiles, cost per accepted action, and authorization failures. Establish a baseline before setting numerical targets. LLM-generated confidence is not an accuracy measure.

## Operator readiness: what is actually supported

- **Text commands: partial foundation.** `POST /api/v1/ai-agents/{agent_id}/chat` takes a message and entity context. Conversations and messages persist. This is agent-specific synchronous chat, not a general command/run API.
- **Multiple tool calls: already supported, within one request.** The orchestrator calls tools and returns results to the LLM up to the configured call budget. This is useful bounded reasoning, but not a persisted execution graph. A request ending or a pending approval does not establish automatic continuation of dependent work.
- **Real PMS actions through AI: narrow.** Approved task creation, subtask creation and risk creation have real executor routes. Project creation, task updates, reassignment, scheduling, dependencies, sprint changes, Docs, timers and bulk edits have HTTP APIs but are not registered PMS agent actions in the reviewed registry.
- **Approval replay: partly solved.** The existing executor locks an approval row and returns a stored result when already executed. Extend that pattern to command/run/step idempotency; do not claim replay protection is wholly absent.
- **Voice: not found in the reviewed PMS/AI implementation.** No speech capture/transcription/playback or voice-session API was found in the PMS frontend, shared agent UI, agent backend or copilot backend. Existing realtime PMS events are record-update transport, not audio or streaming model responses.
- **Context: partial.** Conversation history and one related entity are persisted; there is no established command selection snapshot, pronoun resolution contract, multi-record reference resolver, locale/timezone-aware command parser, or versioned plan across follow-up turns.
- **Background operation: missing in the reviewed operator paths.** No durable PMS agent worker/run lifecycle, checkpoint-resume API, execution cancellation or scheduled AI monitoring contract was established. Existing deterministic automation runs inside task transactions and has a read-only event feed.
- **Capacity: existing read API, incomplete operator semantics.** `/project-management/workload` reads accessible projects and weekly capacity, but currently discards `teamId` and selects tasks through the legacy assignee field. It cannot yet establish leave-aware, skills-aware, multi-assignee redistribution.
- **Scheduling: individual date edits exist.** Task and epic schedule APIs and dependency endpoints are present. Individual schedule edits return dependency warnings; this is not a whole-plan constraint solver or atomic rescheduling preview/commit contract. The separate `/scheduling` router currently serves CRM, SRM/inventory, FAM and HRMS sources, not PMS.
- **Copilot confirmation is not execution evidence.** `/ai/agent-action/confirm` sets status and a result flag based on action type, logs and commits the AI action record. Its reviewed handler does not call the business mutation for create-task/add-note/update-field. Do not surface its `executed` flag as proof of PMS changes. Route operator execution through real domain services and persist resulting record IDs.

## Current API families to reuse

All paths in this section are relative to `/api/v1/project-management` unless another prefix is shown. This is the functional shortlist; the linked inventory lists every source-declared method, path, handler, input annotation and source line.

- **Find and inspect work:** `GET /workspaces`, `/workspaces/{workspace_id}/overview`, `/projects`, `/projects/{project_id}`, `/tasks`, `/tasks/{task_id}`, `/projects/{project_id}/tasks`, `/users/search`, `/projects/{project_id}/members`. Add an operator resolver above these APIs to distinguish duplicate names and bind task keys, project names, people, and selected records to authorized IDs.
- **Create a project:** `POST /intake`, `/intake/{intake_id}/review`, `/projects`; `GET /project-templates`; `POST /projects/{project_id}/clone` and `/projects/{project_id}/members`; `PATCH /projects/{project_id}`. Existing project setup actions need agent wrappers and a versioned multi-step plan.
- **Create and modify tasks:** `POST /projects/{project_id}/tasks`, `/tasks/{task_id}/subtasks`; `PATCH /tasks/{task_id}`, `/tasks/bulk`; `GET /tasks/{task_id}/subtasks`; `DELETE /tasks/{task_id}`; `POST /trash/tasks/{task_id}/restore`. Reuse task-type/custom-field validation. Bulk schema currently exposes status, one assignee, priority, sprint, release and component; no per-task date changes, multi-assignee edit contract, or record-version preconditions.
- **Dependencies and dates:** `GET /gantt`, `/roadmap`; `PATCH /tasks/{task_id}/schedule`, `/epics/{epic_id}/schedule`; `POST /task-dependencies`, `/tasks/{task_id}/dependencies`; `GET /tasks/{task_id}/dependencies`; dependency delete routes. Add multi-record impact preview, cycle/constraint validation and accepted-plan commit.
- **Sprints and delivery:** `GET /backlog`, `/projects/{project_id}/sprints`; `POST /tasks/{task_id}/move-to-sprint`, `/tasks/{task_id}/remove-from-sprint`, `/sprints/{sprint_id}/start`, `/sprints/{sprint_id}/complete`; `GET/PATCH /sprints/{sprint_id}/review`; release CRUD/readiness and epic/component routes. Add tools and eligibility checks rather than duplicate sprint CRUD.
- **Collaborate and produce work:** task comment CRUD, task checklist and tag APIs; `GET/POST /workspaces/{workspace_id}/direct-conversations` and message routes; `POST /projects/{project_id}/docs`, `GET/PUT /docs/{document_id}` and revision reads; attachment/file APIs. Add source-grounded extraction and explicit destination/recipient resolution before posting.
- **Track effort:** `GET /timer`; `POST /timer/start`, `/timer/stop`, `/timer/discard`; time-log CRUD, task time-log routes, timesheet submission/approval. Add agent tools and unambiguous task/time parsing. Timesheet approval uses the actual approver permission independently of voice input.
- **Risk and analytics:** risk CRUD; `/workload`, `/projects/{project_id}/workload`, `/dashboard/{project_id}`, `/portfolio/*`, `/reports/*`, project velocity and sprint burndown. Reuse metric calculations; expose complete, structured, provenance-bearing results to the operator.
- **Automation and events:** workspace automation CRUD and `/automation-runs`; `GET /workspaces/{workspace_id}/workflow-events`; `/realtime/config`, `/realtime/events` and the realtime WebSocket. The event feed has cursors/replay/event IDs for deduplication, but does not execute workflows or provide a durable job queue.
- **Existing AI control APIs:** `/ai-agents/conversations` and messages, `/{agent_id}/chat`, `/approvals/pending`, `/approvals/{approval_id}/approve` and `/reject`, `/logs`, `/usage/*`, `/security/*`, `/analytics/*`, `/cost/*`, feedback and configuration. Extend these controls; avoid a second independent approval/audit subsystem.

## AI tools to add over existing domain services

The current twelve PMS tools are eight data reads plus four draft/proposal tools. Add structured, permission-scoped tool definitions and real executors in stages; HTTP endpoint existence alone does not allow an LLM to invoke it.

- **Resolve/read:** `pms_resolve_entities`, `pms_get_task_context`, `pms_search_tasks`, `pms_get_project_configuration`, `pms_get_sprints`, `pms_get_capacity`, `pms_get_document`, `pms_get_run_result`.
- **Project setup:** `pms_propose_project`, `pms_clone_project_template`, `pms_add_project_member`, `pms_create_milestone`, `pms_create_epic`. Missing domain capabilities such as generic milestone editing must be added separately if exposed.
- **Task execution:** `pms_update_task`, `pms_bulk_update_tasks`, `pms_set_assignees`, `pms_add_checklist_items`, `pms_add_dependency`, `pms_remove_dependency`, `pms_move_to_sprint`, `pms_set_custom_field`.
- **Planning:** `pms_preview_plan`, `pms_validate_plan`, `pms_commit_plan`, `pms_preview_reschedule`, `pms_commit_reschedule`. These require new orchestration/domain contracts below, not thin aliases for single-record updates.
- **Collaboration and effort:** `pms_post_comment`, `pms_create_document`, `pms_update_document`, `pms_start_timer`, `pms_stop_timer`, `pms_log_time`. Add messaging/delivery tools only with recipient and external-visibility checks.
- **Monitoring:** `pms_create_monitor`, `pms_pause_monitor`, `pms_get_monitor_runs`, and scoped alert tools after durable workers exist.

Each tool needs a typed input/output schema, required permission, action scope, side-effect classification, approval policy, preconditions, idempotency semantics, timeout, audit schema and result record IDs. Share the canonical service underneath HTTP handlers and tools; current handlers often commit independently, so chaining them does not give an atomic multi-record transaction.

## Proposed API additions — design only, not current routes

Use `/api/v1/ai-operator` for transport-neutral commands and runs, with PMS-specific planning APIs under `/api/v1/project-management`. Names below are proposed contracts and must go through implementation review.

### P0: commands, context and durable execution

- `POST /ai-operator/sessions` — bind an authenticated interaction to allowed workspace/project scope, timezone, locale and optional existing conversation. Return session ID; client-selected IDs never grant access.
- `POST /ai-operator/resolve` — resolve people, project names, task keys, dates and selected records; return authorized candidates, ambiguities and required questions.
- `POST /ai-operator/commands` — accept text or a finalized transcript, session ID, context/selection snapshot, client command ID and idempotency key. Return `202` plus durable command/run ID; return structured clarification state where necessary. Neither text nor speech bypasses execution policy.
- `GET /ai-operator/runs/{run_id}` and `GET /ai-operator/runs` — status, steps, affected records, cost, partial results and permissible next actions.
- `GET /ai-operator/runs/{run_id}/events` — SSE progress with resumable event cursor. Reuse existing transport infrastructure where practical, but isolate operator events and authorization from PMS record updates.
- `POST /ai-operator/runs/{run_id}/clarifications` — answer ambiguity or change constraints; produce a new plan revision when meaning changes.
- `POST /ai-operator/runs/{run_id}/cancel` — stop future work cooperatively, show committed effects and in-flight work. Cancellation cannot retract already-sent messages or guarantee rollback.
- `POST /ai-operator/runs/{run_id}/resume` — resume a checkpoint only after rechecking authorization, dependencies and record versions; skip completed idempotent steps.
- `GET /ai-operator/capabilities` — list actions available for the current scope, role, enabled modules and provider configuration. Include unsupported intents rather than letting the model invent tools.

Extend the existing `/ai-agents` approval records with run ID, step/group IDs, immutable plan revision/hash, target record versions, expiry and permitted effects. Keep existing approve/reject endpoints as the approval authority. An approval grants only the displayed plan revision; follow-up changes invalidate affected approvals.

### P0: voice input and output

- `POST /ai-operator/voice/sessions` — establish a short-lived authorized audio session, language/locale, allowed scope and server-enforced provider settings. Use WebRTC or a dedicated WebSocket transport; do not expose permanent provider keys.
- `POST /ai-operator/voice/transcriptions` — push-to-talk/upload fallback returning editable transcript, uncertainty markers and utterance ID. Partial transcripts never trigger writes.
- `POST /ai-operator/voice/speech` — synthesize concise result/clarification text with cancellation and text fallback; authorize any record-derived content.
- `DELETE /ai-operator/voice/sessions/{voice_session_id}` — stop capture/stream and close credentials. UI also needs microphone permission, visible recording state, interruption, device errors and transcript correction.

Finalized speech and typed text enter the same command API and produce the same plan and authorization decisions. Bind “yes, apply it” to one visible pending plan and exact revision; ambiguous voice confirmation asks a clarification. Define audio/transcript retention and deletion behavior; transcription accuracy is not authentication. Voice interruption stops playback/capture separately from cancelling a running business operation.

### P0/P1: domain gaps for reliable multi-record work

- `POST /project-management/plans/preview` — propose new-project or task-batch work from authorized source references; return stable temporary IDs, assumptions, dependencies, validation errors, required permissions and before/after effects.
- `POST /project-management/plans/{plan_id}/validate` — validate plan revision, required custom fields/types, assignment eligibility, cycles, dates, budgets and current record versions.
- `POST /project-management/plans/{plan_id}/commit` — apply accepted local PMS changes atomically when feasible. Map temporary IDs to created record IDs and return a durable receipt. Require idempotency key and approved revision where policy requires approval. Keep approval and commit as distinct recorded operations.
- `POST /project-management/reschedules/preview` and `POST /project-management/reschedules/{plan_id}/commit` — calculate impact across dependencies and calendars, expose conflicts and trade-offs, revalidate current versions before applying accepted dates.
- Extend `PATCH /project-management/tasks/bulk` or introduce a versioned batch-change service for per-task changes, add/remove/replace assignees, date updates, expected versions, affected-count limits, and explicit all-or-nothing versus best-effort semantics. Do not silently change the existing endpoint contract.
- `GET /project-management/resource-availability` — combine authorized project allocations, multi-assignee effort rules, working calendars and approved leave for a time window. Return missing inputs and provenance; do not expose private leave reasons or HR records to PMS users.
- `POST /project-management/documents/{document_id}/extract-actions` — proposed extraction job returning cited, editable action proposals. The current document routes use `/docs`; reconcile naming before implementation or attach this action to `/docs/{document_id}`.
- Cross-module handoff needs source-specific adapters and a validated source-reference contract. Reuse existing SRM/PMS links where available; avoid copying records or assuming one transaction across services.

### P1/P2: recurring goals and safe recovery

- `POST/GET /ai-operator/monitors` and `PATCH /ai-operator/monitors/{monitor_id}` — scoped objective, trigger/schedule, budget, escalation destination and pause state; evaluate through the same run engine.
- `GET /ai-operator/monitors/{monitor_id}/runs` — actionable findings and execution history; deduplicate repeated findings.
- `POST /ai-operator/runs/{run_id}/compensations/preview` and `/commit` — only supported compensating actions against unchanged compatible records. Do not promise universal undo; sent communications and external effects may be irreversible.
- Extend existing usage/security settings for per-workspace tool policies, spending caps, allowed providers, audio retention, schedule execution identities and emergency disablement.

## Multi-step execution contract

Persist a run with a versioned DAG of steps, typed inputs, output references, dependencies, permissions, effect category and preconditions. Proposed lifecycle: `queued → resolving → needs_clarification | planning → awaiting_approval | executing → succeeded | partially_succeeded | failed | cancelled`. Individual steps also retain attempts and committed receipts. These are proposed states, not the existing approval enum.

Workers acquire leases, checkpoint after every side effect, and use step idempotency keys with business uniqueness constraints. Recheck access and versions immediately before a write. A transaction handles related local changes; an outbox and compensating actions handle external effects. Do not hold database transactions across model or audio calls. A failed dependent step blocks its children; independent steps follow the plan's declared execution policy. Expose partial effects and a recovery option instead of reporting blanket success.

Persist selection and referents, not just raw transcript history: “those tasks” binds to the explicit authorized ID set and selection version from the relevant turn. “Next Friday” uses the session timezone and displays the interpreted date. Never broaden a frozen selection silently when new matching tasks appear. Context edits create a new plan revision and revalidate the affected steps.

## Revised delivery roadmap

1. **P0 / foundation and capability truth:** unify real provider execution, expose runtime capabilities, audit domain service parity, fix copilot success reporting, add focused context/entity resolution, design durable runs and step receipts. Gate: all successful actions map to verified business record changes; supported and unsupported commands are explicit.
2. **P0 / voice and text task operator:** typed commands plus push-to-talk transcription, editable transcript, selection-aware conversation, multi-step task update/assignment/checklist/dependency/sprint tools, preview, policy-based approval and execution progress. Gate: the same voice/text intent yields equivalent authorized plans; ambiguous names/dates are resolved; interruption, retries, stale records and partial failure work correctly.
3. **P1 / full project setup:** real planner replaces demo; template/project/task/milestone/dependency setup uses plan preview, validate and atomic local commit. Gate: accepted project setup persists end-to-end; retry creates no duplicates; invalid required fields or cycles block the whole local plan.
4. **P1 / replanning and resources:** constraint-aware schedule impact, calendar/leave-aware capacity, multi-assignee edits and before/after staffing scenarios. Gate: schedule feasibility and capacity reconcile with services; missing data and infeasible deadlines are explained.
5. **P2 / continuous operator:** event-driven monitors, scheduled runs, notes-to-actions and reviewed notifications, with budgets, scoped identities, deduplication and recovery. Gate: worker restart resumes safely, permission revocation stops subsequent effects, and unchanged findings do not create repeated alerts.
6. **P2 / BusinessSuite delivery brain:** authorized CRM/SRM scope-to-project handoff, commercial impact and client-safe communications. Gate: source commitments remain linked; module permissions hold across every step; external effects have independent receipts and retry policy.

No delivery dates or development effort estimates are assigned until team capacity and target deployment constraints are established. The first release should prove meaningful execution, not spend its scope on summaries alone.

## Command acceptance scenarios

- “Assign these five tasks to Arun, set priority High, add a review checklist, and move them to the next sprint.” Resolve Arun and sprint; freeze five IDs; preview field/checklist/sprint changes; execute authorized steps; return record receipts. Do not modify an ambiguous sixth task.
- “Create an onboarding project from this approved engagement, finish in three weeks, and use our standard template.” Resolve source/template; verify approval and access; propose project, tasks, owners and dependencies; surface capacity conflicts; commit approved plan and preserve source links.
- “Move launch forward one week but keep client approval and QA.” Calculate constraints and show feasible options or explain infeasibility. Preserve explicit milestones; no silent reduction of scope or fabricated capacity.
- “Arun is away next week; redistribute his urgent work.” Use approved availability metadata and eligible alternatives; preview redistribution, dates and load; execute accepted assignments without exposing leave reasons.
- “Start a timer on this task; when I stop, log the time and post a progress note.” Resolve selected task; start timer; persist follow-up intent; stop/log once and review the note according to policy. A later utterance must not target an unrelated timer.
- “Cancel that” during execution. Clarify only if multiple runs are plausible; cancel the selected run; show what already committed and what stopped. Offer only supported compensations.
- Worker restarts after task creation but before dependency creation. Resume from receipt, reuse created IDs, avoid duplicate tasks, then create dependencies or report a recoverable failure.

Validate with unit/integration and end-to-end scenarios covering tenant/project access, ambiguous names, timezone dates, speech correction, malicious business content, approval revision binding, concurrency, idempotency, provider timeout, worker restart and partial external delivery. Measure end-to-end command completion, valid plans, unauthorized/duplicate effects, recovery success, correction burden, latency and cost per completed objective.
