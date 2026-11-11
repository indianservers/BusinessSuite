# CRM connector and automation rollout

Started 11 November 2026. This tracks the 25 requested workflows. Adapter code,
workflow execution, and live provider acceptance are separate milestones. No live
provider account was connected or external message sent during this implementation.

## Delivered in the first implementation

- Lead workbench links directly to CRM connectors. CRM connectors expose Facebook
  and LinkedIn authorization shortcuts and explain first-import review.
- Facebook source setup loads up to 100 Page forms, with explicit form-ID entry
  for further forms. Page/token access errors remain visible.
- Facebook retrieval explicitly requests lead identity, answers, form/ad identity,
  and submission time. Custom answers and multi-select responses survive mapping;
  attribution and custom answers are included in native lead notes.
- International phone calling codes are detected using the existing phone library.
  National numbers without a code fail preview instead of receiving an invented region.
- Authorized sync reads and Facebook form/lead reads retain numeric business IDs
  and phone numbers. They still remove credential keys and actual credential values;
  debug-text redaction remains the default for other operations and diagnostics.
- Lead imports accept email or a normalized phone/calling-code pair for identity.
  Existing ownership, native record edits, branch checks and import receipts remain
  subject to the existing import service. Job title and notes are optional lead fields.
- CRM leads can be the source of supported outgoing contact workflows: enrichment,
  contact sync, call-center contact creation and contract drafts. Source visibility,
  preview fingerprints, write authorization and operation deduplication are reused.
- Sync jobs report health, last success, failure category and consecutive failures.
  Transient failures respect provider retry delays and bounded exponential backoff.
  Automatic retries stop after eight failures or permanent/uncertain errors.
  Credit-consuming Surfe retries retain their explicit review flow.
- The Power Apps worker dispatches connector imports as well as event workflows.
  The shared follow-up scheduler remains compatible. Lease checks prevent the
  workers from simultaneously reading the same job; later jobs are no longer
  permanently excluded by the first-1,000 candidate limit.

## Work remaining across the 25 workflows

1. Facebook/Instagram capture: signed Page/form-bound leadgen ingress now wakes
   automatic sync immediately; polling remains catch-up. Live Meta acceptance and
   app/Page subscription configuration remain deployment steps.
2. Immediate WhatsApp acknowledgement: connect lead-created events to approved
   templates and enforce existing consent/suppression checks.
3. Gmail/Microsoft email: bind provider conversations/replies to CRM identity.
4. Follow-up sequences: execute provider delivery and stop on real reply events.
5. Capacity routing: working days, time zones, same-day shifts and active-lead
   limits now filter source rules and round-robin/workload routing. Unavailable
   rule owners fall back to eligible distribution; leads stay unassigned for team
   review when no seller is available. Automatic reprocessing of that queue and
   team-specific routing remain.
6. Response SLA escalation: imported leads now initialize native operating state,
   routing, creation tasks and notifications. Scheduled response-SLA escalation
   and duplicate suppression are covered by integration tests.
7. Calendar booking: verify external free/busy and lifecycle synchronization.
8. Integration health: deduplicated owner-only in-app expiry alerts delivered;
   extended operator recovery history remains.
9. Google Ads lead forms: key- and form-bound intake, encrypted submission queue,
   worker import, manual review, retry and pause/resume delivered. Live Google Ads
   acceptance remains a deployment check.
10. LinkedIn forms: live Lead Sync acceptance and CRM setup/mapping improvements.
11. Website/live chat: connect chat transcripts and marketing attribution.
12. Telephony: process call outcomes and missed-call callback automation.
13. Shared inbox: unify channel threads, assignments and agent handoffs.
14. Enrichment: lead-based manual connector workflows now supported; add policy-driven
    automation, provenance and credit budgets.
15. Identity: phone-only import matching delivered; broaden canonical cross-channel
    identity with ambiguous-match review and merge history.
16. Quotes: connect approval outcomes to delivery and follow-up.
17. E-signature: lead-based drafts supported; signature events and deal transitions remain.
18. Payments: connect verified payment events to CRM balances and follow-up.
19. Delivery handoff: connect won deals to customer/project/order creation once.
20. Renewals: add contract-date and customer-signal workflows.
21. Meta conversion feedback: qualified/won event mapping and provider acceptance.
22. Google conversion feedback: supported ingestion route and provider acceptance.
23. Attribution: join spend, qualified leads, won deals and collected payments.
24. IndiaMART/Justdial: confirm supported commercial APIs before implementation.
25. Workflow recipes: add tested, configured recipes to the existing builder.

## Verification and activation

### Second implementation: notifications, native workflows and Google intake

- Per-job Facebook setup returns a callback URL and one-time verify token. The app
  secret is encrypted server-side. GET challenges and raw-byte SHA-256 signatures
  are validated; Page and form identities are bound to the existing scoped job.
  Repeated lead notifications do not wake the worker again. Rotation invalidates
  the old endpoint. Notifications arriving during a provider read schedule a new
  pass so the current read cannot lose the wake-up.
- In CRM connectors, open **Facebook instant notifications** on an automatic job.
  Configure the returned callback/verify token for the Meta app's Page `leadgen`
  webhook, and subscribe the app to that Page. The UI does not claim this remote
  subscription was created automatically. Keep the Power Apps worker running.
- New lead imports call the native lead-creation hook after validation. Assignment,
  tasks, timeline records, operating state and in-app notifications participate in
  the import transaction. Their records are included in the guarded undo receipt.
  Duplicate/skipped rows do not repeat these actions. Revoke intentionally blocks
  when downstream records have since changed.
- In **Google Ads lead forms**, register a form ID for the selected writable CRM
  branch, copy the returned webhook URL and one-time Google key into Google Ads,
  and send test data. Test leads never create CRM leads. Real submissions are
  encrypted until the worker creates a native import batch, after which the queued
  payload is cleared. Validation errors go to review; authority failures stop for
  explicit retry. Source owner, company, branch and permissions are rechecked by
  the worker. Source pause/resume and recent batch review are available in CRM.
- For known connector expiration times, the worker emits one in-app notification
  per connection/expiry/status. Expiring (within 72 hours) and expired credentials
  are distinguished. Providers that supply no expiry timestamp cannot be warned
  about in advance; revoked tokens still surface through sync failures.
- In lead workflow settings → assignment, enable an optional working-hours/capacity
  policy for configured owners. Time zones are validated IANA names. Shift end is
  exclusive, and archived/converted/lost leads do not consume capacity. Configuration
  locking serializes automatic capacity decisions with round-robin allocation.
  Explicit manual assignments retain existing permissions and behavior.

Reference contracts: [Meta lead retrieval and notifications](https://github.com/facebookincubator/catalogue-of-api-solutions/blob/main/solutions/leads/leads-retrieval-set-up-checker.md),
[Google lead-form implementation](https://developers.google.com/google-ads/webhook/docs/implementation).

Second implementation validation: the combined 121-test backend regression suite
passed, as did the 12-test Google intake/seller availability run and frontend
`npx tsc --noEmit`. New checks cover webhook authentication, binding, replay
deduplication, rotation, import side-effect undo, routing, SLA escalation, source
pause/retry, authority revocation, expiry-alert deduplication, and capacity/time-zone
boundaries. A paused-source backlog is excluded before the intake worker's batch
limit so it cannot starve active sources. Provider network calls use synthetic
transports; live provider acceptance and PostgreSQL concurrency are not certified
by these isolated database tests.

Run the focused connector, import and runtime tests in the backend test environment.
Tests use isolated databases and synthetic provider transports. Production activation
also requires real credentials, provider permissions, the relevant worker, and a
real submission-to-record acceptance check. A successful polling job is not proof
that an outbound message, assignment rule or conversion feedback event ran.

Validation completed for this tranche: 107 backend regression tests across CRM
connector reliability, imports, marketplace sync, runtime, provider authorization
and OAuth; frontend `npx tsc --noEmit`. The new reliability suite includes
phone-only lead import, cross-form duplicate prevention, credential-safe numeric
IDs, scheduler starvation/recovery, and Power Apps worker dispatch.

Use `/crm/leads` → **Lead sources & connectors** → authorize a provider → choose
an authorized connection in **Sync & native module workflows** → select the form
→ create a manual review job → inspect its import batch. Enable automatic import
and scheduling after the mapping is correct. Run the existing backend worker:
`python -m app.apps.power_apps.worker`.
