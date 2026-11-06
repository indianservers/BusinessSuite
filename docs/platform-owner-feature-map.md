# Local Platform Owner portal: 60 practical features

The user requested useful owner workflows without VPN restrictions, mandatory
MFA, passkeys or elaborate security gates. This is the revised implementation
map. The owner portal is rooted at `/platform`, mounts a separate React app,
uses only `platformApi`, and authenticates against `indian_servers_platform`.
Client App Super Admins continue to use the business application and database.

## Owner workspace

1. Independent platform login and landing page — `PlatformApp.tsx`; platform JWT issuer, audience, signing key and session table.
2. Owner overview — `Reports.tsx`, `/platform/reports`; real signup and customer counts.
3. Owner profile and workspace preferences — `/platform/profile`; display name, default page and row density.
4. Device sessions and individual/all-other-session sign-out — `/platform/sessions` and `/sessions/revoke`.
5. Configurable idle timeout — server session checks and client inactivity timer.
6. Owner notification inbox — new signups, new devices, overdue reviews and scheduled reports; mark read.
7. Global signup/customer search — `/platform/search`, with staff assignment scope applied.
8. Owner password reset — expiring private local reset links; no customer password endpoint reused.
9. Favorite navigation — staff preferences persist favorite owner pages and place them first.
10. Login history — successful/failed attempts and device details; personal view or owner-wide view.

## Team and collaboration

11. Owner, reviewer, sales, support, billing and analyst roles — `service.py`.
12. Individual action restrictions within each role — server-enforced permission subsets.
13. Staff access reviews and account disabling — team page; active last owner protected.
14. Named staff invitations — expiring one-use private activation links and local outbox previews.
15. Platform-only activity log — actor, action, reason and before/after changes; customer actions are not merged into this log.
16. Assignment-scoped staff visibility — signup, customer, duplicate, search and linked record queries.
17. Permission-checked CSV export — formula-safe cells and an export audit event.
18. Team tasks and follow-ups — assignment, due date, priority, details, edit, complete/reopen and due-date view.
19. Customer-approved support requests — expiring approval/decline links; account configuration and aggregate diagnostics only, no impersonation.
20. Scoped integration keys — read/report/intake scopes, expiry, one-time display and revocation; cannot call owner-session controls.

## Signup management

21. Complete signup workspace — contact information, consent, requested apps, duplicate hints, history and provisioning records.
22. Manual lead/signup creation — company/individual type, source, campaign, tags and consent evidence.
23. Editable pending applications — validated contact/app fields, version checks and before/after history.
24. Advanced filters — status, applicant type, dates, assignee/unassigned, app, priority, source and search.
25. Personal/shared saved views — shared view creation restricted to owners; archive views from Tasks.
26. Possible duplicate detection — matching company, phone or email domain; only permitted matches are exposed.
27. Reviewer/sales assignment — single and bulk updates, with history.
28. Bulk changes with preview — visible proposed records/errors, required reason, version validation and atomic commit.
29. Archive and restore — prior status retained; approved accounts are not accidentally reprovisioned.
30. Controlled personal-data purge — archived non-customer requests only, after retention and without legal hold; associated contact/history values are redacted while decision IDs remain.

## Review and onboarding

31. Review lifecycle — pending, under review, awaiting applicant, approved, rejected, withdrawn and archived.
32. Practical approval checklist — identity, duplicate and app checks; configurable requirement.
33. Trial configuration — allowed apps, days, seats and storage allowance saved to both the owner contract and customer subscription.
34. Reusable reason templates — create/edit/archive wording and select it during review.
35. Request more information — private correction link, original values retained in the audit history, single-use response.
36. Provisioning progress — completed steps for company, admin, apps and local invitation; errors remain visible.
37. Safe retry/reconciliation — customer transaction receipt prevents duplicate workspaces after an owner commit failure; recovered attempts are marked recovered.
38. Invitation lifecycle — local preparation, expiry, acceptance on usage sync, revoke and replacement links.
39. Business-hour review SLA — timezone, weekdays and working hours, overdue indicators and idempotent escalation notifications.
40. Private applicant status — capability link exposes one request only and permits withdrawal before final review.

## Customer and commercial lifecycle

41. Customer directory — approved businesses, primary admin, status, trial dates, plans and aggregate usage.
42. Verified admin transfer — both current and new email holders confirm; the business identity remains company-scoped and sessions are revoked.
43. Trial expiry workflow — local reminders and customer subscription access restriction after the configured deadline/grace period.
44. Trial extensions — reason, end-date calculation and customer subscription synchronization.
45. Trial conversion — apply a catalogue plan to the existing workspace without recreating company or user records.
46. Plan changes and history — immediate or future-effective upgrades/downgrades; current usage validated before lower limits apply.
47. Seat/storage entitlements — compare allowances to usage; business runtime enforces its own subscription without accessing the owner database.
48. Suspend and reactivate — required reason and restoration of the preceding lifecycle state.
49. Offboarding coordination — cancellation, owner configuration export, retention date and a follow-up review task; ERP records are preserved.
50. Customer configuration snapshots — create and restore contract/allowance snapshots after usage checks; these are explicitly not ERP-data backups.

## Statistics and insights

51. Signup overview — requests, companies, individuals and decision states for a selected submission cohort.
52. Acquisition trends — daily submissions, preset/custom dates and previous-period comparison.
53. Approval/rejection rates — denominators exclude undecided requests.
54. Review turnaround — median and 90th percentile in configured business hours.
55. Signup-to-contract funnel — distinct submissions, approvals, invited requests, activated tenants and converted contracts; resends do not double-count applications.
56. Application demand — requested app counts; multi-app requests are represented honestly.
57. Source and campaign attribution — captured on public/manual signups and grouped in reports.
58. Customer engagement summaries — active seats, last-30-day logins, tracked storage and activation state; no ERP record payloads shown.
59. Commercial reporting — monthly active contract value, manually recorded offline receipts, cancellations and paid-cohort churn; currencies never silently combined.
60. Operational reporting — failed provisioning attempts, overdue queues, invitation states and owner-login failures; JSON exports and scheduled local report snapshots.

## Local operations and limits

- Schema migration: `backend/venv/Scripts/python -m alembic -c alembic_platform.ini upgrade head`, from `backend`.
- The development-only due-work runner runs every five minutes against local PostgreSQL. “Run due checks now” is available in Operations.
- Messages remain in the local preview outbox. A preview check is never labelled as real email delivery. Business activation outbox entries created by this flow are held locally.
- Customer configuration export/snapshots intentionally exclude ERP records and credentials. Offboarding does not silently delete business data.
- Actual email providers, payment gateways, VPNs, passkeys, mandatory MFA and customer impersonation are not enabled.
- No deployments, remote databases, pushes or external sends were performed.

## Validation

`backend/tests/test_platform_portal.py` exercises role/identity separation,
versioned edits, assignment scopes, bulk atomicity, checklist enforcement,
private links, retention/holds, tasks, schedules, contracts, payments, snapshots,
staff activation, session revocation, integration scope boundaries, support
consent, two-party admin transfer and due plan changes. Existing public signup
and company isolation tests remain part of the focused validation suite.
