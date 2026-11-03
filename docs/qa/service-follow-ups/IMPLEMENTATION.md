# Products/services visibility and shared service follow-ups

Implemented on November 3, 2026.

## Root cause

`SRMPOSPage.tsx` filtered the shared inventory master by `activeStoreProfile.categories`. If even one item matched the selected template, every item in any other category disappeared. The Bookstore Retail profile allowed only General, Stationery and Office Supplies. This explains why switching templates could hide services and other catalogue categories even though the inventory endpoint returned them.

The terminal now uses every active, non-deleted inventory row returned within the existing organization, branch and workspace permissions. Templates describe register behavior; category selection is explicit. No duplicate CRM product/service master was introduced. Existing SRM product IDs remain the canonical catalogue identities.

POS adds All, Products, Services, Packages and Recently Used tabs; counts, search, explicit category filtering, name/price sorting, and tax/category/duration information. Inventory reads accept optional validated pages of up to 500 rows. POS fetches successive pages of 200 until the reported total is reached. Existing inventory consumers retain the original response behavior when no page is supplied. The service quantity increment no longer clamps to inventory stock for untracked services.

## Routes and integration

Both CRM and Sales render the same page components and call the same APIs:

- `/crm/follow-ups` and `/srm/follow-ups`: dashboard.
- Append `/directory`: shared advanced grid.
- Append `/calendar`: Day, Week, Month and Agenda calendar.
- Append `/:id`: detail, contact log, internal comments, private attachments, reschedule, completion, cancellation and next commitment.

Navigation entries and dashboard summaries were added to both modules. Customer detail and deal pages link to shared commitments. Manual creation supports catalogue defaults and permitted lead/contact/deal/quotation associations. Backend creation also accepts an invoice association, validated against the customer. Existing customer records, staff accounts, CRM teams, permissions, catalogue IDs, orders, storage and notification delivery records are reused.

Catalogue edits persist `follow_up` rules in the existing product metadata, under its existing version/access checks. Checkout exposes per-line overrides and a registered customer selector. Follow-ups and audit activities are inserted inside the existing successful POS order transaction. A failed creation rolls back the order transaction. A stable checkout key plus tenant serialization allows an identical checkout retry to return the original order without issuing stock or follow-ups twice.

Follow-ups link to the precise order line. Completed recurring commitments create one next occurrence and retain the originating line. Rescheduling preserves the original timestamp and reason. Cancelled orders cancel open commitments unless the rule retains them. Fully refunded sale lines apply the same rule, including subsequent recurring commitments. Partial line refunds retain the commitment until the whole line is returned.

## Persistence and APIs

Migration: `backend/alembic_postgresql/versions/pg_20261103_064_follow_ups.py`, following `pg_20261103_063_crm_features`.

New tables:

- `service_follow_ups`: tenant, customer, catalogue, transaction/line, optional CRM and invoice associations, employee/team, timezone, schedule, status, priority and configuration; unique tenant/source key and indexed references/dates.
- `service_follow_up_activities`: employee, action, original/new values, reasons and timestamp.
- `service_follow_up_reminders`: unique occurrence/recipient/phase receipt, delivery state, attempt history, backoff and notification reference.
- `service_follow_up_attachments`: protected storage reference, uploader and history.
- `service_follow_up_preferences`: organization/user reminder and escalation preferences.

Development's existing SRM schema compatibility helper creates missing new tables. Production should apply the Alembic migration before serving the updated API. No production database migration or deployment was performed in this session.

Shared `/api/v1/follow-ups` endpoints provide create, paginated directory, statistics, staff/customer/team options, details, audited actions, private attachments, personal preferences, searchable permitted CRM associations, and the shared SQL grid adapter. The grid reuses the suite's validated filter/sort/group primitives and its existing resize, reorder, multi-sort, saved-view, selection and paging components. CSV/clipboard export supports filtered or selected records, with an explicit 20,000-record ceiling. Saved grid layouts remain browser-local, consistent with the existing grid.

All business rows remain branch-private. Customer/catalogue/source links are checked within the current permissions. Employees must be active and in the same tenant; teams must be active and accessible. Personal reminder preferences are branch-independent configuration scoped to the current organization and user. Existing organization and branch middleware remains active.

## Scheduling and reminders

Long-running backends start a one-minute polling worker. Serverless deployments have a five-minute Vercel cron entry for `/api/v1/internal/service-follow-up-reminders`, protected by the existing `CRON_SECRET` bearer convention. The existing protected general cron also invokes dispatch. Deploying the configuration and providing scheduler credentials are required for hosted execution.

The scheduler reads persisted commitments even when browsers are closed. Each due/overdue phase has a unique receipt, preventing repeated delivery. Notification creation and receipt updates are transactional; row locks support concurrent PostgreSQL workers. Failed attempts retain timestamp/error-class history and exponential retry delay capped at one hour. Successful delivery writes the existing in-app notification and delivery-log records. Employee preferences control reminders and escalation alerts. No external email or WhatsApp messages are sent automatically.

Dates must include an offset; the configured IANA zone governs local-date status and calendar-day interval calculations. The form translates selected-zone wall-clock dates into instants and rejects nonexistent DST times. Purchase date is the default only for a purchase-reference rule. Delivery/completion rules require their explicit reference. The tested November 3 + 45 days example produces December 18, 2026.

## Verification

- Focused backend workflow and catalogue migration compatibility tests: **15 passed**. Sources: see `backend/tests/test_service_follow_ups.py` and `test_pos_catalog_migration.py`.
- HTTP coverage includes actual POS retry, shared directory creation/completion, cross-branch denial, attachment upload/download protection and preferences.
- Scheduling coverage includes 45 days, custom dates, explicit references, DST, recurrence, preserved reschedule history, tenant link denial, duplicate reminder prevention, failed delivery history/retry and disabled employee reminders.
- Grid tests exercise filtering, sorting/grouping and bounded pages.
- `qa/service_follow_ups_browser.cjs` passes dashboard creation, shared directory rendering, POS category visibility, service tab filtering and mobile layout checks. Browser API responses are controlled fixtures; these checks are not a live-database browser E2E certification.
- TypeScript checking and Vite production build passed during implementation. Build reports existing large-chunk/mixed-import warnings.
- Broader catalogue/POS suites were attempted. Some fixtures were rejected by the current destination-branch or module-membership requirements (403), so those suites are not reported as passing.

Screenshots and browser results are under `docs/qa/service-follow-ups/`.

## Remaining limits

The requested scope is broader than this implementation. Existing legacy CRM lead-task follow-ups have not been migrated into the new service commitment directory. Dedicated follow-up badges in every customer/order grid, a full customer transaction/interaction aggregate, and separate lead-only scheduling without a customer record remain unfinished. The dashboard's Conversion Rate currently measures completion share rather than sales conversion outcomes. Calendar events are explicitly bounded to the current directory page and use the device timezone for display; selected-zone scheduling is supported by the forms. The calendar does not offer hour-slot drag positioning. Package browsing supports existing package-type inventory records; the shared catalogue editor still creates products and services.

No production PostgreSQL concurrency run, hosted cron execution, deployed migration, or live payment-provider E2E test was performed. External email/WhatsApp automation remains intentionally unconfigured.
