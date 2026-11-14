# ClickUp live capability parity backlog

Observed read-only on 2026-11-13 in the authorized Indianservers workspace:
https://app.clickup.com/1300420000012861/ai/brain

This is an observed UI inventory, not proof of execution quality or feature parity. No agent configuration, permissions, connections or activation was changed. No credits were consumed by submitting model prompts. Do not mark an item complete from a catalog entry alone.

## Observed capability families

### Live recheck: 2026-11-14

The authorized Indianservers browser workspace is available. Rechecked Create Agent, an existing deactivated agent's configuration, and its Add tools selector. The selector still exposes searchable All/Apps, custom MCP, native task/document/hierarchy/view/form/time/capacity tools, email/calendar operations, public search/fetch, image generation/editing, transcription, code execution and file staging/transfer. No tool was installed, connection granted, agent activated or prompt submitted. The editor still explicitly restricts agent-to-agent orchestration on this account's current plan; execution parity for that feature cannot be established here.

Continue treating this as operation-level acceptance work. Catalog presence is neither a verified authenticated connection nor a completed workflow. Remaining acceptance includes connector account/scopes and revocation, native forms/views/capacity/time breadth, meeting workflows, isolated code execution, all workflow blueprint scenarios, and comparable end-to-end quality/latency/cost measurements. Existing server-side TensorFlow release 324 remains active; this recheck does not train or fine-tune model weights.

- Brain workspace: Ask, Agents, Artifacts, Skills, Workflows (Beta), Scheduled, All/My Agents, Activity, Analytics, AI Settings, Connections, recent chats, usage and credits.
- Agent configuration: instructions and history, skills, activation, sharing/management, model Auto selector and usage.
- Triggers: mentions, direct messages, assigned tasks, shared meeting notes, hourly/daily/weekly/monthly/custom schedules, inbound webhooks and automations.
- Knowledge: workspace access, selected ClickUp content, meeting notes, web search, help center and external connections.
- Orchestration: agents triggering other agents. The inspected account explicitly displays an upgrade restriction; execution was not testable from this editor.
- Memory: recent private work, preferences from human direction, Intelligence Beta automatic memory, and a memory inspection control.
- Tools: searchable All/Apps selector, grouped tools, installed/default status and custom MCP server connection.
- Native work management: tasks/subtasks/properties, priorities, stale tasks, comments/replies/chat, spaces/folders/lists, custom fields, forms, views, duplication/archive/restore/trash, time entries, workload/capacity, project updates, standups and executive summaries.
- Email: search/read/attachments, drafts/create/edit/send, labels/stars/read state, archive and organization; Gmail and Outlook Mail appear.
- Calendar: search/read, calendars, availability, events create/update/delete, and Outlook rooms.
- Other tools: public web search/fetch, create/edit images, code execution, media transcription, assets, file transfer and attachments.
- App catalog includes Gmail, Google Calendar, Outlook Calendar/Mail, Slack, and MCP entries for Airtable, Amplitude, Apollo, Atlassian, Attio, Box, Cal.com, Calendly, Canny, Canva, Clay, ClickHouse, Close, Dropbox, Fathom, Figma, Fireflies, GitHub, Gorgias, Grafana, Granola, Hex, Higgsfield, HubSpot, Intercom, Klaviyo, LaunchDarkly, Lightfield, Linear, Mixpanel, Neon, Notion, Otter, PostHog, Postman, Read AI, Runway, Salesforce, Sentry, Slack, Statsig, Stripe, Supabase, Tableau, tl;dv, Webflow and ZoomInfo.
- Workspace AI administration: AI enablement, custom skills, ambient replies after initial mention, notetaker recording/sharing/retention, model settings, user overrides, role permissions and usage.

## Implementation and verification order

1. Audit native action coverage first. Reviewed CRM lead creation, field updates, qualification facts, conversion and authorized employee profile edits now have canonical adapters and integration coverage (see milestones below). Continue auditing the remaining native operations individually. Reuse existing canonical module endpoints, current permissions and reviewed execution.
2. Verify every observed work-management operation against the actual tool schema and UI. Add missing operations through existing module services. Map ClickUp spaces/folders/lists to supported Business Suite hierarchy explicitly rather than silently substituting unrelated records.
3. Verify connector operations, not just adapter names: authenticated account, granted scopes, read/search, draft, reviewed write, receipt, revocation, expiry and failure recovery. An unconnected catalog entry is not a working integration. Current local development has no verified external account connections.
4. Audit ambient conversations, meeting notes/notetaking, capacity/time tracking, forms/views, image generation, sandboxed code execution and transcription. Treat these as unverified gaps until code and execution evidence exist. Preserve consent, recording retention and execution isolation requirements.
5. Extend agent authoring to expose the verified tools, knowledge, skills, memory, triggers and delegation policies. Reuse server-side persistence and existing workspace components. Activation remains an explicit reviewed operation.
6. Build synthetic paired scenarios for each supported behavior, then run them in both authorized test environments. Include ambiguous names, multi-turn edits, dependency failures, retries, cancellation, duplicate requests, permission changes and recovery. Report task completion, correct target, output quality, latency, cost and unintended actions; do not infer superiority from training accuracy.

## Completion rule

For each individual operation record: observed ClickUp behavior, Business Suite implementation, canonical permission boundary, deterministic/integration test, live test where available, and material limitations. Track statuses as unverified, missing, implemented, integration-tested, or live-verified. Full parity remains incomplete until all agreed operations have evidence. Provider/account availability and ClickUp plan restrictions must be reported separately from implementation gaps.

Local TensorFlow remains a server-side intent/dialogue model, not a generative LLM. Gemini supplies configured cloud reasoning; adding command examples cannot create a missing native action or connector.

## Verified milestone: local image import and reviewed image snapshots

### Follow-up: conversation history and native access boundaries, 2026-11-14

Routine native edits and deletion of an unchanged private, unshared PMS saved view no longer invalidate unrelated AI conversation proofs. A personal filter does not grant task access. Its deletion therefore preserves the owner's current chat/results without re-signing or restoring old proofs. Shared-view deletion and changes to view ownership, company, project or sharing still invalidate cached scope. Bulk view deletion remains conservative.

The audit also closed missing native boundaries: project/workspace reparenting and membership role/user changes now participate in invalidation. Record transfers invalidate both previous and current companies. PMS child rows without a company column resolve their real task/project/workspace parents, with small per-flush metadata reads and caching; background updates no longer assume company 1 when a parent identifies another company. Existing source/parent actor metadata supports the required epoch record outside an HTTP request. Both normal and owner-control fingerprints are cleared after a scope mutation, preventing a second history query in the same request from reusing an old cached proof. Existing HMAC, identity, company, permission, session and source checks remain in place.

The final 117-case disposable PostgreSQL gate passed, including private-view history preservation, shared-view and project deletion, owner/company/project changes, request-bound bulk changes, same-request owner-history isolation, background membership changes in another company, task transfers across companies, saved-view recovery and existing mandatory security regressions. Live synthetic reviewed view creation/deletion preserved the existing conversation and completed result; native chat archival and project archival then succeeded. No cloud call or business message occurred. Local release 324 passed after deployment to API 1534. No model weights were retrained.

This prevents the verified false invalidation for private views. Previously invalidated conversations are not automatically reauthorized or exposed, and actual access changes still hide cached history. A complete source-by-source history recovery experience, the remaining native/connector capabilities and full comparative ClickUp acceptance are still open.

### Follow-up: native private PMS saved task views, 2026-11-14

The bot can create a real native private task-list view through reviewed execution. Example: `Save task view called Delivery focus: priority=High`. If no project is selected it asks for `project=ID`; subsequent labelled corrections retain the name and filters. Supported fields are status, priority, search, assignee ID and an ISO due-date range. The existing workspace review supports inline name edits; a following conversation correction retains that edited name. Completed result cards link to `/pms/tasks/advanced?view=ID`, where the existing native page applies the saved filters and pinned project.

The adapter reuses `PMSSavedFilter`, native project authorization and the canonical saved-view creation service. The native API retains its previous commit behavior; the reviewed adapter can flush and commit its execution checkpoint in the same transaction as the new view. Lost outer receipts resume from that committed record without creating a second view. Changed/deleted views, changed filter/query/sort/column data, wrong workspaces, stale project scope, extra sharing fields and unapproved direct endpoint calls are rejected. Native permissions, saved-agent tool bindings, current identity and approvals remain mandatory. No task, sharing or default-view setting is changed. Shared views, arbitrary view layouts and CRM/HRMS view adapters are not claimed complete.

The broader PostgreSQL gate passed 30 cases, including existing native view and People-directory regressions. The final eight focused cases and an additional audited-resume check passed; these gates overlap. One targeted browser case, TypeScript and the production build passed. Live synthetic creation verified missing-project clarification, inline name revision followed by a priority correction, the native private view/filter values, result link and replay prevention. No cloud call or business message was made. Synthetic view/project/chat cleanup was independently verified.

The first smoke cleanup exposed an existing conservative security behavior: deleting a PMS record advances the company AI ACL epoch and hides chats with older proofs. The exact synthetic chat was archived with guarded local maintenance after the view had already been deleted; the project was soft-deleted through the native API. The smoke cleanup now archives its chat first. No ACL proof was renewed or bypassed to expose history. Persistent-history behavior after native record deletion remains an acceptance gap to address with current source authorization; the full goal is not complete.

### Follow-up: reusable image instructions, 2026-11-14

Image artifacts now offer **Save image instructions as template**. This uses the existing private versioned artifact-template review/storage/history/archival system. An image-instruction definition stores a title, literal prompt placeholders and an explicit aspect ratio; it cannot store binary manifests, image bytes, reference uploads, credentials or model permissions. The user supplies the reusable instructions rather than having private generation prompts copied automatically.

Using the template by name or ID in CRM, PMS or HRMS asks for missing values through persistent follow-ups, accepts labelled corrections, then prepares the existing reviewed image-generation action. The current model/policy are bound by the existing server image adapter. Template revision/archival, agent tool restrictions, provider disablement, module/project permissions and normal approval checks still apply. Template values cannot silently overwrite manual prompt edits. Saving the template does not call a model or authorize future generation.

The main PostgreSQL regression gate passed 38 cases; the final five focused cases also passed and overlap that gate. Three browser tests, TypeScript and the production build passed. Live synthetic private review/confirmation and placeholder follow-ups passed, then the unfinished generation request was cancelled and the synthetic template/artifact/chat data archived. No generation approval or cloud call was made; API logs independently confirmed zero calls for the workspace's runs. Local release 324 passed after deployment. Actual generation for these new template flows is integration-tested with a mock, since live Gemini image requests previously returned HTTP 429. Full enterprise-agent acceptance and ClickUp comparison remain incomplete.

### Follow-up: image-preserving dashboard exports, 2026-11-14

Private and reviewed shared dashboards now embed the exact pinned image pixels in Word, PDF and Excel downloads. This supersedes the earlier image-dashboard Office/PDF export limitation below. Private exports resolve the owned historical version with native source export authorization; shared exports load only separately published, signed snapshot copies after current audience/module/project/export checks. No image URL is fetched. Missing/corrupt pixels fail explicitly, and shared export access is denied after revocation. Export byte/pixel budgets remain bounded. Word uses real headings and source tables rather than displaying Markdown text, and images retain their aspect ratio.

The new integration coverage exposed a genuine preflight defect when optional dashboard panel display settings were omitted. The resolver now applies the existing typed panel defaults consistently before accessing those settings. The final disposable PostgreSQL gate passed all 52 cases across dashboard/image exports and text/image sharing. Two browser regressions, TypeScript and the production build passed. A PDF page was rasterized and visually inspected; Word image dimensions/aspect and Office embedded bytes were checked structurally. A live private synthetic workflow created an imported image and dashboard through separate reviewed actions, verified image bytes in private and self-shared PDF/DOCX/XLSX exports, and verified revocation. Synthetic artifact/chat data was archived. API 1534 remains healthy and local model release 324 passed its post-deployment check. No cloud calls, model retraining or business messages occurred. Full enterprise-agent acceptance and comparative ClickUp benchmarking remain incomplete.

CRM, PMS and HRMS can review `Import image file #ID called Title` and save an owned upload as a private, versioned PNG artifact using the existing conversation, Suite approval and artifact services. The files UI prepares the same command. Import uses no model. It preserves display orientation, strips ancillary metadata, verifies source ownership/hash/liveness at review and execution, and recovers a committed artifact after a lost outer receipt without creating a second version.

Image publication reuses signed artifact shares, with separate publication-only image copies. Audience readers cannot access the publisher's private artifact history. Review shows exact pixels; publication, new editions and audiences retain separate approval. Corrupt copies and stale editions are rejected. Revocation, discarded reviews and source archival retire the relevant publication bytes. Per-share byte/pixel and per-owner/workspace byte budgets bound storage. Dashboard image panels can be viewed and downloaded individually as PNG. Full Office/PDF export of image-containing dashboards is explicitly unavailable rather than silently omitting images.

The final disposable PostgreSQL gate passed 64 tests across image actions, private images, text/image shares and transcription, including local imports across all three modules and interrupted-receipt recovery. Two browser cases, TypeScript and the production build passed. A live synthetic private workspace verified reviewed import, exact self-share preview/publication/download, revocation and continued owner access to the private original. Synthetic artifact/chat data was archived afterward. No cloud model call or business message was sent. Local release 324 and private upload smoke checks passed after deployment to API 1534; School port 5173 was untouched.

Gemini image generation/editing remains implemented and integration-tested, but previous live requests returned HTTP 429. No further image inference was attempted in this milestone. No successful live Gemini image output, full parity or superiority is claimed. Real external connector accounts, the remaining native/media capabilities and the full comparative benchmark remain incomplete.

## Verified milestone: native CRM lead actions

- Added code-approved lead creation, updates, workbench qualification and conversion, plus a minimized qualification read. Existing saved agents do not gain tools automatically; updated specialist templates must still be reviewed and activated normally.
- Local lead conversations persist missing fields and explicit conversion choices, accept corrections, retain recorded qualification facts and support cancellation. They use deterministic typed grammar around release 243, not new TensorFlow weights. Cloud planners receive the same typed tools.
- 32 focused tests pass, including reviewed creation, dependent create → qualify → convert, replay prevention, stale snapshots, read-only denial, native qualification rejection, qualification facts over several follow-ups and minimized source disclosure.
- 676 existing tests pass across Suite actions/conversations/workspace, local intent/workflows, saved agents/builders and native lead management. These are synthetic integration/regression results, not a head-to-head ClickUp benchmark.
- Live API 1534 exposes the new tools; a private local create-lead dialogue collected details, rejected an acknowledgement as a name, retained fields during correction and cancelled its unexecuted draft. No real lead was created, no action was approved and no cloud call was made. Frontend 5186 proxy remains available.
- Conversion and qualification business writes are integration-tested in disposable PostgreSQL only. External accounts, other native module gaps, arbitrary conversational coverage and the full parity benchmark remain incomplete.

## Verified milestone: authorized employee profile actions

- Added native employee profile read/update tools and HR Assistant template bindings. Profile source projection excludes personal contacts, banking, identity documents, medical data and login roles. Personal contact writes still require native sensitive-field authorization.
- Local conversations collect an exact employee record ID and labelled fields, retain corrections, accept optional-field clearing and support cancellation. The workspace shows current/proposed fields before separate approval.
- Reuses native duplicate and organizational validation, existing Suite snapshots and native locked `If-Match` version checking at write time. A concurrent change between the last read and write was rejected in integration tests. Lost receipts do not cause automatic repeated writes.
- 73 focused employee/lead tests pass. Broader regression: 681 pass, one existing profile-browser test skipped because its separate Vite 5198 fixture was not running. Five targeted browser tests pass separately, including employee review and mobile layout; TypeScript and production build pass.
- Live API 1534 exposed both tools and completed an authorized profile preview through local follow-ups, then cancelled it. No employee update was approved or executed; no cloud call was made. Frontend 5186 proxy passed its access check. Server-local model remains release 243 with no new training or automatic private-data collection.
- Profile editing excludes account roles, employment status, payroll, banking and identity fields. This milestone does not prove complete HRMS action coverage, all ClickUp tools or head-to-head quality parity.


## Verified milestone: reviewed support-ticket workflows

- Added native HRMS ticket read, account lookup, assignment, status, escalation and public/internal reply tools. Local follow-ups retain corrections and cancellation; cloud planners receive the same schemas and versioned helpdesk planning guidance. This extends the existing server-local classifier with typed action grammar; it does not retrain TensorFlow weights.
- Reviewed chains use current ticket versions, dependencies, explicit reply visibility, current company/participant access, active eligible assignees and native row-lock checks. Internal notes require helpdesk management permission. Native ticket listing, replies, analytics and SLA queries share the same authorized subset and exclude enterprise diagnostic tickets.
- Suite private state and routes use AI grants while native actions still require their own module grants. Verified an HRMS-only requester can use private conversations and separately approve an authorized public reply while PMS access remains denied. Company kill switches and quotas remain effective under own-record policies; ordinary reads do not create settings.
- PostgreSQL regression gates passed 280 existing tests and 95 focused authorization/regression tests. A further 11 control/directory edge tests passed, including unflushed settings and quota updates. These gates overlap and are not a unique-test total. The final broader control regression passed 217 tests, including emergency-disable enforcement, AI-only module policies, selected-company directory lookup and quota/security controls.
- Six targeted browser tests, TypeScript and the production build passed. The live server exposed the tools and retained local clarification/cancellation. There are no authorized native support tickets in the checked live directory, so no live ticket-write preview was verified. Actual dependent writes, stale versions and lost-receipt safeguards were tested in disposable databases. No live ticket action or reply was approved.

## Limited live ClickUp/Gemini comparison

The same synthetic, planning-only request asked both products to assign ticket QA-42 to Ravi, add an internal note saying "Access reviewed", then resolve only after the note succeeds. It explicitly prohibited execution or contacting anyone.

- ClickUp Brain searched for the ticket/person, retained a three-step proposed outline with the note-success dependency, and asked for a ticket link/ID and Ravi's full name, email or mention. The private AI conversation was observed in the browser; no task or outgoing human message was created.
- Our first comparable auto-mode Gemini response asked for a backend version counter. Added server planning guidance to fetch versions from authorized native reads and preserve a non-executed outline while identifiers are missing. Normal review also hides those counters while preserving the signed payload.
- The live candidate returned `needs_clarification`, retained an assignment/note/resolution outline and asked for the ticket record ID and Ravi's user ID or email, without asking for a version. Gemini `gemini-3.5-flash-lite` returned HTTP 200. No native source read or business action was executed in this missing-ID case. The response remains more technical than ClickUp's link/name wording, and the returned summary alone does not prove executable dependency correctness.
- An earlier summary-mode diagnostic is excluded from the comparison because that mode intentionally suppresses actions and clarification. Private outputs were not automatically added to training data. One synthetic clarification case establishes neither full feature parity nor superiority; an authorized execution benchmark and broader real-world evaluation remain outstanding.


## Verified milestone: model consumption without unrelated PMS access

- Reproduced a real HTTP 403 for an AI/HRMS-only consumer: cross-module query capture and model telemetry were still classified as PMS state. These private records now use AI grants, with native company, actor and branch isolation retained. Native PMS actions and records keep their original module requirements.
- Provider consumption reads only authenticated company/personal or explicitly authorized workspace configuration scopes as server-only control metadata. Disabled overrides, data-sharing restrictions, explicit workspace inheritance and ambiguous sponsorship behavior are preserved. No duplicate provider table or browser credential storage was introduced.
- Added the AI-authorized, read-only Suite provider catalog. The floating bot and Suite workspace use this safe metadata projection. Existing provider changes and connectivity tests remain administrator-controlled through their original endpoints. Provider administration without a PMS grant remains a separate follow-up; this milestone covers consumption.
- 84 PostgreSQL integration/regression tests passed, including ordinary AI/HRMS cloud planning with mocked provider HTTP, company isolation, disabled/data-sharing-denied providers, circuit breaking, another user's failure isolation, native workspace inheritance and existing operator behavior. Five targeted browser tests, TypeScript and production build passed.
- Live API 1534 and frontend 5186 were rechecked. A private no-action request used the configured `gemini-3.5-flash-lite` adapter and returned HTTP 200 with an answered run. Its conversation was archived; no business action or reply was approved. Restricted-role access is verified by disposable PostgreSQL integration tests rather than an actual restricted live account. Local TensorFlow release 243 remains unchanged and server-side.
- This closes one cross-module consumption gap; it does not establish full ClickUp functionality, external account readiness, or model-quality superiority.


## Verified milestone: recovery controls during operational stops

- Suite owners can inspect their runs/conversations and cancel pending work after exhausting quota or an emergency stop. New commands, approval and resume retain the normal execution gates. Current AI grants, actor/company/branch ownership, workspace access and signed authorization-state checks remain mandatory.
- Added a signed control fingerprint excluding only operational stop switches, derived alongside the unchanged execution fingerprint from one authorization-state read. Control proofs cannot authorize action execution, confirmation or payload approval. Normal conversation retrieval keeps its original execution-proof isolation; explicit internal owner-control queries use the separate proof.
- Older signatures are not rewritten. An unchanged legacy context or one matching the current all-enabled baseline can prove control access. A nondefault historical baseline that cannot be proved after a switch change remains blocked; no old permissions or flag values are guessed.
- Final current-code gate: 148 PostgreSQL tests passed, with zero failures/errors/skips. It includes emergency/quota cases for both unapproved drafts and already-approved queues, default legacy contexts, nondefault fail-closed behavior, revoked access, cross-user isolation, tamper rejection, zero-trust checks, providers and existing Suite conversations/operator actions.
- Live private draft inspection and cancellation passed; the conversation was archived. No live emergency switch or quota was modified, no cloud call was made and no business action was approved. API 1534 and frontend 5186 remained available. The stopped-state cases were executed in disposable databases.
- This improves recovery reliability; complete ClickUp parity and the full enterprise platform objective remain unverified and incomplete.


## Verified milestone: central AI provider administration

- Added canonical `/ai-agents/providers/:provider` pages and Suite provider configuration/test routes. They reuse the existing form, handlers, encrypted provider table, adapters, rate limits and audit services. AI settings and workspace links now use the AI page; legacy PMS routes remain registered.
- Central configure action plus native settings-management permission are both mandatory. AI administrators can update an existing company configuration without owning its original row or receiving PMS record access. A missing replacement key preserves the stored key. Separate companies remain isolated; unmanaged native workspace overrides are rejected.
- Provider configuration uses AI scope only when consumed through the AI module; legacy PMS endpoints keep their classification. Authorized administrators can inspect and repair connections during an emergency stop. Ordinary consumers remain subject to execution-stop gates.
- The settings form can load and save when optional PMS usage analytics is denied; it does not invent zero usage values. Backend gates passed 47 provider/operator regressions, 31 authorization/recovery checks and seven focused administrator tests. These overlap and are not a unique-test total. Two targeted browser checks, TypeScript and production build passed.
- Live saved Gemini connectivity returned HTTP 200 using `gemini-3.5-flash-lite`, recorded as CROSS usage. The existing encrypted credential was unchanged; no configuration save or business action was performed. Restricted-role behavior is verified in disposable PostgreSQL HTTP integration tests, rather than a newly created live administrator account.
- Full enterprise Super Agent functionality, external account readiness and ClickUp execution parity remain incomplete and unproven.


## Verified milestone: AI-scoped usage monitoring

- Added a central Suite analytics endpoint requiring AI configuration plus native settings-management authorization. It reuses the existing provider telemetry table and a shared reporting service with the legacy PMS endpoint. No separate analytics table or browser credential storage was introduced.
- The provider form and Suite activity view now load usage through AI administration. Own-scope administrators see permitted own-user events; organization-scope administrators can aggregate authorized users. Company/workspace and branch restrictions remain in force. Monitoring remains available during an emergency stop.
- Reports bound the period to 1–365 days and recent detail to 200 sanitized events. Tokens, latency, priced-request counts and known cost sums retain native semantics. Unknown cost stays null and partial sums are explicitly limited to priced requests. Private conversation text, prompts, responses and credentials are excluded.
- Server-plan counts use prepared Suite runs with server intelligence, rather than inaccessible PMS-only events. Cloud plans and requests lacking a prepared summary are excluded. The UI labels the visibility scope and remains usable if analytics temporarily fails.
- 37 provider/operator regressions and five focused usage tests passed; these overlap. Two browser checks, TypeScript and production build passed. Tests cover own versus organization visibility, period limits, company isolation, operational stops, missing pricing and invalid/cloud plan exclusion.
- Live usage returned HTTP 200 with 31 bounded, current-scope telemetry rows and a server-plan count. The check made no model call and no business write; restricted-role behavior is verified in disposable PostgreSQL HTTP tests. Full enterprise-agent functionality and ClickUp execution parity remain incomplete.


## Verified milestone: shared definitions under central module roles

- Reproduced a restricted AI/HRMS consumer failure: an approved shared agent was discoverable, but its bundled skill could not install because version messages lacked their existing conversation-parent scope rule. Added that real foreign-key relationship to the central scope engine. No private sharing bypass or duplicate version table was introduced.
- Verified installation creates recipient-owned agents and skills with private version histories. Repeated installation is idempotent, publisher-private memory stays excluded, and the recipient cannot read the source skill versions or agent history. The installed agent can prepare a local clarification without receiving PMS record access.
- Reproduced an authorization gap where organization administrator membership bypassed an explicit central AI configure denial. Managed library publishing/management now also checks the current central/branch configure grant. The same decision controls publishing/management metadata; denied publishers may still install approved definitions in their audience. Authorized managed publishers and legacy organization administrators retain their supported workflows.
- 47 library/agent/skill regressions and 42 authorization/branch checks passed. These gates overlap. Cases include permitted HRMS-only install/use, private version/source isolation, denial metadata, denied preview/revoke and positive publishing without PMS grants, plus existing publication/revocation and package behavior.
- Live catalog and private skill-version inspection passed; the private smoke skill was archived. No definition was published, no business action was approved and no model call was made. Restricted-role cases were executed in disposable PostgreSQL tests. Full ClickUp functionality and the complete enterprise-agent objective remain incomplete.


## Verified milestone: organization controls during execution stops

- Reproduced emergency-stop blocking of administrator catalog/history access. Current library administrators can now inspect approved definitions, revoke an edition and discard an exact pending preview during emergency stops or exhausted execution quota. Company/workspace authorization, current administrator/configure grants, signatures and revision/hash checks remain mandatory.
- New preview, publish and private install paths retain normal execution gates. Managed publishing/revocation/discard routes are classified as configuration operations, allowing an administrator with only AI view/configure and no PMS/record-create grant to revoke an existing shared definition.
- Final current-code regression: 36 tests passed, with no failures/errors/skips. It covers emergency/quota cases, history access, exact discard, stale hashes/revisions, denied new publication/install, continued runtime revocation after stop removal, managed permission denial and configure-only administrator success, plus existing library and owner recovery behavior.
- Live read-only catalog/detail/history checks returned HTTP 200. No live publication or stop setting was changed, no model call was made and no business action was approved. Stopped-state and managed-role mutations were verified in disposable PostgreSQL tests.
- This strengthens administrative recovery; full enterprise-agent capability and complete ClickUp parity remain incomplete and unproven.


## Verified milestone: reviewed PMS milestone management

- Added canonical milestone read/edit services on existing PMS tables, project authorization and schemas. The bot can find milestones within projects and review edits to names, descriptions, dates, eligible ownership, status and progress. Client approval remains separate; pending/approved client milestones cannot be edited through this operation.
- Local dialogue supports missing-ID clarification, acknowledgement rejection, labelled corrections, rename/reschedule/assignment/completion/reopening phrases and cancellation. Connected planning fetches the exact native revision and receives server guidance to resolve identifiers without asking users for concurrency tokens. The cloud path was tested with HTTP mocks, not a new live provider call.
- Native row locks/revisions and existing Suite snapshots protect against stale writes. Current/proposed cards identify milestone name/project, show derived completion progress, and hide concurrency metadata. Receipts link to the real parent project even when milestone and project IDs differ. Newly reviewed Project Coordinator template revision 3 includes the new tools; existing saved agents are unchanged.
- Fixed responsibility assignment invalidating its own execution receipt: milestone visibility is project-governed, so owner metadata alone does not change the authorization epoch. Actual project-parent moves remain invalidation events. The managed/native project checks and all other permission invalidation behavior remain in place.
- 120 security/milestone regressions passed, followed by 10 dialogue checks validating explicit-progress preservation and completion-draft correction. An earlier 42-test native/operator gate is complementary; these gates overlap. Three targeted browser tests, TypeScript and production build passed.
- Live tools, missing-ID follow-ups and cancellation passed with no model call or approved business write. No eligible milestone was found within the bounded scan of ten projects and twenty milestones per project, so an actual live milestone-update preview was not verified. Actual writes were verified in disposable databases. Local model weights were not retrained.
- Local named record/owner selection still needs identifiers; connected models can use authorized project/milestone/directory reads. Same-milestone changes must be combined into one reviewed action. Full enterprise-agent functionality and complete ClickUp parity remain unfinished.


## Verified milestone: compound milestone drafts and contextual corrections

- Local milestone grammar combines same-record rename/reschedule clauses with `and` or `then` into one reviewed native patch. Pending-draft pronoun corrections retain the selected record and other proposed fields. Corrections can be collected before the record ID, while keeping exact selection mandatory.
- Clause and field boundaries are recognized outside quoted literals; names containing action words, `it`, or apparent field labels stay intact. Conflicting values, cross-record compounds, unsupported operations and incomplete clauses are clarified without silently discarding a requested action.
- Routed validated milestone edits around the legacy creation-only composer and ahead of the generic single-action guard, retaining the earlier permission/consent/destructive checks. Existing canonical preflight, revisions, project permissions and separate approval still own all execution.
- 62 milestone/workflow regressions passed, followed by 26 focused checks covering final slot-order handling. Gates overlap. End-to-end cases verify reviewed execution of both fields, natural corrections and cancellation without a record selection; pure language checks cover quoted literals and ambiguity.
- Live private dialogue retained compound fields and a natural name correction, rejected acknowledgement as a record selection, then cancelled and archived. No actual milestone was selected or updated, no business action was approved and no model call was made. Local weights were not retrained. Full enterprise-agent functionality and ClickUp parity remain incomplete.


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


## Verified milestone: new project with a parent task and subtasks

Local conversation planning can now prepare a native project and a true parent/subtask hierarchy in one review. Example: `Create a project called Customer launch with task called Release with subtasks Design, Build, Test`. The existing composer, Suite dependency engine and canonical PMS create services are reused. No parallel project/task tables or new model storage were introduced.

The project is action 1, the parent task is action 2, and subtasks reference the parent task's confirmed receipt rather than the project ID. Ordinal/name draft revisions retain these absolute references. Removing a parent with remaining subtasks is blocked; removing an individual child retains the other relationships. Existing approval, project/workspace permissions, typed references, checkpointing and duplicate prevention remain mandatory. This local grammar supports one parent hierarchy per new-project request; it does not claim arbitrary nested project structures or unresolved named assignments.

All 54 conversational/workflow regressions passed. Two focused checks also passed; these overlap the broader gate, and the final focused integration additionally injects a pre-dispatch interruption after project/parent creation. Resume retained both completed receipts, created only remaining children, and a repeated approval/tick created no duplicates. Live private preview verified five dependent actions and a subtask-title correction with correct references, then cancelled/archived without creating a project or task, approving a business action or calling a cloud model. Local model weights were not retrained. Full enterprise Super Agent functionality and ClickUp parity remain incomplete.


## Verified milestone: workflow inspection and cancellation during operational stops

Multi-agent workflow history, detail, combined results and owner cancellation now use the existing explicit owner-control path. An emergency AI switch or exhausted company quota stops new planning, resume, retry and action approval while allowing the authorized owner to inspect and cancel existing work. Current identity, ownership, workspace, branch and AI entitlement checks remain mandatory; control proofs do not authorize business execution.

Child traversal propagates this read/cancel-only option through the existing scheduled-occurrence helper, including superseded follow-up drafts and unrecorded child IDs. In a cancelled planning wave, a child committed before a lost response is recovered by its original request key and cancelled even after an operational stop. Normal dispatch, handoff preparation and resume retain execution gating. No parallel workflow tables or separate cancellation engine were introduced.

The workflow/Suite-control gate passed 31 tests; parallel-handoff/scheduler/migration regressions passed 36; eight focused current-code cases passed after the final cancellation-race fix. Gates overlap. Tests cover draft, queued and revised child cancellation under quota and emergency stops, ownership denial, blocked new work, parallel preparation, response-loss recovery and retained schedule behavior. Live private workflow preview/list/detail/results/stop passed without starting the workflow, creating child plans, approving business actions, changing operational switches/quotas or calling a cloud model. Its private agent profile was archived after the check. Local model weights were not retrained. Full enterprise Super Agent functionality and ClickUp parity remain incomplete.


## Verified milestone: schedule and event controls during operational stops

Recurring schedule history/detail, pause and cancel now use the existing explicit owner-control path. Event subscription list/detail and pause/cancel use the same path, including workspace authorization and signed subscription validation. New previews, activation and resume retain normal execution gates. Event preview checks operational authorization before looking up its agent so emergency stops and exhausted quotas report their actual gate rather than masking it as a missing profile. Existing current identity, ownership, company, branch and AI entitlements remain mandatory.

Schedule cancellation stops future occurrences; already prepared action drafts retain separate review and cancellation. Event subscription cancellation stops new intake; existing occurrences remain separately controllable through schedules/conversations. No parallel schedule engine or storage was added. Schedule detail now has a canonical owner-authorized GET endpoint.

The schedules UI loads reminders, existing schedules and creation options independently. If creation catalogs or reminder data are unavailable, successfully loaded schedule controls remain visible. Event intake likewise distinguishes partial option loading from usable existing triggers. These changes reuse the existing controls and server APIs.

The schedule/workflow/migration gate passed 48 tests, and the final event/chat/email/WhatsApp/webhook gate passed 52. Two targeted browser tests passed, including pause/cancel with quota-failed creation lookups and verification that no activate/resume/approve request was sent. TypeScript and the production build passed. Live private schedule/event preview, list/detail and cancel passed with no activation, occurrence planning, approved business write, cloud call or operational-setting change; the temporary private agent was archived. Stop/quota scenarios were exercised in isolated databases. Local model weights were not retrained. Full enterprise Super Agent functionality and ClickUp parity remain incomplete.


## Candidate milestone: workplace dialogue fine-tuning

Added 450 versioned synthetic dialogue turns (150 per CRM/PMS/HRMS) and 90 separate context-labelled probes using 30 authored phrases. Private query histories are not imported. From-scratch 64/96-unit candidates improved some wording probes but regressed on development data and remain unreleased. Fine-tuning from the verified release 243 retained its vocabulary and starting weights, selected checkpoint 100 by authored development performance, and achieved 95.9% development accuracy versus 90.6% for the baseline. New workplace probes improved from 63/90 to 81/90; the existing v2 message probes improved from 51/60 to 58/60. These are small synthetic/regression checks, not production accuracy or competitor rankings.

The exported fine-tuned candidate passed numeric/reload parity, 21 planning integration cases, 684 conversation programs, 600 common-action routes and a 234-test PostgreSQL gate. The latter contains 141 canonical core tests and 65 message-action tests with overlapping conversation coverage. The experimental candidate passes the current release policy but is not registered or activated; live release 243 remains unchanged.

The platform trainer now freezes a verified starting release when compatible, fine-tunes the dialogue head, records safe lineage/metrics and training stages, and runs canonical release checks against fresh disposable local PostgreSQL databases. Check databases are cleaned after evaluation. Release policy requires separate workplace wording and exact-weight planning integration; classification scores cannot replace action checks. The admin UI distinguishes seen examples, development wording and separate probes without fetching model weights.

Managed end-to-end verification found compound-object routing defects: lead reminders, lead notes and lead outreach were intercepted by lead creation. The shared boundary is fixed while labelled lead fields remain supported. All 3600 authored recognition examples preflighted successfully after the fix; 85 focused regressions, 43 release/platform checks, one targeted browser check, TypeScript and production build passed. Gates overlap. Live private smoke checks retained release 243 and correctly clarified lead reminder/note commands without approving business writes or calling cloud models.

The full managed workflow verification subsequently passed: one end-to-end integration test exercised approved training, canonical PostgreSQL actions, message checks, release signing, activation and reset in its isolated platform. The controller is terminal; do not restart it. Inspect `.local/workplace-model-verification.json` for evidence. The live experimental candidate remains unregistered and inactive. Browser audit also found active legacy PMS/writing workers and public classifier assets that still need migration. Server-only compliance and full ClickUp parity are not yet complete. Preserve native capabilities and explicit provider choices when unifying those paths.
