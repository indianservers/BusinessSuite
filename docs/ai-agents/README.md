# Business Suite AI Architecture

## Current conversational action workspace

The floating `ActionBot` and expanded workspace use `/api/v1/ai-operator/suite/*`.
The server implementation is in `backend/app/ai_operator`; the older
`backend/app/ai_agents` foundation below remains a separate compatibility layer.
Changes to the current bot should reuse the suite's conversation, permission,
tool, approval and execution services rather than introduce a third action path.

- `suite.py` owns command planning, source reads, action reviews, execution and
  receipts. Native tools call existing module APIs and keep their permissions.
- `suite_conversations.py`, the memory services, saved agents, skills, schedules
  and orchestration services persist their state on the server.
- `providers.py` contains server-side Gemini and OpenAI adapters. The effective
  provider and model come from scoped, enabled configuration; an implemented
  adapter alone does not prove that its key is configured or its connection works.
- `local_tensorflow.py` and `dialogue_tensorflow.py` load signed local releases
  for intent recognition and dialogue acts. Typed dialogue and workflow code
  resolve fields and prepare actions. This local classifier is not a generative
  conversational LLM. Training, weights and activation pointers stay on the
  server; the browser does not train or store the model.
- `routing.py` offers opt-in selection using reviewed quality, measured latency
  and configured pricing. Suite `auto` commands derive a versioned request shape
  with `routing_tasks.py`: modules, answer/action planning, complexity, requested
  capabilities and response schema. Selection requires at least three comparable
  reviewed outcomes, not unrelated successes. The current enabled model and
  sharing permissions are still checked. Only the final output provider receives
  review credit when multiple providers participated. The UI explains the match
  under “Why this model?”. Shape matching and owner reviews are not independent
  capability certification. `provider_fallback.py` adds an explicit per-request
  alternative through `fallback_provider` in suite commands. The floating bot and
  advanced operator expose this choice; it defaults to none.

Fallback planning uses only a distinct, currently enabled, scoped cloud provider
with data sharing allowed. It rechecks that configuration immediately before a
switch and rejects a changed model. Timeouts, rate limits, open circuits and
selected transient server errors can switch once. Authentication failures,
invalid model output and ambiguous connection/key errors do not switch. The
attempts share the organization's planning deadline (at most 45 seconds), reserve
time for the alternative and disable nested retries. Attempt metadata is stored
in `result.provider_routing`; provider token/cost logs retain their usual path.
Follow-ups retain the pending choice; a local planning retry drops cloud fallback.
Inline edits remain server-local and require a fresh review.

### Scoped planning and output contracts

`planning_catalog.py` filters discovery by the selected module, current native
permissions, employee identity requirements and saved-agent tool selection.
`/suite/tools` accepts optional `module` and `workspace_id` filters. Automatic
reference reads and provider prompts use the same permitted capability set.
Provider action proposals and additional source requests must stay inside the
offered catalog. Discovery is not execution consent: approval and workers recheck
the original session, current permissions, exact plan hash and native records.

`suite_tools.payload_schema` exposes only adapter fields. Native URLs, methods,
credentials and tenant selectors remain server-owned. `structured_output.py`
closes fully typed schemas for strict OpenAI/Claude output. Optional values have
explicit wire nullability; decoding restores omitted defaults without discarding
unknown arguments. Open-map plans and Gemini retain validated JSON mode because
their schemas cannot reliably use that strict transport. All provider outputs
still pass Pydantic, adapter and canonical business validation. Prompt provenance
records the actual output-contract mode.

`identity_resolution.py` resolves exact names, emails and account IDs only from
fresh authorized native results. Duplicate names or incomplete lookup results
need clarification. Local PMS and CRM task creation retain the resolved assignee
through draft edits; canonical creation validates eligibility again.

Run `venv/Scripts/python.exe -m pytest tests/test_planner_architecture.py -q` from
`backend` for complete PMS, CRM and HRMS planning/approval/persistence/receipt
workflows, unknown-field rejection, revoked access and duplicate-write checks.
Provider HTTP responses are simulated; the application APIs, permissions and
business persistence use an isolated test database. No cloud credentials or live
customer writes are required.

Model output does not grant tool access or approve a business change. Current
access, exact action review and canonical execution receipts remain required.
Message-triggered actions retain their source citation and conversation binding.
PMS project-name replies use a bounded native lookup when the agent has selected
`pms.projects`; duplicate names require a choice that is checked again before
selection. Explicit project IDs still go through native access checks.

Use the effective runtime configuration and model-release status to answer
which model is active. Do not hard-code an environment's model or release number
in the frontend or infer successful connectivity from a saved API key.

## Core instruction versions

`prompt_registry.py` keeps immutable server-owned core instruction revisions.
The initial revisions preserve the previous provider instruction text exactly.
Each attempt fingerprints the template, response schema and exact rendered core
instructions. `prompt_provenance.py` records these fingerprints through existing
API logs/audit associations and private suite run results; it stores no prompt
content, business context or credentials. Activity shows the recorded version of
each attempt, and administrative usage logs attach the same provenance.
`GET /api/v1/ai-operator/prompt-versions` lists safe catalog metadata under the
existing AI administration and workspace-management checks.

Core revisions are published through server releases; clients cannot override
the core version. Older revisions remain available in the registry for server
rollback and comparison. Agent and skill instructions retain their existing
reviewed revision workflows. Task-aware measured routing only credits successful
final-provider outputs whose fingerprints match the current core instructions
and response schema. Unversioned historical reviews remain inspectable in global
statistics but do not qualify a new task-aware routing decision.

Complete outbound JSON requests also receive `request_fingerprint` metadata
immediately before the transport attempt. `request_fingerprints.py` covers the
provider endpoint, model, purpose, full instruction/context payload and generation
settings using versioned canonical JSON. Authentication headers are excluded.
The audit retains only a server-keyed HMAC and opaque key epoch, with user,
tenant and scope included in its identity. This prevents cross-user equality
matching and offline guessing from an unkeyed business-content hash. Changing
context or generation settings changes the fingerprint even when the core
instruction revision is unchanged. Failed transport attempts retain the same
provenance; policy- or deadline-blocked attempts do not claim a request fingerprint.

Activity and authorized analytics expose this metadata alongside core versions.
Legacy attempts remain readable and explicitly show that a complete request
fingerprint was not recorded. Comparisons require the same user, tenant, scope
and key epoch; signing-key rotation intentionally starts a different epoch.
Canonical payload identity does not reproduce historical source content or HTTP
wire bytes. No raw prompt, headers, credentials or business-context snapshot is
added to provenance storage. Measured routing continues to compare core policy
and output schema versions, rather than requiring identical business requests.

## Signed native-record webhook triggers

Agent events reuse the existing signed receiver at
`POST /api/v1/access/services/webhooks/{endpoint_id}/receive`. Administrators
configure its existing managed service identity, record contract, event names
and encrypted signing secret through webhook governance. The agent picker lists
only approved active record endpoints for its module (CRM, PMS, HRMS, SRM or FAM).
Both the endpoint and an admitted event name must be selected before preview.
The exact review includes the record type and managed receiver identity; activation
is a separate step. Conversational agent design accepts, for example,
`When CRM webhook #42 receives event "record.changed"`, and saves an inactive
review using the existing builder workflow.

The existing timestamped HMAC, replay, rate and payload limits remain enforced.
A server-owned admission receipt binds the native event, tenant, record, receiver
identity, endpoint configuration and payload digest. A generic service event
cannot impersonate an admitted webhook by copying its request-key prefix.
External JSON remains untrusted signal data and is not forwarded to the model.
The agent re-reads the current ERP record through the native authorized API.
Endpoint changes, revocation and source tampering invalidate subsequent work.
PMS sources must also match the reviewed workspace and project. Existing event
budgets, pause/resume floors, private occurrence conversations and reviewed
business actions remain in force. This is a native-record signal integration;
it does not interpret arbitrary external payloads as business facts or consent.

## Connection account identity and action readiness

The Connections workspace reuses the native Power Apps vault and its existing
owner, organization and environment checks. It lists provider-confirmed identity
separately from connection health, granted scopes, authorization expiry and action
readiness. Environment choices follow the native `development`, `testing` and
`production` keys. Refreshing these cards reads metadata only; it does not run a
provider check or approve an external action. Delayed responses from a previous
environment cannot replace the current environment's cards.

Successful native `test` operations can record a small account allowlist through
existing connection audit storage: Gmail, Outlook, GitHub, Slack, Dropbox, Box and
Jira verification results. Resource checks, such as spreadsheet metadata, do not
become account identities. Unknown providers explicitly report no account identity.
No extra provider request, credential decryption or new table is introduced for
this display. The proof binds the existing connection revision/configuration and
credential version. Rotation, revocation or changed settings invalidate the display
until verified again. A response from an operation whose authorization changed
in flight cannot mark the replacement configuration healthy. Operations configured
not to retain output do not persist an account identity through this feature.

Action readiness reuses the native effective-scope rules and the agent bridge's
existing action restrictions. Cards distinguish missing scopes, disabled writes,
expired/unavailable authorization, native-workflow-only actions and actions ready
for separate review. Readiness remains a snapshot: selected-agent bindings,
current permissions, action inputs, rate limits and exact approval are checked at
execution. This view never invokes the listed actions.

The activity permission governs recent-error history and successful-operation
metadata. History uses bounded, owner/tenant/environment-scoped window queries,
showing at most five sanitized errors per connection and excluding raw provider
error bodies. A successful data read is labelled as such; full synchronization
completion remains in native workflow history. Connection metadata responses are
`no-store` and do not expose vault fields or arbitrary provider response bodies.

## Reviewed HR support-ticket actions

Suite tools now include `hrms.ticket`, `hrms.people`, `hrms.status_ticket`, `hrms.assign_ticket`, `hrms.escalate_ticket` and `hrms.reply_ticket`. They reuse the native helpdesk table, shared account directory, routes, replies, permissions and version field. The HR Assistant template selects these tools for newly reviewed agents; existing saved agents retain their original tool grants. Account-name/email lookup returns account IDs and minimized names, not employee IDs or personal contact fields. The shared directory uses the authenticated selected company rather than silently reverting to the account's primary company.

Local conversation examples:

- `HRMS: update ticket`, then `ticket #12`, then `status: Pending`.
- `Resolve ticket #12`, `Close ticket #12`, or `Reopen ticket #12`.
- `Assign ticket #12`, then `user id: 4`. Native assignment also sets status to In Progress.
- `Escalate ticket #12`, then `reason: First-response deadline missed`. An optional `escalate to user id: 4` selects a current active company member; escalation sets priority to Critical.
- `Reply to ticket #12`, then `message: Your exact requester-visible text`.
- `Add internal note to ticket #12`, then `message: Your exact staff-only note`.
- Supply corrected labelled fields before approval, or say `cancel`. An acknowledgement is not a ticket selection, reply body or approval. Reply text remains literal even if it contains strings such as `status: Pending`.

The workspace uses the same current/proposed-values component as employee actions. Every mutation requires normal Suite approval and native execution confirmation. Version numbers are mandatory in bot action payloads. A reviewed sequence may assign, reply, escalate and resolve the same ticket using successive versions; later steps rely on native row locking/version checks rather than incorrectly comparing the initial snapshot after an earlier approved change. Concurrent changes reject execution. Lost receipts retain the existing reconciliation policy and are not automatically repeated.

Native helpdesk list, detail, reply, SLA and analytics access share company and ticket ownership/assignment rules. Staff management permission enables the authorized company helpdesk view; ordinary requesters cannot read unrelated tickets or internal notes. Enterprise-control diagnostic tickets stored in the same table remain outside HR helpdesk views. Assignees must be active company members. Existing legacy tickets with an authorized employee relationship remain readable. Native query routes remain available; JSON adapters reuse the same controllers.

Cloud planners also receive the typed tools. With an HRMS request and no explicitly selected context, an explicit supported ticket command reads the exact ticket ID, avoiding dependence on its position in a list sample. Agent read-tool bindings and native source permissions still apply. The model-facing ticket projection excludes attachment URLs, private enterprise diagnostics and unreviewed suggested replies.

The versioned server helpdesk planning policy tells cloud planners to retain a proposed workflow outline when identifiers are missing, ask for a ticket link/record ID and ambiguous person identity, and fetch concurrency versions through authorized reads. Users are not asked to supply backend version counters; normal action review hides those counters while retaining them in the signed action payload.

Suite routes and private Suite/chat state use AI grants rather than requiring PMS record access. Native HRMS read/write grants and helpdesk management permissions remain separate and mandatory; ordinary requesters need a centrally authorized write grant for bot-mediated public replies. Internal notes still require staff management permission. Legacy PMS operator routes and records keep their PMS classification. AI feature switches and quota definitions are consumed as company-scoped control metadata, so an own-record scope cannot hide the kill switch or company usage cap. Quota aggregates remain company-bounded; raw usage records are not exposed. Ordinary reads do not create security configuration, and pending control changes preserve the prior ORM autoflush behavior. Configuration updates retain their administrator endpoints and permission checks.

These are server-side typed conversation extensions around the existing local runtime, not new TensorFlow weights. Private ticket conversations, replies and source content are not automatically added to training datasets. Automatic event replies, universal undo, external customer-support connectors and complete ClickUp parity are separate capabilities and are not implied by this milestone.

## Reviewed employee profile actions

`hrms.employee` reads a selected authorized employee profile through the native employee endpoint. Its model-facing projection excludes personal contacts, identity documents, bank details, medical information and login roles. `hrms.update_employee` prepares reviewed contact, directory and organizational changes through the existing native employee update endpoint. It requires employee update permission plus read access for the exact preview. Sensitive contact changes retain the native sensitive-field permission check; the bot cannot grant that permission or bypass duplicates.

Local conversation examples:

- `HRMS: update employee`, then `employee #12`, then `office extension: 204, work location: Hyderabad`.
- `Edit employee #12 desk: clear, timezone: Asia/Kolkata`.
- `Update employee #12 department id: 3, designation id: 4` (native branch/department relationships must be valid).
- Reply with another labelled field to revise an unapproved local proposal. Other existing fields are retained; `yes` never supplies a missing employee selection or approves execution. Say `cancel` to discard.

Employee codes and names are not silently interpreted as numeric employee record IDs. Organizational relationships use explicit IDs and native validation; invalid departments, designations or managers cannot be written. Account roles, login linking, status changes, payroll, banking and identity fields are excluded from this profile tool and remain separate authorized native workflows.

The workspace shows current/proposed fields before approval. Existing Suite snapshots detect changes since preview. Immediately before dispatch the worker also passes the native profile version in `If-Match`; the native employee router locks and checks that version, covering changes between the final read and write. Lost responses retain the existing reconciliation policy and never automatically repeat a profile write. Receipts and result cards link to the employee profile only after native success.

The HR Assistant template selects these tools for new reviewed agents. Existing saved agents retain their original tool grants. Everything persists on the server; this typed local extension does not retrain or replace the TensorFlow model and does not automatically contribute private employee data to training.

## Reviewed CRM lead actions

The Suite tools catalog includes `crm.create_lead`, `crm.update_lead`, `crm.qualify_lead`, `crm.convert_lead` and the authorized `crm.lead_qualification` read. They reuse existing CRM CRUD, lead workbench and conversion APIs. No parallel lead table or direct model-generated database writes are used. The CRM Sales Assistant and Lead Qualification Agent templates select the appropriate new tools; existing saved agents retain their reviewed tool bindings.

Local examples (also available as typed tools to enabled cloud planners):

- `CRM: create a lead`, then `name: "Asha Rao", email: asha@example.com, company: Example Ltd`.
- `Update lead #12 job title: Sales Manager`.
- `Qualify lead #12`, then `need: CRM deployment, budget: 10000 INR, decision maker: Owner, timeline: Next month`.
- When facts are already recorded, answer the qualification question with `use only existing facts`. Native required-field and stage-transition rules still apply.
- `Convert lead #12 to customer`, then `contact and customer`, `contact customer and deal`, or `contact only`. Creation choices are shown in the exact action payload and do not approve execution.
- Reply with corrected labelled fields while collecting details or reviewing a local lead draft, or say `cancel`. An acknowledgement such as `yes` is not a name, field value or approval.

Every mutation requires fresh normal action review, canonical permission checks and execution receipts. Existing record snapshots prevent overwriting changes made after preview; workflow references support reviewed creation → qualification → conversion dependencies. Native qualification, duplicates, assignments, custom required fields and linked-record access remain authoritative. A rejected native action is not reported as completed. Computed lead ratings and scoring overrides are deliberately absent from the general field-update schema.

The local lead extension is explicit typed grammar and persistent slot filling around the existing local runtime. It is not a new TensorFlow training release or a generative local LLM. Arbitrary prose and complex cross-module planning use an enabled provider; new multi-intent training and paired ClickUp execution benchmarks remain separate work. Private lead facts are not automatically added to training datasets.

## Conversational action recovery

In the original persistent conversation, commands such as `Undo the last change`,
`Please undo that action` or `undo run #123` resolve a confirmed execution on the
server. The default lookup survives the recent-message window. Exact run IDs
must still belong to the same private conversation, workspace and agent selection.
The server prepares a fresh reviewed plan; selecting a model does not delegate
recovery decisions to that provider or send historical values to a cloud model.

New CRM task updates retain the changed fields' native before-values and a digest
of the confirmed task columns. Their inverse uses the existing `crm.update_task`
API, including explicit null for restorable unset fields. Current task fields
must still match the source execution before preparation. The normal preview
snapshot also protects execution against edits made after preview. CRM recovery
cards show the current and restoration values before approval. Legacy CRM
updates without complete before-evidence require manual recovery.

Completed PMS task plans delegate to the existing workbench undo preview, with
its current project access, original execution evidence and supported-inverse
checks. Supported CRM/PMS workflow steps are proposed in reverse order. Native
PMS limitations remain visible before approval; restoring fields does not recall
messages or reverse unrelated external side effects. Created records, HR workflow
approvals and tools without a supported inverse are disclosed for native manual
recovery. A source workflow containing an unsupported top-level action produces
no automatic reversal plan. Incomplete/uncertain executions require their existing
checkpoint or reconciliation controls first.

The original source is linked to one recovery preview. Exact retries reuse the
existing run; active or executed recovery previews cannot be duplicated. An
unexecuted cancelled preview can be prepared again. `cancel recovery` uses the
existing cancellation endpoint. Restoration values are fixed for that preview;
inline revision and unrelated pending follow-ups cannot silently change its
meaning. Different changes require cancellation and a new explicit action.
Current private-history access, source agent/event bindings, native tool checks,
exact approval, worker checkpoints and execution receipts remain in force.
Before-values stay in existing server-side run storage; this feature does not
add tables or authorize training on private business data.

## Original AI Agents foundation

The original AI Agents module is a backend AI assistant layer across CRM, HRMS, and PMS.

It stores agent configuration, conversations, messages, approvals, audit logs, company-level settings, uses safe adapters/tools for product data, and calls OpenAI from the backend only.

### Foundation backend structure

- `app.ai_agents.api` exposes `/api/v1/ai-agents/*`.
- `AiAgentRegistryService` seeds and lists the initial 16 AI agent configuration records.
- `AiConversationService` provides basic conversation/message persistence helpers.
- `AiApprovalService` stores and updates AI approval records. Approving currently marks a proposal as approved only.
- `AiAuditService` records AI foundation actions.
- `AiAgentSettingsService` stores company-scoped agent settings.
- `CrmAiAdapter`, `HrmsAiAdapter`, `PmsAiAdapter`, and `CrossModuleAiAdapter` read from existing product modules without creating duplicate product APIs.
- `AiToolRegistryService` registers safe tool metadata.
- `AiToolExecutionService` validates tool calls, checks agent/tool permissions, routes to adapters, and creates AI approvals for risky tools.
- `OpenAiService` wraps the official OpenAI SDK and normalizes responses/tool calls.
- `AiAgentOrchestratorService` runs the chat loop, saves messages, calls OpenAI, executes safe tools, records approvals, and saves final assistant responses.

### Foundation database tables

- `ai_agents`
- `ai_agent_tools`
- `ai_conversations`
- `ai_messages`
- `ai_action_approvals`
- `ai_audit_logs`
- `ai_agent_settings`

The `ai_agent_tools` table stores active tool availability per agent. Tool metadata is seeded from the safe registry.

### Foundation seeding

The backend seeds the 16 initial agent configuration records on application startup through `AiAgentRegistryService.ensure_seed_data()`.

These records are AI configuration only. They are not CRM, HRMS, or PMS sample data.

### Foundation security notes

- All endpoints use the existing authentication dependency.
- No OpenAI API key is exposed to the frontend.
- No frontend AI Agents code is included in this foundation step.
- Conversations are scoped to the creating user.
- Pending approvals are scoped to the current user unless the user is a superuser.
- Company settings use the current user's organization/company context when available.
- The temporary AI access check should be mapped to the full RBAC permission system in a later step.

### Historical foundation follow-ups

These describe that foundation only; they are not a status report for the current
ActionBot workspace. Current suite authorization uses its own RBAC and native
module checks.

1. Map `cross_get_alerts` to an existing alert aggregation service when one is available.
2. Add frontend pages and Ask AI buttons after the backend integration is stable.
3. Add streaming after non-streaming chat is verified in production-like environments.


## Cross-module model consumption

The floating bot and Suite workspace read model availability from `GET /api/v1/ai-operator/suite/providers`, using AI grants and the current authenticated company or authorized workspace. Provider configuration is consumed as server-only control metadata through exact authorized scope keys, rather than being hidden by PMS business-record ownership rules. The public catalog exposes the existing sanitized provider projection only; credentials remain encrypted at rest and are decrypted only by server adapters. Disabled configurations and blocked data sharing remain unavailable, and explicit disabled workspace overrides still block inheritance.

Native provider editing and connectivity-test endpoints retain their administrator checks. Workspace inheritance still requires native workspace membership and explicit sponsorship; unrelated companies and ambiguous sponsorship do not inherit configurations. Usage logs and query-capture records are cross-module AI state with actor/company/branch controls; query capture remains pending review, without automatically making examples eligible for training. Legacy business tools retain their module grants.


## Owner inspection and cancellation during operational stops

Suite run history, private conversation inspection and cancellation retain current authentication, AI access, company/branch scope, workspace membership, ownership and signed permission checks. They do not consume model quota or require emergency switches to remain enabled. New commands, approval, retry and resume keep their normal execution gates.

New contexts include a separate signed control fingerprint. It covers the same actor, grants, native permissions, entitlements, ACL epoch, agent permissions/settings and policy version, while excluding emergency-stop switch values. The execution fingerprint remains unchanged. A control proof is rejected for execution, payload confirmation or action approval. Both fingerprints are derived from one authorization-state read when sealing a context.

Old signed contexts are not re-signed automatically. An unchanged legacy fingerprint remains valid; a legacy fingerprint matching the current all-enabled control baseline also proves the same non-switch authorization state. Older non-default switch configurations that cannot be proved this way fail closed after a switch change. No historical permissions or switch values are guessed. SQL conversation isolation selects the same proof only for explicit internal owner-control queries; normal retrieval keeps the execution fingerprint.


## Central AI provider administration

Authorized AI administrators can open `/ai-agents/providers/gemini` (or `openai`/`claude`) and manage shared company/personal model configuration without a PMS business-record grant. The Suite PUT and connection-test routes reuse the native provider handlers, table, encryption, rate limits, audit entries and adapters. Both the central AI configure action and the native settings-management permission are required. The public catalog remains sanitized; missing replacement keys preserve saved credentials.

AI administration treats provider rows as exact current company/personal or natively authorized workspace configuration. The original PMS API routes retain their original classification. Workspace overrides still require native workspace management authorization. Company administrators can inspect and repair configurations during operational stops; ordinary consumers remain blocked by execution stops. Denied optional PMS analytics no longer prevent the configuration form from loading, and the page does not substitute fabricated usage totals.


## Shared provider usage monitoring

`GET /api/v1/ai-operator/suite/analytics` exposes administrator telemetry using the existing API log table and a shared report service. It requires AI configure plus native settings-management permission, current company/personal or managed workspace scope, and existing record/branch boundaries. An own-scope administrator sees permitted own-user events; an organization-scoped administrator can aggregate permitted users. The response labels the applied scope. Operational stops do not hide administrator monitoring.

The central provider form and Suite activity page use this AI endpoint instead of PMS analytics. Groups cover the selected period (1–365 days); recent request detail remains bounded to 200 rows. Tokens, latency, known cost sums and priced-request counts retain the existing telemetry semantics. Unknown cost remains null, and partial cost sums cover only priced requests. Rates are administrator-supplied estimates, not provider invoices. Private prompts, responses and credentials are excluded; existing sanitized prompt provenance remains available.

Server-plan counts come from Suite runs with an actual summary and server intelligence, rather than a PMS-only event count. Cloud plans and unprepared/invalid runs do not count as server plans. Counts include reviewed previews even when later cancelled. Legacy PMS analytics reuses the same reporting service with its existing legacy event-count behavior.


## Shared definitions under central module roles

Installing an organization-library agent with bundled skills creates recipient-owned private definitions and version history. Skill-version messages inherit scope through their existing conversation foreign key; no separate history table is introduced. Central own-record AI permissions can therefore install and read authorized versions without receiving unrelated PMS record access. Publisher-private memory and history remain excluded, and installs retain ordinary native tool checks.

Organization administrator membership no longer overrides an explicit central or branch AI configure denial. Managed publishers require both current organization administration and the AI configure action; the same eligibility drives `can_publish` and `can_manage`. An audience member may still install an active approved definition without gaining publishing or revocation rights. Unmanaged legacy organization administrators retain their existing publishing authority, and platform-owner privileges remain unchanged.


## Library controls during execution stops

Current organization-library administrators can inspect the shared catalog and publication history, revoke a definition, and discard an exact pending publication preview during an emergency stop or exhausted execution quota. These are explicit server-side control paths, retaining company/workspace authorization, current administrator/configure checks, signature verification and optimistic revision/preview-hash validation. They do not activate tools or run an agent.

Publication preview, publish and private installation retain normal execution-stop gates. Managed library publishing controls are classified as AI configuration, so a view/configure administrator can revoke an existing definition without being granted unrelated record-creation or PMS access. Revocation uses the same existing signed publication state and runtime-origin checks; linked installs remain blocked after execution is re-enabled. Live stop settings and real publications are not changed by the verification smoke.


## Reviewed milestone management

PMS now exposes a canonical milestone read/edit service using the existing milestone table, schema and native project access. Suite tools add project milestone lookup, exact milestone reads and reviewed updates to names, descriptions, dates, eligible owners, status and progress. The Project Coordinator template revision 3 includes these tools; existing saved agents keep their original tool bindings until separately reviewed.

Local examples include `PMS: update milestone`, `Move milestone #42 to tomorrow`, `Rename milestone #42 to "Client sign-off"`, `Mark milestone #42 as complete` and `Assign milestone #42 to user #12`. Follow-ups collect missing record IDs/fields, retain corrections and support cancellation. Local named owner/milestone lookup still requires a record/account selection; connected planners can use authorized project/milestone/directory tools. This is typed server action parsing around the existing local release, not new TensorFlow weights.

Exact native revisions are fetched by the server rather than requested from users. Native row locks and revision checks prevent stale edits, including after an earlier review. Date ordering, completion/progress consistency, eligible active owners, selected workspace/project scope and client-approval lifecycle boundaries are enforced. Pending or approved client milestones require their separate native workflow; the edit tool never grants client approval. Multiple changes to one milestone must be combined into one reviewed action. Existing separate records can still participate in dependent Suite workflows.

Expanded review shows the actual milestone name/project and current/proposed values; completion and reopening include their derived progress changes. Concurrency metadata stays out of ordinary review fields. Successful receipts identify the actual milestone and parent project, with a link to the project's milestone page. Source citations also use that parent project. Native milestone listing is explicitly bounded and paginated.


Milestone responsibility changes do not grant record access: visibility remains governed by the required project parent. They therefore preserve otherwise-current action receipts instead of invalidating every private AI context in the company. Actual project-parent changes remain access-invalidation events. Explicit progress supplied in conversation is retained; native completion/reopening normalization supplies defaults only where needed.


## Compound milestone drafts and contextual corrections

Local milestone edits can combine same-record clauses, such as `Rename milestone #42 to "Client sign-off" and move it to tomorrow`, into one reviewed native update. Both `and` and `then` are routed to this typed handler instead of the creation-only workflow composer. The global permission/consent and destructive-command checks still apply before interpretation.

Within a pending draft, `Rename it to "Final acceptance"` retains the selected milestone and other proposed fields. Corrections can also be collected while the record ID is missing, including labelled fields; the bot continues asking for an exact record rather than guessing one. An explicit different record starts its own selection rather than borrowing the old record's changes. Conflicting field values, different-record compounds and unsupported operations need clarification before any action is prepared.

Clause boundaries and field labels are recognized only outside quoted literals, preserving names such as `Research and create`, `Ship it`, or `Release, due date: 2027-04-01`. This extends server-side action parsing and dialogue state; it does not retrain or deploy new local model weights.


## Verified milestone: conflicting milestone instructions

The server-side milestone grammar now asks for one value when a message repeats a date or owner with conflicting values, or combines a completion/reopening command with a contradictory explicit status. Identical repeated values remain valid. A conflicting labelled follow-up keeps the previous draft intact. Corrected values continue through the existing native revision, permission and approval checks.

All 71 milestone/language/workflow regressions passed, including clarification followed by reviewed execution in an isolated database. A live private conversation verified conflict detection, retention of the corrected date, mandatory record selection, acknowledgement handling and cancellation. No live business action was approved, no milestone was changed and no external model call was made. Existing local model weights were not retrained. Full enterprise-agent functionality and ClickUp parity remain incomplete.


## Verified milestone: CRM and HRMS pending-draft follow-ups

Lead updates and employee profile edits now retain labelled changes supplied before the record ID. Partial restatements such as `Update employee office extension: 205` or `Update lead job title: Director` keep the selected record and other pending fields. Supplying the missing ID in a full command also keeps the collected values. An explicit different record starts a fresh draft, preventing accidental transfer of the old edit. Creation/conversion boundaries, native validation, record permissions, revision checks and separate action approval remain mandatory.

The initial HRMS/conversation gate passed 58 tests and the CRM/workflow gate passed 43. After extending full-command record selection, the final CRM/HRMS gate passed all 80 tests; gates overlap and are not a unique aggregate. End-to-end disposable-database cases verify that no native write occurs before approval and that the final corrected values execute successfully. Live private CRM and HRMS conversations verified early fields, partial corrections, missing-ID handling, acknowledgement handling and cancellation, with zero approved business actions, native business writes or cloud model calls. Existing local model weights were not retrained. Full enterprise Super Agent functionality and ClickUp parity remain incomplete.


## Verified milestone: Office format requests and populated spreadsheet drafts

Local artifact drafting now recognizes Excel workbook/sheet/spreadsheet, worksheet, Word document/DOCX, PDF document/report and PowerPoint presentation requests through one shared creation grammar. Initial recognition and clarification reconstruction use the same format parser. Existing table/document/presentation storage, approval, permissions, revisions and export services are reused; no additional artifact tables or browser model storage were introduced.

Spreadsheet/table/chart creation retains user-supplied CSV rows following the title/column declaration. For example: `Create Excel workbook called Pipeline with columns Lead, Owner: Synthetic lead, Asha`. Multiple rows use newlines; quoted CSV values can contain commas. Row-width mismatches or malformed CSV ask for corrected rows while retaining the original title and columns. Native business commands are not consumed as missing artifact data. Quoted column names remain intact. Supplied formula-like strings stay inert text, including in Excel downloads.

The broader document/presentation/chart/dashboard regression gate passed 91 tests. After final quoted-column and native-command handling changes, 15 focused current-code tests passed; gates overlap. The Excel integration test verifies clarification, separate approval, server persistence and populated XLSX export with formula text kept nonexecutable. Live private drafting verified format recognition and corrected rows, then cancelled and archived without saving an artifact, approving business actions or calling a cloud model. Local model weights were not retrained. Full enterprise-agent functionality and ClickUp parity remain incomplete.
