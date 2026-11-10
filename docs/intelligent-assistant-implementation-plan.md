# BusinessSuite intelligent assistant implementation plan

Updated: 10 November 2026. Scope: one assistant across CRM, HRMS and PMS first; reuse existing AI, authorization, provider settings, approvals and workers. OpenAI means the server-side OpenAI API, not a ChatGPT subscription. Cloud credentials stay in the existing encrypted provider configuration.

## Phase 1 — Unified briefing, evidence and reviewed native actions

### Deliverables

- Extend `/ai-operator/suite` and the existing AI workspace; no parallel assistant backend or credential store.
- Select OpenAI or Gemini through existing scoped provider adapters. Retain Claude compatibility. Offer an explicit local rules mode for deterministic briefs and bounded task creation; do not represent it as a general-purpose local LLM. Preserve the existing browser-local PMS model separately.
- Read current CRM tasks, selected-workspace PMS projects/tasks and personal HR leave/tickets through canonical APIs and existing tool authorization.
- Daily briefing: overdue, due-today, blocked and high-priority work; personal/all-visible scope, module and deadline filters. Mark bounded source coverage and source failures.
- Delivery signals: project-linked blocked/overdue tasks and missed project deadlines. Attribute only to actual project/client links; no inferred CRM customer matching or unsupported financial impact.
- Source identifiers, retrieval timestamps and authorized deep links. Cloud answers select from server-issued evidence IDs; reject fabricated citation IDs. Distinguish a source list from independently verified claim-level entailment.
- Reuse exact-plan previews, hashes, expiry, approval, cancellation, queued execution and receipts. Local bounded commands can prepare CRM/PMS tasks; HR leave/helpdesk actions continue through the existing cloud tool catalog and business rules.
- Show citations and source coverage in the current operator UI. Clear scoped data when workspace, organization or branch changes.

### Engineering work

1. Add shared evidence and local-plan helpers, plus a deterministic briefing service with canonical reads.
2. Add evidence to existing command prompts/results without changing the approval contract.
3. Add provider selection and a briefing component to the existing suite workspace.
4. Exercise ranking, timezone boundaries, missing dates, completed work, source limits, authorization failures, local no-cloud behavior, citations and approval-before-write.

### Acceptance

- Native briefs work without a model key; local mode makes no model request.
- Unauthorized module data is never included. Failed reads are explicitly marked; an unavailable source is never reported as empty.
- Only real authorized source IDs become citations. Task drafts have no business effects before approval.
- Existing suite operator/approval regressions and frontend type checks pass.
- Live OpenAI/Gemini verification is conditional on configured test credentials; mocked transport tests are labeled accordingly.

## Phase 2 — Broader native tools, invoice drafts and usable reports

### Deliverables

- Expand CRM: owner/date/status/customer filters, task reminders, follow-up plans, lead/deal summaries and internal notes.
- Expand PMS: task creation with assignees, milestones, due dates, dependencies, checklists and status updates through existing validators/executors.
- Expand HRMS: personal leave requests, helpdesk tickets, policy answers and authorized manager availability/approval queues. Keep sensitive payroll fields out of general context.
- Add typed report requests: module, entity, dimensions, measures, date range, status, owner, customer and output format. Use approved report services and deterministic aggregates, with filter/source metadata and export authorization.
- Reuse SRM invoice draft tooling and canonical customer, seller, currency, tax and line validation. CRM/PMS context does not substitute for SRM/FAM permissions or installed modules. Issuing/sending invoices, posting ledgers and taking payment remain separate business actions.
- Replace short local command coverage with more typed local intents and, if justified, a browser-local model adapter feeding the same validator. Unsupported local requests ask for structured fields instead of silently switching to cloud.

### Acceptance

Real CRUD integration tests for each added tool; denied-role and tenant tests; exact report totals on known fixtures; invalid filters rejected; invoice drafts cannot issue, post or charge money; ambiguous customer names require selection. Test pagination and filters against canonical endpoint contracts.

## Phase 3 — Reminders, commitments and connected communication

### Deliverables

- Scheduled reminders with explicit timezone, recipients, channel, quiet hours, deduplication, owner, expiry and cancellation.
- Reuse the existing notification/email dispatch and durable jobs. Store schedule configuration, not a long-lived user bearer token; reauthorize at execution.
- Pilot Google Workspace OR Microsoft 365 using existing OAuth/vault/connector code. Add the collaboration channel used by the pilot customer; expand afterward.
- Inbox/meeting-to-task drafts, customer commitment links and delivery follow-through. Keep author/source/time and ambiguity attached to extracted commitments.
- Connection health, scope checks, token/subscription renewal, incremental sync, revocation and deletion propagation. Never infer user access solely from service-account or bot membership.
- Outbound reminders show recipients/content before approval or use narrowly configured standing consent. Handle send timeouts as unknown until reconciled; do not blindly repeat messages.

### Acceptance

Duplicate jobs/events produce one effect; cancelled/expired rules do not send; permission withdrawal blocks execution; timezone/quiet-hours cases pass; send receipts reconcile; live pilot OAuth and webhook recovery are verified. Public Google app verification and tenant admin consent are tracked where applicable.

## Phase 4 — Proactive business operations and measured expansion

### Deliverables

- Source-backed customer → deal → project → delivery → invoice views using explicit existing entity links.
- Capacity scenarios using authorized skills, allocations, leave, working calendars and dependencies. Label projections and missing evidence.
- Reusable playbooks with limits, owner, expiry, stop rules and inspectable memory. Allow bounded reversible autonomy only under explicit policy.
- Model routing by measured quality/cost, optional voice and regional languages, and allowlisted MCP tools sharing the same policy gateway.
- Production observability: source freshness, policy denials, approvals, partial/unknown outcomes, token/cost ceilings, circuit breakers and incident handling.

### Acceptance

Versioned benchmark of factual answers, business workflows, ambiguity, prompt injection, tenant boundaries, revocation and connector failures. Require authoritative receipts for claimed writes and no unauthorized disclosure/effects in the release suite. Compare overlapping workflows with ClickUp under equivalent data/access conditions; report domain coverage separately from reasoning quality.

## Delivery order and dependencies

Each phase ships only after its own acceptance checks. Phase 2 depends on shared tool/evidence contracts from Phase 1; Phase 3 depends on reliable native writes, jobs and receipts; Phase 4 depends on proven source freshness, identity mappings and recovery. Calendar estimates follow baseline testing and pilot scope selection; no unverified deadline is implied.

## Phase 1 implementation record

Implementation and verified checks are recorded in the completion message. Remaining phase work must not be labeled shipped merely because supporting legacy code exists. No production credentials, customer data, external sends or deployment are needed for Phase 1 development.
