# Lead management implementation

Updated 25 October 2026. This document describes the repository implementation, not a production deployment or a claim of feature parity with commercial CRMs.

## Where to use it

- **CRM → Leads** (`/crm/leads`) opens the new workbench.
- `/crm/leads/classic` retains the earlier workspace.
- Click a name for the detail drawer; the full record remains available at `/crm/leads/:id`.
- Administrators use **Lead workflow settings** for stages, assignments, sequences, workflows and website capture.
- **Import Excel** accepts `.xlsx` and UTF-8 `.csv`. **Export Excel** downloads a real `.xlsx` workbook.

## Functional coverage of the 20 requested features

1. **Configurable stages:** Keep the five system stages, add custom stages, choose allowed transitions and required business/contact fields. Conversion uses a dedicated operation. Saved process requirements also guard classic creation, updates, qualification and imports.
2. **Stage history:** Actor, timestamp, previous/next stages and measured hours in the previous stage are recorded. Earlier history is not fabricated or backfilled.
3. **Automatic assignment:** Round-robin, fewest active leads, first-match source/location/industry/territory/product rules, and the existing territory engine. Owners are checked against the organization and assignment permissions. Product rules match recorded interests. The creation form and Excel transfer keep existing territory/routing defaults; record interests can be maintained in qualification.
4. **Response SLAs:** Configurable first-response deadline, visible breach indicators, manual evaluation and bounded automatic escalation through the existing protected `/api/v1/internal/cron` entry point. Scheduled notifications go to the valid owner and configured administrator when distinct. Actual recurrence depends on deployment cron configuration.
5. **Follow-up sequences:** Configurable timed call/email/meeting/general tasks, enrollment, replacement, cancellation, completion and next-follow-up advancement. Logging a response or booking a meeting stops pending sequence tasks. Email steps are manual sending tasks; see the integration gaps below.
6. **Website capture:** Revocable public enquiry form and embeddable HTML with name, email, company, requirement, source, consent timestamp, duplicate handling and responsible owner. Link rotation invalidates old forms. The database enforces a tenant intake cap of 100 accepted enquiries per hour, including repeat enquiries. Repeat submissions attach to the existing lead and reopen its enquiry queue entry. Existing website-form tools remain linked.
7. **Enquiry inbox:** A work queue includes unassigned records and untouched enquiries from supported recorded channels. Website submissions enter it directly. Automatic mailbox and messaging-provider ingestion is not certified by this change.
8. **Duplicate prevention:** Normalized email and phone checks during creation, updates and imports, including duplicates within a workbook. The existing duplicate review/merge tool remains linked. Duplicate responses do not reveal hidden record identifiers.
9. **Qualification:** Business need, budget, decision-maker and buying timeline; configurable requirements are enforced before a stage change.
10. **Explainable scoring:** Existing active scoring rules are shown with individual contributions. Manual overrides require a reason and a score between 0 and 100. The current automatic calculation is distinguished from a stored manual score.
11. **Lead aging:** Untouched, overdue, inactive, archived and review-due queues, plus a bounded priority work queue.
12. **Suggested next actions:** Deterministic recommendations based on first contact, response deadline, follow-up, inactivity and qualification. These are rule-based recommendations, not predictive AI.
13. **Communication history:** Recorded call/email/meeting outcomes, notes, activity history and links to the existing communications tool. Logging an outcome does not send an external message.
14. **Meeting scheduling:** Schedule a 30-minute meeting against the assigned owner's BusinessSuite calendar; generate a private, single-use booking link valid for 30 days. Bookings check overlaps, notify the owner and attach to the lead. External-calendar availability is a remaining integration gap.
15. **Product/service interests:** Multiple named interests, individual estimated values and requirement notes on each lead.
16. **Lost-lead analysis:** Required loss reason, competitor details and reason breakdowns. The drawer offers structured reasons and preserves existing custom reasons.
17. **Reactivation:** Archive with a reason, set a review date, review due records, restore them and move Lost records back to New through the configured process.
18. **Safe conversion:** Review matching visible contacts/companies, explicitly reuse an existing contact, require qualification and provide links to the resulting customer/deal records. Existing-contact reuse was wired into the original conversion handler as well.
19. **Analytics:** Current stage/source/loss counts, recorded stage progression, measured time before stage exits, qualification/conversion by source and owner, and sampled first-response averages. The UI labels snapshot counts separately from historical progression and reports incomplete legacy measurements honestly.
20. **Workflow automation:** Enabled rules on creation, stage change and recorded response can create scheduled tasks, notify owners or assign a validated owner. This is a focused rule editor; a general branching process designer remains a gap.

## The 10 UI enhancements

1. Table, Kanban-style board and compact layouts. Board counts refer to the current page.
2. Consistent text-labeled stage badges with differentiated colors.
3. Useful default columns for company, owner, score, follow-up and next action; configurable visibility.
4. Summary header showing stage, company, suggested action and contact shortcuts.
5. A detail drawer that preserves the list behind it.
6. A typed, chronological activity and stage-change timeline.
7. Clear overdue, due-today and upcoming follow-up labels.
8. Separate overview, qualification, activities, score and history sections.
9. Responsive controls, scrollable queues/tables and a full-width mobile drawer.
10. Loading, empty, validation, failure and successful-save states.

## The 10 UX enhancements

1. Name-first quick capture, with an in-session draft retained after failures or closing.
2. Guided stage changes: failed inline transitions open the intended stage and qualification fields together; loss transitions request the reason before saving.
3. A My day queue combining due follow-ups, untouched assigned leads and priority signals.
4. One operation to save an interaction outcome, its response status and the next follow-up task.
5. Inline stage and owner editing in the table.
6. Named saved views and column preferences isolated by user in the browser session.
7. Bulk previews before atomic assignment, stage, archive or restore operations.
8. URL-backed filters, selected drawer record, layout and pagination; opening/closing the drawer retains list context.
9. Explicit unsaved/saving/saved feedback, retained form input after validation failures and version checks to reject stale edits.
10. Conversion preview with duplicate reuse and links to the resulting records.

## Excel behavior and limits

- Download the template, populate the **Leads** sheet, upload, review row errors and duplicate skips, then explicitly import.
- Preview performs no lead writes. Commit revalidates all rows. A validation error prevents the batch from being imported.
- Imports accept at most 3 MB, 5,000 data rows and 40 columns. `.xlsx` decompression is capped. Legacy `.xls` should be saved as `.xlsx` first.
- Supported business fields include name, company, email, phone/calling code, source, status, value, next follow-up, location, industry, notes, qualification, loss details and archive/review details.
- Phone numbers follow the suite's shared contract: exactly ten national digits and a separate supported country calling code. Excel numeric phone cells are converted to their decimal text representation; missing leading zeroes are not guessed.
- Excel formulas are rejected on import. Export explicitly writes strings as text, including values beginning with `=`, preserving phone numbers and preventing spreadsheet formula execution.
- Converted leads require a real conversion operation; importing a status cannot manufacture linked customer/deal records. Lost imports must include `loss_reason`. Configured qualification requirements also apply to imports.
- Exports honor tenant and record visibility. Export all matches the search/stage/owner filters and includes archived records; it does not imply the current work queue. Selected export is limited to 200 selected records. Over 5,000 matches requires narrower filters instead of silently dropping records.
- Export includes supported business and qualification fields, not a full database backup, attachments, product-interest collections or audit history.
- Templates use frozen headers, readable widths, header styling and Excel filters.

## Operations and verification

- Final checks: **52 backend tests passed on PostgreSQL**, **12 browser tests passed**, and the production frontend build passed. The build emits existing third-party Rollup annotation warnings. Browser screenshots were visually checked on desktop and mobile.
- New migration: `pg_20261025_022_leads`, following `pg_20261025_021_contact_codes`.
- Install backend requirements, including `openpyxl==3.1.5`, and apply the reviewed Alembic migration chain before running the new APIs against an existing database.
- Local development data was not changed. Its migration version was older than the pending repository chain; validation uses a separate disposable database.
- Scheduled SLA escalation reuses the existing authenticated cron endpoint. No outside scheduler, mailbox, messaging account or customer communication was activated during implementation.
- Backend coverage: process enforcement, stale-edit rejection, duplicates, transfer validation and safety, batch rollback, tenant/record visibility, qualification/conversion, response cancellation, task advancement, public capture, booking conflicts, analytics, reactivation and scheduled alert idempotence.
- Browser coverage: views/queues, capture, inline edits, bulk preview/apply, Excel preview/import/download, qualification/outcomes, settings, read-only controls, responsive layout, and the existing lead/conversion screens.
- Desktop/mobile screenshots are under `docs/qa/lead-management/`. Browser tests use mocked API responses; real backend behavior is tested separately.

## Remaining gaps

See [competitor benchmark and prioritized gaps](lead-management-competitive-gaps.md). The integration and scale gaps there remain open; the presence of a UI or scheduled task is not proof that a third-party service is connected.
