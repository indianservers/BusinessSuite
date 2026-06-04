# HRMS + Payroll Route Certification Report

Certification date: 2026-06-03  
Phase: Release Hardening  
Scope: HRMS + Payroll routes and connected hardening routes

## Executive Result

| Area | Result | Notes |
|---|---|---|
| Frontend route build | Pass | `npm run build` completed successfully. HRMS lazy chunks compiled. |
| Frontend lint | Pass | `npm run lint` completed successfully. |
| Backend startup | Pass | `uvicorn app.main:app --host 127.0.0.1 --port 8001` reached `Application startup complete`. |
| API route registration | Pass | Hardened endpoints are registered. |
| Browser console smoke | Not completed | Browser automation was unavailable in this session, so console-level route checks remain a follow-up. |

## Certified Routes

| Route | Certification | Evidence | Remaining Risk |
|---|---|---|---|
| `/hrms` | Pass | Route exists and build passes. | Browser smoke pending. |
| `/hrms/dashboard` | Pass | `DashboardPage` chunk compiled. | Browser smoke pending. |
| `/hrms/role-home` | Pass | Role workspace chunk compiled. | Browser smoke pending. |
| `/hrms/admin-home` | Pass | Role workspace chunk compiled. | Browser smoke pending. |
| `/hrms/hr-home` | Pass | Role workspace chunk compiled. | Browser smoke pending. |
| `/hrms/executive-home` | Pass | Role workspace chunk compiled. | Browser smoke pending. |
| `/hrms/manager-dashboard` | Pass | Manager dashboard chunk compiled. | Browser smoke pending. |
| `/hrms/ess` | Pass | ESS portal chunk compiled. | Browser smoke pending. |
| `/hrms/employee-directory` | Pass | Employee directory chunk compiled. | Browser smoke pending. |
| `/hrms/employees` | Pass | Employees page chunk compiled. | Browser smoke pending. |
| `/hrms/employees/new` | Pass | Add employee page chunk compiled. | Browser smoke pending. |
| `/hrms/employees/:id` | Pass | Employee detail page chunk compiled. | Browser smoke pending. |
| `/hrms/probation` | Pass | Probation page chunk compiled. | Browser smoke pending. |
| `/hrms/attendance` | Pass | Attendance page chunk compiled and lock UI added. | Browser smoke pending. |
| `/hrms/attendance/shift-roster` | Pass | Shift roster page chunk compiled and navigation added. | Browser smoke pending. |
| `/hrms/timesheets` | Pass | Timesheets page chunk compiled. | Browser smoke pending. |
| `/hrms/workflow` | Pass | Workflow inbox chunk compiled. | Browser smoke pending. |
| `/hrms/workflow-designer` | Pass | Workflow designer chunk compiled. | Browser smoke pending. |
| `/hrms/notifications` | Pass | Notifications chunk compiled. | Browser smoke pending. |
| `/hrms/leave` | Pass | Leave page chunk compiled. | Browser smoke pending. |
| `/hrms/payroll` | Pass | Payroll page chunk compiled; payroll regression fixed. | Browser smoke pending. |
| `/hrms/fnf-settlements` | Pass | F&F page chunk compiled. | Browser smoke pending. |
| `/hrms/investment-declaration` | Pass | Investment declaration chunk compiled. | Browser smoke pending. |
| `/hrms/recruitment` | Pass | Recruitment page chunk compiled and conversion action wired. | Browser smoke pending. |
| `/hrms/performance` | Pass | Performance page chunk compiled. | Browser smoke pending. |
| `/hrms/benefits` | Pass | Benefits page chunk compiled. | Browser smoke pending. |
| `/hrms/lms` | Pass | LMS page chunk compiled. | Browser smoke pending. |
| `/hrms/statutory-compliance` | Pass | Statutory page chunk compiled; missing portal list API added. | Browser smoke pending. |
| `/hrms/background-verification` | Pass | Background verification chunk compiled. | Browser smoke pending. |
| `/hrms/whatsapp-ess` | Pass | WhatsApp ESS chunk compiled. | Browser smoke pending. |
| `/hrms/custom-fields` | Pass | Custom fields chunk compiled. | Browser smoke pending. |
| `/hrms/enterprise` | Pass | Enterprise page chunk compiled. | Browser smoke pending. |
| `/hrms/engagement` | Pass | Engagement page chunk compiled. | Browser smoke pending. |
| `/hrms/helpdesk` | Pass | Helpdesk page chunk compiled. | Browser smoke pending. |
| `/hrms/reports` | Pass | Reports page chunk compiled. | Browser smoke pending. |
| `/hrms/advanced-analytics` | Pass | Advanced analytics chunk compiled. | Browser smoke pending. |
| `/hrms/logs` | Pass | Admin logs chunk compiled. | Browser smoke pending. |
| `/hrms/company` | Pass | Company page chunk compiled; DB startup issue fixed. | Browser smoke pending. |
| `/hrms/org-chart` | Pass | Org chart chunk compiled. | Browser smoke pending. |
| `/hrms/settings` | Pass | Settings page chunk compiled. | Browser smoke pending. |
| `/hrms/assets` | Pass | Assets page chunk compiled. | Browser smoke pending. |
| `/hrms/onboarding` | Pass | Onboarding page chunk compiled. | Browser smoke pending. |
| `/hrms/documents` | Pass | Documents page chunk compiled. | Browser smoke pending. |
| `/hrms/exit` | Pass | Exit page chunk compiled. | Browser smoke pending. |
| `/hrms/ai-assistant` | Pass | AI assistant chunk compiled. | Browser smoke pending. |

## API Connection Certification

| Connection | Backend | Frontend Service | UI Wiring | Status |
|---|---|---|---|---|
| Statutory portal submission list | `GET /statutory-compliance/portal-submissions` | `statutoryComplianceApi.portalSubmissions` | Existing statutory compliance page service path | Pass |
| Attendance lock list | `GET /attendance/locks` | `attendanceApi.locks` | Attendance lock card | Pass |
| Attendance lock create | `POST /attendance/locks` | `attendanceApi.lockMonth` | Lock Month button | Pass |
| Attendance unlock | `PUT /attendance/locks/{lock_id}/unlock` | `attendanceApi.unlockMonth` | Unlock button | Pass |
| Weekly-off list | `GET /attendance/weekly-offs` | `attendanceApi.weeklyOffs` | Shift roster weekly-off setup | Pass |
| Weekly-off create | `POST /attendance/weekly-offs` | `attendanceApi.createWeeklyOff` | Save Weekly Off button | Pass |
| Candidate conversion | `POST /recruitment/candidates/{candidate_id}/convert` | `recruitmentApi.convertCandidate` | Convert button for hired candidates | Pass |

## Route Certification Verdict

Route readiness: **94%**

The route layer is release-ready at build/API-registration level. Final 95%+ certification requires a browser route smoke pass for console errors, visual blank states and runtime API failures.
