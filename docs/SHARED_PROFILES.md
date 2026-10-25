# Shared employee, user and intern profiles

## Access

- Employees and HR: HRMS → Profile (`/hrms/profile`).
- HR management: `/hrms/profile-management`; Intern Applications also links to `/hrms/interns/profiles`.
- Employee detail: **Complete Profile** tab.
- Interns Hub: **Profile**, using the same editor through portal-specific APIs.
- Other Business Suite modules: the existing module Profile page now includes the shared editor.
- Existing account security, MFA and HR document tools remain at `/hrms/profile/security`.

## Form carryover and email connection

Approving an Interns Form retains its existing account/employee creation flow and seeds the shared profile from the approved application. Personal/contact information, guardian, academics, interests, skills, internship preferences, availability and professional links carry over. Application documents appear as document metadata. The Application tab retains the submitted values separately from later edits.

Previously approved applications are backfilled on the first authorized profile read. This preserves later employee edits. No database migration is required; additional values use the existing CommonProfile JSON storage.

For an existing user, HR can choose **Connect by email**, preview matching employee records, and confirm one. Matching is case-insensitive, limited to the same organization and HR scope, and cannot overwrite another account's employee link. A pending or rejected application cannot be bypassed through email matching. Email connection does not send mail or grant access. Existing account email and role changes remain in account administration.

## Editing and management

Profiles contain personal details, addresses, emergency contacts, academics, education, experience, skills, professional links, biography, preferences, photo, employment summary, documents and application history. Employment assignments are read-only here and retain existing HRMS management controls. Document entries are metadata; existing authorized document tools handle file access.

Employees and interns may directly edit professional information. Protected employee details create an existing HR profile-change request; the current record changes only after an authorized approval. HR can manage profiles within their established scope. Review buttons use the existing request review authorization.

The editor validates contact details, dates, URLs and collection ownership, preserves drafts on validation/conflict errors, prompts before abandoning edits, and rejects stale saves. Photo upload accepts validated JPEG/PNG files up to 3 MB, strips metadata and saves a private normalized image. Passwords, full identity numbers, upload tokens, payroll details and authentication secrets are excluded from application snapshots and profile APIs.

Common APIs are under `/api/v1/profiles`; intern sessions remain confined to `/api/v1/interns-hub/profile` and its photo endpoint. Organization and manager scope checks remain enforced.

## Verification

- SQLite: 21 tests covering shared profiles, application approval, profile change requests and Interns Hub.
- PostgreSQL: 18 tests covering shared profiles, profile change requests and Interns Hub, using a dedicated disposable test database.
- Browser: eight tests covering form carryover, editing, approvals, education records, email linkage, stale drafts, mobile layout and the separate intern portal.
- Main frontend and Interns Hub production builds.

Logs and screenshots are under `docs/qa/shared-profiles/`. The development database was not migrated or altered during verification.
