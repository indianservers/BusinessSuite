# Conversational workload rebalancing

## Fresh review of remaining work

In a fresh conversation, `Review remaining PMS workflow #ID` prepares the
never-dispatched remainder of a paused pure-PMS workflow. The ID is the suite
workflow ID, not the native execution ID used by undo. The current workspace and
selected project must match, and all source targets are authorized again.

For an eligible single-project paused receipt-only workflow, the bot and expanded
workspace offer **Review remaining tasks**. This starts a fresh local-provider
conversation and prefills the explicit command; it does not send, approve or
execute it. The shortcut is hidden when another project is selected, when the
workflow is complete, or when the remaining actions require historical text or
are already queued. Sending the request still revalidates current access and
native eligibility before preparing new previews.

Confirmed native executions are excluded. Remaining structured task changes are
validated against current records and collaborator eligibility before entering a
new draft. Workload guards are refreshed, dependency references to completed steps
are removed, and the new native task groups execute atomically only after a new
approval. Historical prompt/source text is not carried forward.

Only after new previews and their approval are ready does a bounded transaction
retire the old pending native approvals and supersede the original workflow. The
new approval binds the source ID and plan hash; existing receipts are retained.
Already queued, partially executed or uncertain native work is rejected. Pending
comments and other text/content intentions require a new explicit request from
current sources instead of implicit historical transfer.

The broader regression gate passed seventy-one tests in
`.local/business-suite-qa-43fa6b8baa864d58ba7728afb6b63c8a/results.xml`.
After adding early native validation, four focused cases passed in
`.local/business-suite-qa-0bd4fc5bbd074472b278dcbc4b5b5c3a/results.xml`.
They cover fresh approval/execution of the remaining priority change, unchanged
completed assignment, source retirement and duplicate rejection, text refusal,
queued-work refusal and a newly inactive intended collaborator. Counts overlap.
Live deployment and concurrent race/load acceptance remain unverified.

The UI starter and shared structured-action classifier passed four focused
backend cases in `.local/business-suite-qa-fffe1349f71e4f169afb696310dd3315/results.xml`,
ten targeted browser tests, and `npx tsc --noEmit`. Browser coverage uses development
fixtures and verifies no automatic write requests and project-selection hiding;
it does not establish authenticated live UI acceptance.

## Confirmed receipts after assignment changes

An assignment can invalidate the workflow's old history permission fingerprint.
GET status now supports a narrow read-only projection for a pure PMS task-plan
workflow with at least one confirmed native completion. It verifies owner/company
provenance, current project/task access, exact parent/child plan and approval
linkage, and native execution evidence. The response contains status and minimal
confirmed receipt metadata, with no historical prompt, source context, action
payload, approval or resume capability. Original history proofs are not resealed.

For multiple task-plan steps, every child and its currently authorized targets are
checked. Only completed native executions produce result cards, and only committed
parent receipts appear as workflow receipts. Remaining steps show `not_confirmed`.
A two-step integration case confirms one assignment, a paused parent, unchanged
second task and still-unapproved second child. Seven recovery/partial-workflow
checks passed in `.local/business-suite-qa-42435bd3e7b04690b6ba3807cbb6ae1a/results.xml`.
This is read-only evidence, not authority to resume old work or expose cross-module
history.

If the native child completed but the parent is still collecting its receipt,
the parent remains `waiting_pms` and exposes no invented parent receipt. Foreign
users and revoked current access remain denied. Conversation memory and stale-chat
continuation stay protected; this status projection does not reopen them.

Thirty-three assignment-recovery/PMS-agent/stop-control checks passed in
`.local/business-suite-qa-07b60cdd50444a05b6a5fbf51acf13eb/results.xml`.
They include pending receipt collection, confirmed completion, historical content
exclusion, foreign actor denial and current access revocation. Live deployment
acceptance remains separate.

Receipt-only bot results disable the composer and offer **Start new conversation**.
The workspace disables draft review and hides feedback that would depend on the
old history context; confirmed native results are labeled as execution receipts.
Starting fresh clears local conversation state without approving, resuming or
posting feedback. Old cancel/resume controls stay hidden in this read-only view.
Eight targeted browser checks, sixty-one earlier ActionBot regression
checks and `npx tsc --noEmit` passed. These browser checks use development-only
simulated fixtures on Vite5186 and do not prove authenticated live deployment.

## Reviewed assignment recovery

The native Workbench undo endpoint can prepare an inverse for a completed
rebalance. Assignment changes invalidate the original ACL fingerprint, so recovery
does not reuse or reseal the original approval. It authenticates the completed
record's signed owner/company provenance, checks current native project/task
permissions and exact after-state, then issues a new inverse plan with a fresh
workload guard and separate approval. Immutable run-state evidence has a narrow
recovery lookup; memory, skill and normal execution visibility are unchanged.

A later manual assignment blocks recovery. Foreign users and tampered signatures
are rejected. Repeating a completed inverse returns its existing completion rather
than writing again. Twenty-three focused assignment/guard/Workbench/hidden-field
context tests passed in
`.local/business-suite-qa-e8854729de1c47f38e10b78f1cc9f602/results.xml`.
The local bot also accepts an explicit fresh request such as `Undo PMS run #22`.
The ID is a native PMS execution ID, not a conversation or suite-run ID. Native
recovery verifies provenance and current access; the normalized parent task plan
retains the inverse workload guard. Nothing is restored until separate approval
and native worker completion. Fifteen assignment/PMS-agent checks passed in
`.local/business-suite-qa-64c3538b44344d39b3ef09f25dfa67b9/results.xml`.
`Undo the last PMS change` also prepares recovery for the current user's most
recent completed **AI task execution in the selected project**, using the recorded
approval completion time. It does not mean the latest manual edit or another
user's execution. If no project is selected, the bot asks and accepts a project-ID
reply in the same fresh conversation. The selected source is frozen in the new
draft and still needs separate approval. Unsupported latest executions are not
silently skipped in favor of older ones.

Eighteen recovery/PMS-agent checks passed in
`.local/business-suite-qa-4447c9c714944abf9a6fd1d2b3d18b32/results.xml`, including
explicit ID, latest source, missing-project follow-up, manual-change rejection and
revoked-access paths. Continuation from stale historical conversations and live
undo are not established by this coverage.

Two additional native ordering/scope checks passed in
`.local/business-suite-qa-a72f6b8ad4fe427690440543bf0ab893/results.xml`: a lower-ID
execution completed after a higher-ID one and was correctly selected, while
later executions by another actor and in another project were excluded. A project
with no completed AI execution answers without an approval/action and retains
the selected project after clarification.

A later security-focused gate passed forty-three tests in
`.local/business-suite-qa-0be07dc4238e4f87bff5470d8a3d27ad/results.xml`, covering
revoked current access, exact execution/approval/evidence linkage, foreign actors,
tampering, workflow identity boundaries and emergency-stop controls alongside
Workbench and workload-guard regressions. Revocation denies recovery without
changing assignments. Historical provenance never authorizes execution itself.

The server-local bot accepts `Rebalance workload` in PMS and asks for missing
tasks, recipients and the starting Monday. The selected project and tasks can
come from the current app context. Follow-up values remain in the existing
private server conversation history.

When the bot asks a specific question, a plain reply can fill that field: a
project number, task title/key, collaborator name or Monday ISO date. For example,
`Rebalance workload` → `project 92` → `Prepare release` → `Ravi` → `2026-11-16`.
These example values are illustrative. The server stores the pending question
explicitly and retains earlier selections; a plain value does not authorize writes.
The date question also accepts `this week` and `next week`, mapped to Monday in
the request timezone. Follow-ups inherit that timezone unless explicitly supplied.
An invalid initial date retains the date question, allowing a plain corrected
Monday date instead of requiring the entire request again.

Recipients can be named: `Rebalance workload with Ravi`, followed by any missing
inputs. `candidates=Ravi Sharma,Anu` also works. The server searches only native
eligible collaborators in the authorized project. Exact display names take
precedence; a first-name prefix must identify exactly one eligible person.
Ambiguous names prompt for selection instead of guessing. Names are resolved
again on follow-ups. Projects with over 200 collaborator candidates require IDs.

Tasks can use exact titles or task keys: `tasks=Prepare release,QA-104`. Duplicate
matches require a record-ID or unique-key follow-up. Resolution excludes deleted
tasks and other projects. Names are rechecked on follow-up, and projects with more
than 200 tasks require record IDs. Numeric values are treated as record IDs.
Selecting previously missing tasks is allowed only in an unfinished server
rebalance clarification with no prior task selection, execution steps or approval.
Each project and task selection is frozen in the normal request context as soon
as it is resolved, even if recipients or the starting week still need clarification.
Later follow-ups cannot switch those established task targets.

An explicit request can use:

```
Rebalance workload: project=92; tasks=101,102; candidates=12,13; start=2026-11-16; weeks=2; scope=workspace
```

These are example IDs, not actual deployment records. The project must belong to
the current conversation workspace. Candidate recipients must pass native active
collaborator validation. Requests cannot move tasks from another project.

Recommendations keep co-assignees, dates and dependencies, require recipient
headroom in every affected week, and subtract earlier proposed moves from later
headroom. They use the canonical authorized native workload source. The algorithm
is greedy and moves whole task shares; it does not establish skills or optimality.
Hours-mode capacity comes from the native personal working schedule, dated weekly
overrides, holidays and approved leave; it is not a sprint budget. The native
heatmap's final hours-mode calculation replaces its intermediate sprint share.
An integration case with a two-hour sprint budget verifies that both the proposal
and actual post-assignment snapshot show the recipient's 40-hour personal capacity
and 30 planned hours, while preserving the task's sprint.

A nonempty recommendation becomes the existing `pms.task_plan` action. Nothing is
assigned during recommendation or preview. Approval delegates to the native
atomic PMS worker; the parent waits for its confirmed receipts. The full workload
guard is checked at preview, approval, execution and resume. This is an optimistic
freshness check, not a reservation. A request with no suitable move reports that
outcome without an action.

The planner catalog also exposes `pms.rebalance_workload` as a read-only GET tool
at `/suite/pms/workload/{project_id}/rebalance`, with explicit task IDs, candidate
IDs, Monday start, week count and project/workspace scope. It is independently
registered in the security catalog. Its typed source retains the exact plan and
workload guard for a separately reviewed `pms.task_plan`; reading it never assigns
tasks. Native management authorization and eligible collaborator checks still apply.
AI discovery requires the same PMS management permissions as `pms.task_plan`:
`pms_manage_tasks`, `pms_manage_projects` or `pms_admin`. Ordinary viewers retain
workload reading without being offered assignment recommendations they cannot
apply through the AI task executor. Both the tool and independent security catalog
declare this requirement. Two ordinary-role checks passed in
`.local/business-suite-qa-14c1148239de4566bc994720f2eae2ca/results.xml`.
When an action uses a recommendation read in its planning context, the server
requires a matching full workload guard on `pms.task_plan` for that project.
The provider cannot silently remove the precondition and obtain an approval.
Every relevant task-plan step is checked, including later steps in a larger plan.
For the recommendation project, playbook and undo shortcuts must first be
expanded into an explicit guarded task plan, because they can contain assignment
changes. This check does not claim that several precomputed guards reserve shared
capacity; a prior change can still require a fresh read and review for later work.
Parent approval revalidates guarded task children before queuing. A second check
before dispatch catches known staleness before the operation is marked in flight,
so the parent pauses instead of reporting an uncertain write outcome. The native
approval/execution checks remain in place for changes after dispatch. Already
queued or completed native children keep their existing idempotent recovery path.
The retry-safe parent resume path also checks pending child workload before
requeuing. Stale work stays paused immediately. If the exact reviewed workload is
restored, resume can proceed through normal native execution and receipts; this
does not reserve capacity or bypass any later checks.

After this resume change, fifteen focused timing/PMS-agent tests passed in
`.local/business-suite-qa-4190f3eec30d4bffb0e3f244d92f0fb4/results.xml`. They include
stale resume rejection and successful recovery after exact source restoration.
This gate overlaps the earlier forty-four-test gate below.
The focused mocked-Gemini context test passed in
`.local/business-suite-qa-4a8a7388b2214e01ac0e06957cb1f534/results.xml`.
It verifies catalog discovery, preserved source guard and unchanged assignments;
it is not a live Gemini quality benchmark.

The existing BotWorkspace now displays a dedicated review card with current and
proposed assignee IDs, weekly source and recipient loads, snapshot recipient
capacity and limitations. This comes from the server recommendation. A source
hash or assignment mismatch, or additional task edits, hides the projection.
It is a draft estimate; confirmed execution still comes from receipts.
Provider-prepared single-action recommendations use the same card. The server
attaches review data only when normalized proposed task steps equal its authorized
recommendation; it does not accept model-generated projection numbers. A different
plan retains native action review without borrowing these workload projections.

The current recommendation/guard/PMS-agent gate passed forty-four tests in
`.local/business-suite-qa-549c0a7f9ed543d9b5c1c619ee6cb5e6/results.xml`, including
server review data, separate project/task collection and blocked target-switch
assertions. The frontend rendering check
`node scripts/test-workload-rebalance-review.cjs` and `npx tsc --noEmit` passed.
Four Playwright checks passed with the existing Vite5186 server using the
development-only BotWorkspace fixture and production bot stylesheet. Desktop
(1280px) and mobile (390px) screenshots were inspected; the review fits without
horizontal overflow, renders the approval requirement and planning limits,
performs no mutation requests and hides stale projections. Screenshots are
`.local/rebalance-review-1280.png` and `.local/rebalance-review-390.png`.
This fixture coverage does not establish authenticated live backend execution.

Authenticated native guard preview/rejection was separately verified on an owned
temporary API1645. A synthetic task priority proposal retained the full guard;
changing only that task's estimate caused approval HTTP409. Priority and assignee
stayed unchanged. Native run22 was cancelled and synthetic task2466 soft-deleted;
an independent database check confirmed cleanup and zero model API log entries.
The temporary API was stopped and shared services were not restarted. Evidence:
`.local/workload-guard-live-preview.json`. This proves the native guard boundary,
not live reassignment, provider quality or authenticated full-bot execution.

Source verification: seventeen recommendation/conversation and workload-guard
tests passed in `.local/business-suite-qa-fd8bc89b8caf41faa46bea81b4389bc6/results.xml`.
The positive conversation test covers approval, native worker execution and
parent completion. An overlapping combined guard/follow-up gate passed twelve
tests in `.local/business-suite-qa-ee3115028df9428e93826a9282d1fb7b/results.xml`.
No live API restart, cloud call or model retraining was part of this milestone.

Remaining work includes broader natural
phrasing and authenticated live
acceptance. This does not establish full ClickUp parity.
