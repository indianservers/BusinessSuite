# CRM relationship follow-ups redesign

Implemented at `/crm/customer-follow-ups` using the existing SharedDataGrid and growth APIs.

- Compact header and real filtered KPI counts; scoped record, owner, offering, date, and status filters.
- Server-side grid filters, sorting and pagination; column preferences and saved view context; CSV/clipboard exports.
- Inline relationship details, activity/history, notes, scoped file references, reviewed messaging, and canonical lead conversion.
- Follow-up creation/rescheduling/completion, assignment, priority, notes, next action, offering context, and optional in-app reminders.
- Bulk schedule/assignment with per-record authorization, explicit partial results, and idempotent retries.
- Reminder delivery uses the existing protected CRM scheduler. A running scheduler is required; saving does not deliver external messages.
- Mobile cards and full-screen details/editor.

Validation: 11 CRM growth tests passed; TypeScript no-emit check passed. Browser checks covered super-admin login, Main Branch data, server-side search, relationship panel, editor, and a saved local verification follow-up. Desktop/laptop and mobile layouts were inspected. Local dataset can change while other development tasks update shared contacts.

CSV and clipboard are supported export formats for this adapter. XLSX/PDF report an explicit unsupported-format error. File links open the existing file record view.
