# Master Suite Phase 2 — shared-service foundation

Implemented on 2026-10-26. This document describes the implemented foundation and its remaining rollout work; it does not certify every Phase 2 scenario as complete.

## Adding a module

`AppModule.shared_services` defaults to true. Registration makes the installed module a consumer of existing authentication, central access policies, company entitlements, shared settings, workflows, approvals, AI, notification/email queues, integrations, forms/custom fields and documents. An optional `service_registration` module exposes `register_services()` during router assembly.

Use `app.shared.gateway.ModuleServices(db, actor, company_id, module_key)` inside a transaction. It provides `read`, `emit`, `approval`, `notify`, `email`, `integration`, `ai`, `ai_draft`, `documents`, `form`, `settings`, and `validate_custom_fields`. Commit the transaction to persist events. Never substitute a superuser for the calling user.

Domain records still need a small code-owned adapter, because the central service must know how to enforce native record access:

```python
from app.shared.contracts import RecordContract, register_record

def register_services():
    register_record(RecordContract(
        "new_module", "record", "/new-module/records/{id}", "new_module_view"
    ))
```

The fixed read endpoint runs through the real API with the actual caller and selected company. Native permissions, owner/team scope and business validation remain authoritative. `register_action` can register a fixed native API tool; administration cannot upload executable handlers or arbitrary action URLs. A regression test registers a future module and exercises its real endpoint, existing policy/settings, durable workflow and notification without creating another service implementation.

## Administration and execution

Open `/admin/control/services/services`. The central console includes a draggable graph editor, drafts, immutable published versions, execution history and controls, approved connections, signed webhook subscriptions, AI governance, delivery history, private documents and layered settings. Existing Phase 1 user/access and control pages remain available.

The runtime reuses existing automation jobs/logs and approval requests rather than creating competing engines. Events are captured transactionally from supported native ORM changes. Workers checkpoint each node, use a bounded execution lifetime/step budget, recheck the managed execution identity, and back off transient failures. Unsupported legacy simulated actions now fail explicitly. Native writes and integration requests enter `reconciliation_required` before their separate transaction/provider call; uncertain effects are not blindly retried.

Published graphs are append-only at both ORM and database levels. Definitions capture the execution identity in the published version. Approval groups bind independent approvers to a sanitized business-record snapshot, reject stale/tampered records and forged group references, and serialize decisions at the group row. Administrative mutations reuse Phase 1 password step-up and rate limiting.

## Service boundaries

- Notifications use the existing inbox and delivery logs. In-app persistence is operational. SMTP uses the existing provider infrastructure; acceptance means provider acceptance, not confirmed delivery. No external email was sent during verification. SMS, WhatsApp and push remain unconfigured.
- AI uses existing provider resolution, native tools and usage records. Company/module request budgets and permission checks apply. Provider availability and billed cost are not fabricated; live external AI execution was not verified.
- Integration secrets use existing encryption infrastructure. Outbound destinations are approved, HTTPS-only, DNS checked and pinned, with redirects disabled. Webhooks use timestamped HMAC, bounded bodies, replay checks and rate limits. External provider acceptance is not end-recipient delivery.
- Documents use private existing storage, real record authorization on upload/list/download, size and file-signature checks, immutable versions and audit metadata. PDF/PNG/JPEG are accepted. Malware scanning is not configured; do not describe files as scanned.
- Forms and custom-field validation reuse existing services. Some custom-field schema metadata remains global; relationship/unique/rollup field writes are rejected until a safe tenant adapter exists. Per-user setting overrides are explicitly reported unsupported.
- Legacy automation cannot access shared versioned graph definitions through its mutable endpoints. Tenant filters also protect approval/workflow records and queued email/delivery rows. This is not a claim that every legacy communication or public intake entity has been converted to a tenant-aware service.

## Migration and rollout

PostgreSQL revision: `pg_20261026_025_shared` after `pg_20261026_024_control`. SQLite revision: `20261026_025_shared` after `20261026_024_control`.

The revisions create policy/outbox/version/document tables, extend existing automation definitions and integration credentials, add tenant columns to approval/workflow/email records, and install published-version immutability triggers. Historical tenant backfill uses the author's common-person organization, with company 1 as the legacy fallback; delivery rows inherit their message organization. Review ambiguous historical ownership before a multi-company production rollout. Null/missing author organization cannot establish provenance by itself.

Only disposable test databases were migrated during this work. The development and production databases were not migrated. Before enabling the console, back up and inventory the target database, apply both pending Phase 1 and Phase 2 revisions through the correct migration tree, provision a non-superuser managed execution identity and encryption keys, and arrange periodic execution of the existing scheduled-jobs endpoint. Keep workers disabled during rollback; downgrade removes the new tables/columns and therefore loses their data unless exported/restored from backup.

## Verification and remaining scope

Verification evidence is under `docs/qa/suite-access/`. The real browser test uses actual FastAPI responses through a local test bridge: login, all shared-console sections, configure/drag/connect nodes, validate, save, publish, reload, native CRM write, outbox capture, worker execution and real inbox delivery. It captures desktop/mobile screenshots. No mocked provider delivery is presented as real delivery.

The foundation is implemented, but the full Phase 2 checklist still has gaps: all fifteen end-to-end business recipes; time-based scanning/scheduling beyond event/delay jobs; a guided manual reconciliation interface; approval delegation/resubmission administration; connection reconnect/test flows; document search/inline preview and revision-upload UI; per-user settings; richer node-output data mapping; complete migration of legacy public intake/communication tenant boundaries; and live configured external-provider verification. Existing native business flows remain the authoritative adapters. Phase 3 should not assume those gaps have been completed.


### Verified results for this checkout

- PostgreSQL migration plus shared services, central access/control and native automation regressions: **57 passed** (`phase2-final-postgres.log`).
- Final focused SQLite shared-service tests, including date offsets and effective node limits: **16 passed** (`phase2-final-focused.log`). A subsequent combined focused/backend and real-browser run also passed: **17 passed** (`phase2-final-focused-browser.log`).
- Actual browser workflow: **1 passed** (`phase2-final-browser.log`), with desktop and mobile screenshots.
- Frontend TypeScript and production Vite build: **passed** (`phase2-final-build.log`). Existing dependency annotation warnings remain.
- No production migration, external-provider delivery, live AI-provider call or deployment was performed.


### Integration inventory and API surface

Inspected native CRM/Sales (leads, quotes, tasks), PMS (projects, tasks, forms), HRMS (leave, employees), SRM/Finance (invoices), automation, approvals, communication, AI operator, platform credentials, custom fields and storage. Code-owned read adapters currently cover CRM lead/quote, PMS project/task, SRM invoice and HRMS leave. Other module keys inherit the service contract automatically, while domain-specific record/actions require registration; this inventory does not imply every business scenario has a complete adapter.

New APIs live at `/api/v1/access/services`: catalog/overview, settings, workflows and published versions, graph validation, events, executions and execution commands, bounded worker tick, connections, signed webhook subscriptions/receiver, delivery, AI governance and authenticated document operations. Existing authentication, approval inbox, forms, custom-field, provider setup and business endpoints are reused.

Phase 3 readiness: the central consumer contract is available and tested. Full Phase 2 acceptance and a production rollout remain pending the gaps above, target-database migration review, and configured-provider verification.
