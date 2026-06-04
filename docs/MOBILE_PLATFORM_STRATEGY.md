# Mobile Platform Strategy

Date: 2026-06-04

## Vision

Mobile should be the action layer of the suite: approve, punch, visit, update, collect, upload, and respond. Desktop remains the planning and analysis layer; mobile handles time-sensitive work.

## App Strategy

| App | Audience | Primary Jobs |
|---|---|---|
| Business Suite Mobile | Managers/executives | Approvals, dashboards, alerts, customer/project/employee lookup |
| Sales Mobile | Sales reps/field teams | Leads, visits, calls, quotes, follow-ups, offline customer notes |
| Employee ESS | All employees | Attendance, leave, payslips, documents, helpdesk, announcements |
| Project Field App | PMs/site/team leads | Task updates, site progress, photos, timesheets, risks, client approvals |

## Offline Mode

| Area | Offline Capability |
|---|---|
| CRM | View assigned leads/accounts, add notes, log calls, capture visit, draft quote request |
| PMS | View tasks, update status, add time, upload queued photos/documents, site diary |
| HRMS | Attendance fallback, leave draft, payslip/document cache |
| Approvals | Queue approve/reject/comment with conflict resolution |

## Push Notifications

| Notification | Target |
|---|---|
| Approval due | Manager/CFO/HR/project director |
| Lead assigned/no follow-up | Sales rep/manager |
| Project risk/milestone slip | PM/project director/COO |
| Missing punch/payroll blocker | Employee/manager/HR |
| Invoice overdue/payment received | Finance/sales |
| AI daily digest | Executives/managers |

## Mobile Priority Workflows

1. One-tap approval with evidence summary.
2. Attendance punch with geo/device/photo policy options.
3. Field sales visit route, check-in, note, follow-up, quote request.
4. Project task/time update with offline sync.
5. Site/photo/document upload with metadata.
6. Employee leave, payslip, helpdesk, document request.
7. Executive daily digest and drilldown.
8. WhatsApp-friendly reminders and self-service commands.

## Architecture Requirements

| Requirement | Notes |
|---|---|
| Offline-first cache | Per-user scoped data, encrypted local storage, sync queue |
| Conflict resolution | Last-write policy plus review queue for sensitive records |
| Push service | Template, preference, digest, escalation support |
| Device policy | Optional geo, IP, device binding, biometric unlock |
| Mobile audit | Track action source, device, location where applicable |

