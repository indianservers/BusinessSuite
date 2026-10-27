# Power Apps Approvals — Phase 5

## Delivered implementation

The standalone application starts at `/power-apps/approvals`. Its inbox, requests, new request form, designer, templates, policies, delegations, analytics, audit and settings routes use persisted company/environment-scoped data. The inbox has search, priority filtering, pagination and a keyboard-dismissible detail drawer with focus trapping. The responsive drawer supports real document downloads, comments, reasoned decisions and request changes.

The designer reuses the Automation Studio canvas and condition builder. It supports ordered stages with all, any, strict majority or quorum voting inside each stage, conditional stage execution, versioned policy publication, business calendars, temporary delegation, reminders, escalation and expiration. Guided form controls author the existing approval schema; the server validates submitted values. Unsaved edits disable publication. Templates are twenty disabled configuration starting points; they require authorized approvers before use.

Approval requests reuse the existing ApprovalRequest, ApprovalHistory and ApprovalComment models. Policy versions reuse PowerResource/PowerVersion. Five additive metadata tables hold policy links, request state, assignment seats, delegation periods and attachment metadata. No native business-module integration was activated.

## Execution and consistency

`approval_wait` is a canonical node on the existing Phase 3 persistent queue. Sequential stages create waits; parallel approvers occupy independent seats in a stage. The normal worker tick sends reminders, records escalations and expires overdue requests. It never approves automatically. Rejection follows an explicit rejected output. Changes and resubmission restart all approval stages in the same execution while preserving earlier decisions and cycles. In-app notifications use the existing notification table in the decision transaction.

Decisions lock execution, request and assignment state consistently, check expected revision and idempotency, revalidate current permissions and delegation, and reject requester self-approval. A missing or ambiguous approver creates Resolution Required. Administrative resolution does not silently reduce the published group to a single voter.

## Deployment

Review the additive migration 037 in both Alembic trees. Its PostgreSQL predecessor is `pg_20261027_036_integrations`; its other-tree predecessor is migration 036. Use the repository deployment procedure for the configured database. These migrations were tested against isolated stores; no production migration or deployment was performed.

Run the existing worker from the backend directory with `python -m app.apps.power_apps.worker`. Keep the API and worker on the same database, signing configuration and private storage. Existing worker deployment configuration remains authoritative. Policies start disabled and publication requires explicit manage, publish and execute authority. Submission, decision, delegation, audit and export permission names are registered independently; a permission name alone does not imply an implemented export endpoint.

The execution limit inherited from Phase 3 is seven calendar days for the complete request. A process supports up to twenty stages and thirty form fields. Selector input lists support thirty identities each. Attachments permit up to ten references of at most 2 MB each, with PDF, PNG, JPEG and UTF-8 text validation. Files use content-addressed private storage, authenticated downloads and signed hashes. A malware scanner is not configured.

## Evidence and operations

History events form an HMAC chain bound to company, environment, request, execution, actor, reason, timestamps, policy snapshot, request contents, decision state and document hashes. Completed assignment decisions and history are immutable through the ORM. Verification detects direct storage tampering and blocks subsequent mutations from resealing altered records. This is application audit evidence, not a qualified electronic signature or protection from an operator holding both database and signing-key access.

Verification accepts SECRET_KEY and SECRET_KEY_PREVIOUS. Preserve historical verification material before rotating beyond that pair; a full historical keyring is not implemented. Approval evidence is retained without a deletion API. Existing execution-payload retention is separate; do not treat payload retention as a configurable approval-record retention policy. Back up private document blobs with the database.

## Remaining scope

The current canvas authors sequential stages with parallel voting within a stage. It does not provide twenty-five separate approval node types or arbitrary branching approval graphs. Policy selectors consolidate those operations around the canonical wait node. Bulk decisions, dedicated audit exports, configurable approval-evidence retention and the complete Phase 6 shared Forms builder are not delivered. Some advanced actor settings still use explicit role or identity IDs. Phase 4 connector work remains independently incomplete as recorded in power-apps-phase4.md.

The user's Zapier, Make and n8n comparison is a product quality target. No comparative usability, performance or feature-superiority benchmark has been run; this implementation does not establish superiority over those products.

## Verification

See power-apps-phase5-security.md for security scenarios and docs/qa/power-approvals-*.png for browser captures. The approval test module covers persisted decisions, all voting modes, sequential stages, conditional stages, request changes, delegation, private files, reminder/escalation/expiry, concurrency, restart recovery, analytics and authorization. Migration tests cover additive upgrade/downgrade behavior without deleting legacy requests.
