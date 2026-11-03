# Local super-admin follow-up verification

Verified on 3–4 November 2026, using Main Branch and explicitly labelled Followup QA records.

Checks completed:
- Relationship type, search, scope, owner, catalog offering, status buckets, custom date range, advanced conditions, sorting and pagination.
- Shared grid column visibility, ordering, pinning, auto-fit, saved view creation/restoration and refresh.
- Bulk scheduling and reassignment; partial failures, retry safety and changed-payload request IDs.
- Existing follow-up rescheduling, channel/priority/owner edits, completion with an immediate next follow-up.
- Automatic local reminder dispatch, exactly one fresh notification, branch-visible delivery receipt and contextual relationship destination.
- Overview, Activity, Notes and History tabs; saved notes; linked attachment upload/link/download.
- New Follow-up relationship search/selection/cancel; reviewed messaging navigation; full profile, worklist and product audience navigation.
- CSV, Excel, PDF and clipboard exports, including real browser downloads.
- Dedicated QA lead conversion, with historical follow-up retained.

Fixes include local worker dispatch, reminder branch ownership and receipts, notification destinations, per-record bulk savepoints, partial retry handling, all export formats, attachment download links, plural activity event filtering, custom datetime inputs, and PostgreSQL nullable date types in mixed-record queries. CRM record refreshes preserve an open editor.

Automated validation: 17 CRM growth tests passed. TypeScript no-emit checks passed during verification. Export tests verify binary Excel/PDF output, formula-safe spreadsheet cells and access checks. Reminder tests verify visibility through the authenticated notification API and retry deduplication.

QA contacts A/B/C and one converted QA lead remain labelled in the local database for review. The attachment is followup-qa.txt. Messaging was checked through recipient preview.
