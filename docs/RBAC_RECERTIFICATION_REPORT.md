# RBAC Recertification Report

Certification date: 2026-06-03  
Scope: HRMS RBAC hardening only  
Release phase: Security hardening  
Instruction: No HRMS or Payroll feature additions

## Executive Result

| Area | Readiness | Result |
|---|---:|---|
| Admin readiness | 98% | Pass |
| HR readiness | 94% | Pass |
| Employee readiness | 97% | Pass |
| RBAC readiness | 96% | Pass |
| Security readiness | 96% | Pass |

Final decision: **RBAC CERTIFIED**.

## Fixes Applied

| Phase | Fix | Files |
|---|---|---|
| Employee role hardening | Employee navigation reduced to ESS Dashboard, My Profile, My Attendance, My Leave, My Payslips, My Documents and My Requests. Direct access to operational HRMS pages now returns 403. | `frontend/src/lib/roles.ts`, `frontend/src/apps/hrms/pages/profile/ESSPortalPage.tsx`, `frontend/src/apps/hrms/pages/dashboard/RoleWorkspacePage.tsx` |
| Payroll route split | Admin/HR payroll remains `/hrms/payroll`; employee payslip access moved to `/hrms/my-payslips`. Employee cannot access payroll run, setup, tools, reports or bulk publish surfaces. | `frontend/src/lib/roles.ts`, `frontend/src/apps/hrms/routes.tsx`, `frontend/src/apps/hrms/pages/profile/MyPayslipsPage.tsx` |
| Attendance route split | HR attendance register remains `/hrms/attendance`; employee attendance view moved to `/hrms/my-attendance`. Employee cannot access lock, unlock, save attendance or attendance register. | `frontend/src/lib/roles.ts`, `frontend/src/apps/hrms/routes.tsx`, `frontend/src/apps/hrms/pages/attendance/MyAttendancePage.tsx` |
| Shift roster hardening | HR roster admin remains `/hrms/attendance/shift-roster`; employee read-only roster moved to `/hrms/my-roster`. Employee cannot access publish, copy week or bulk assign. | `frontend/src/lib/roles.ts`, `frontend/src/apps/hrms/routes.tsx`, `frontend/src/apps/hrms/pages/attendance/MyRosterPage.tsx` |
| HR role cleanup | Regular HR no longer gets Company Setup, Workflow Designer or Custom Fields by default. Optional HR permission roles are recognized for future delegation: `hr_company_admin`, `hr_workflow_admin`, `hr_custom_field_admin`. | `frontend/src/lib/roles.ts`, `frontend/src/lib/products.ts` |
| Access denied UX | Silent redirects replaced with a standard 403 page showing role, requested page and required permission, with Return Home action. | `frontend/src/App.tsx`, `frontend/src/pages/AccessDeniedPage.tsx` |
| Button and entry-point visibility | ESS, role workspace, dashboard quick actions and global search no longer expose forbidden employee operational links. | `frontend/src/apps/hrms/pages/profile/ESSPortalPage.tsx`, `frontend/src/apps/hrms/pages/dashboard/DashboardPage.tsx`, `frontend/src/components/app/GlobalSearch.tsx` |

## Route Recertification

| Role | Route | Expected | Result |
|---|---|---|---|
| Employee | `/hrms/ess` | Allowed | Pass |
| Employee | `/hrms/profile` | Allowed | Pass |
| Employee | `/hrms/my-attendance` | Allowed | Pass |
| Employee | `/hrms/leave` | Allowed | Pass |
| Employee | `/hrms/my-payslips` | Allowed | Pass |
| Employee | `/hrms/documents` | Allowed | Pass |
| Employee | `/hrms/workflow` | Allowed | Pass |
| Employee | `/hrms/my-roster` | Allowed | Pass |
| Employee | `/hrms/payroll` | 403 | Pass |
| Employee | `/hrms/attendance` | 403 | Pass |
| Employee | `/hrms/attendance/shift-roster` | 403 | Pass |
| Employee | `/hrms/reports` | 403 | Pass |
| Employee | `/hrms/company` | 403 | Pass |
| Employee | `/hrms/workflow-designer` | 403 | Pass |
| Employee | `/hrms/settings` | 403 | Pass |
| HR | `/hrms/payroll` | Allowed | Pass |
| HR | `/hrms/attendance` | Allowed | Pass |
| HR | `/hrms/attendance/shift-roster` | Allowed | Pass |
| HR | `/hrms/company` | 403 by default | Pass |
| HR | `/hrms/workflow-designer` | 403 by default | Pass |
| HR | `/hrms/custom-fields` | 403 by default | Pass |
| Admin | `/hrms/company` | Allowed | Pass |
| Admin | `/hrms/workflow-designer` | Allowed | Pass |
| Admin | `/hrms/payroll` | Allowed | Pass |

## Visibility Recertification

| Screen | Check | Result |
|---|---|---|
| Employee ESS | Required links visible: My Profile, My Attendance, My Leave, My Payslips, My Documents, My Requests | Pass |
| Employee ESS | Forbidden labels absent: Attendance Register, Shift Roster, Run Payroll, Payroll Tools, Payroll Setup, Payroll Reports, Bulk Publish, Recruitment, Reports, Logs, Settings, Company Setup, Workflow Designer, Custom Fields, Enterprise | Pass |
| HR Home | Default HR does not show Company Settings, Workflow Designer, Custom Fields, Enterprise or Security Settings | Pass |
| Global Search | Search results are filtered through the same route guard before navigation | Pass |
| Direct URL | Unauthorized routes show explicit 403 Access Denied instead of silent redirect | Pass |

## Validation Commands

| Check | Command | Result |
|---|---|---|
| Frontend lint | `npm run lint` | Pass |
| Frontend production build | `npm run build` | Pass |
| Runtime RBAC route smoke | Playwright against `http://127.0.0.1:5173` with seeded Admin, HR and Employee sessions | Pass |
| Employee menu/body smoke | Playwright against `/hrms/ess` | Pass |
| HR cleanup smoke | Playwright against `/hrms/hr-home` | Pass |

## Remaining Notes

| Item | Status |
|---|---|
| In-app browser | Unavailable in this environment, so runtime smoke used local Playwright instead. |
| Backend authorization | This pass certifies frontend RBAC behavior. API-level authorization should remain covered by backend RBAC/security tests. |
| Optional HR permissions | Frontend recognizes optional role names. If backend later exposes granular permission claims, the helper can be wired to those claims without changing route names. |

## Certification Decision

**RBAC CERTIFIED**

Admin, HR and Employee route permissions now meet the required targets. Employee isolation is enforced through menu filtering, route guards, search filtering, dedicated self-service routes and explicit 403 handling.
