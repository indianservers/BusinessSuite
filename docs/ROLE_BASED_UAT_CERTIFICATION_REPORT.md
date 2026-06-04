# Role-Based UAT Certification Report - HRMS + Payroll

Certification date: 2026-06-03  
Scope: HRMS + Payroll role-based UI UAT  
Test perspective: Senior QA Lead, HR Director, Payroll Manager, Employee User  
Method: Browser UI login and navigation only. No code inspection was used before role testing.

## 1. Executive Verdict

| Area | Result | Reason |
|---|---|---|
| Admin UAT | PASS / Partial | Admin can access core HRMS, payroll, setup, reports, logs and platform menus. Some pages initially render with limited content but routes load. |
| HR UAT | PARTIAL | HR can access HR operations, employee, attendance, leave, payroll and recruitment. HR also sees broad platform/company/setup access that may be excessive depending on policy. |
| Employee UAT | FAIL | Employee can directly open operational Attendance, Shift Roster and Payroll pages. Sensitive action buttons are visible even when disabled or API-blocked. |
| Unauthorized access handling | FAIL | Blocked URLs often redirect silently to ESS/home instead of showing a clear Access Denied page. Employee payroll route is not blocked. |
| Button-level permission behavior | FAIL / Partial | Employee sees Lock Month, Publish Roster and Payroll viewer/bulk publish controls. Some are disabled or backend-blocked, but should be hidden or clearly denied. |
| Final RBAC decision | RBAC NOT CERTIFIED | Employee and HR permission boundaries require hardening before production sign-off. |

Final decision: **RBAC NOT CERTIFIED**.

## 2. Test Accounts Used

| Role | UI Login Result | Account |
|---|---|---|
| Admin | Success | `admin@aihrms.com` |
| HR User | Success | `hr@aihrms.com` |
| Employee User | Success | `employee@aihrms.com` |

## 3. Admin Access Matrix

Expected: Admin can access all HRMS and Payroll screens.

| Screen | View | Add | Edit | Delete | Approve | Export | Expected | Actual | Pass/Fail |
|---|---|---|---|---|---|---|---|---|---|
| Dashboard | Yes | N/A | N/A | N/A | N/A | N/A | Full admin dashboard | Route loads | Pass |
| Company / Organization Setup | Yes | Yes | Yes | Partial | N/A | N/A | Company, branch, department, designation setup visible | New Company and Save Company visible | Pass |
| Employees | Yes | Yes | Yes | Partial | N/A | Yes | Employee management visible | Add Employee and Export visible | Pass |
| Add Employee | Yes | Yes | N/A | N/A | N/A | N/A | Employee creation wizard visible | Wizard steps visible | Pass |
| Attendance Register | Yes | Yes | Yes | N/A | Lock/Unlock | N/A | Attendance operations visible | Lock Month, Unlock, Save controls visible | Pass |
| Shift Roster | Yes | Yes | Yes | N/A | Publish | N/A | Shift and weekly-off setup visible | Copy, bulk assign, publish controls visible | Pass |
| Leave | Yes | Yes | Yes | N/A | Yes | N/A | Leave administration visible | Route loads | Pass |
| Payroll | Yes | Yes | Yes | N/A | Yes | Yes | Full payroll setup/run/report access | Route loads | Pass |
| Recruitment | Yes | Yes | Yes | N/A | Partial | N/A | Jobs/candidates visible | Post Job, Job Openings, Candidates visible | Pass |
| Reports | Yes | N/A | N/A | N/A | N/A | Yes | Reports visible | Reports page visible | Pass |
| Audit Logs | Yes | N/A | N/A | N/A | N/A | Partial | Logs visible | Refresh, errors-only, field-audit controls visible | Pass |
| Settings / Security | Yes | Yes | Yes | Partial | N/A | N/A | System settings visible | Settings and user-role areas visible | Pass |
| Profile / Sessions | Yes | Partial | Partial | N/A | N/A | N/A | Admin profile visible | Profile route visible | Pass |

Admin readiness: **92%**.

## 4. HR Access Matrix

Expected: HR can operate employee, attendance, leave, recruitment and selected payroll workflows. HR should not automatically receive unrestricted platform/security permissions unless explicitly assigned.

| Screen | View | Add | Edit | Delete | Approve | Export | Expected | Actual | Pass/Fail |
|---|---|---|---|---|---|---|---|---|---|
| Dashboard | Yes | N/A | N/A | N/A | N/A | N/A | HR dashboard visible | Dashboard route loads | Pass |
| Employees | Yes | Yes | Yes | Restricted | N/A | Yes | HR can manage employee records | Add Employee and Export visible | Pass |
| Add Employee | Yes | Yes | N/A | N/A | N/A | N/A | HR can create employees | Employee wizard visible | Pass |
| Company Setup | Restricted | Restricted | Restricted | Restricted | N/A | N/A | Usually limited or admin-only | HR can open Company and sees New/Save/Add controls | Fail / Policy Risk |
| Attendance | Yes | Yes | Yes | N/A | Lock | N/A | HR can enter/import/lock attendance if assigned | Attendance route visible; Lock Month disabled but Unlock visible | Partial |
| Shift Roster | Yes | Yes | Yes | N/A | Publish | N/A | HR may manage roster | Publish Roster visible | Pass / Review |
| Leave | Yes | Yes | Yes | N/A | Yes | N/A | HR can approve/reject leave | Pending Approvals visible | Pass |
| Payroll | Yes | Inputs/Run if assigned | Restricted | N/A | Policy-dependent | Yes | Payroll access should be scoped | Setup Wizard, Run Payroll and Payroll Tools visible | Partial / High Risk |
| Recruitment | Yes | Yes | Yes | N/A | Partial | N/A | HR can manage recruitment | Post Job, Jobs and Candidates visible | Pass |
| Reports | Yes | N/A | N/A | N/A | N/A | Yes | HR reports visible | Reports visible | Pass |
| Audit Logs | Restricted | N/A | N/A | N/A | N/A | N/A | Usually admin/security only | Direct URL redirected to HR Home | Pass with UX Issue |
| Settings | Restricted | Restricted | Restricted | Restricted | N/A | N/A | Usually admin-only | Direct URL redirected to HR Home | Pass with UX Issue |
| Profile | Yes | Own fields | Own docs | N/A | N/A | N/A | HR own profile visible | Profile route visible | Pass |

HR readiness: **78%**.

## 5. Employee Access Matrix

Expected: Employee should access ESS, own profile, own attendance/leave, own payslips and own documents only. Employee must not access HR/Admin operational screens.

| Screen | View | Add | Edit | Delete | Approve | Export | Expected | Actual | Pass/Fail |
|---|---|---|---|---|---|---|---|---|---|
| ESS Dashboard | Yes | N/A | N/A | N/A | N/A | N/A | Employee home visible | ESS visible | Pass |
| Profile | Yes | Own allowed fields | Own allowed fields | N/A | N/A | N/A | Own profile only | Profile visible, change/doc buttons disabled until input | Pass / Partial |
| Employee Directory | Optional | No | No | No | No | No | Directory may be allowed if policy permits | Visible in employee menu | Review |
| Employee Master List | No | No | No | No | No | No | Must be blocked | Direct URL redirects to ESS | Partial - blocked but no denial message |
| Other Employee Profile | No | No | No | No | No | No | Must be denied | Direct `/hrms/employees/1` redirects to ESS | Partial - blocked but no denial message |
| Attendance | Own view / regularization only | Regularization | Own request only | No | No | No | No HR attendance register actions | Attendance page opens and shows Lock Month / Save controls | Fail |
| Shift Roster | Own roster only | No | No | No | No | No | Should not show roster admin page | Shift Roster page opens with Publish Roster visible; lock API returns 403 | Fail |
| Leave | Yes | Apply/cancel own | Own request | No | No | No | Employee leave self-service | Apply Leave visible | Pass |
| Payroll / Payslip | Own payslip only | No | No | No | No | Download own only | Must not show payroll operations | Payroll route opens; Payslip Viewer and Bulk publish visible | Fail |
| Recruitment | No | No | No | No | No | No | Must be blocked | Redirects to ESS | Partial - blocked but no denial message |
| Reports | No | No | No | No | No | No | Must be blocked | Redirects to ESS | Partial - blocked but no denial message |
| Logs | No | No | No | No | No | No | Must be blocked | Redirects to ESS | Partial - blocked but no denial message |
| Settings | No | No | No | No | No | No | Must be blocked | Redirects to ESS | Partial - blocked but no denial message |
| Documents | Own only | Own upload if allowed | Own metadata if allowed | No | No | Download own | Own documents only | Visible in employee menu | Pass / Needs record-level test |

Employee readiness: **58%**.

## 6. Menu Visibility Audit

### Admin

Admin menu visibility is broadly correct. Visible modules include:

Dashboard, Inbox, Workflow Designer, Notifications, Employees, Probation, Employee Directory, Attendance, Shift Roster, Timesheets, Leave, Payroll, Investment Declaration, F&F Settlement, Benefits, Recruitment, Performance, LMS, Engagement, Statutory Compliance, BGV, Helpdesk, Company, Org Chart, Settings, Logs, WhatsApp ESS, Custom Fields, Enterprise, Reports, Advanced Analytics, Onboarding, Documents, Assets, Exit and AI Assistant.

Result: **Pass**.

### HR User

HR menu includes expected HR operations, but also exposes broad platform-oriented screens:

| Menu | Expected | Actual | Result |
|---|---|---|---|
| Employees, Attendance, Leave, Recruitment | Visible | Visible | Pass |
| Payroll | Role-dependent | Visible with setup/run/tools controls | Review / Risk |
| Company | Usually restricted | Visible | Risk |
| Workflow Designer | Usually restricted | Visible | Risk |
| Custom Fields | Usually restricted | Visible | Risk |
| Reports | Visible | Visible | Pass |
| Logs / Settings | Hidden/direct blocked | Direct URL redirects to HR Home | Pass with UX Issue |

Result: **Partial**.

### Employee User

Employee menu is mostly ESS-oriented but still exposes operational pages:

| Menu | Expected | Actual | Result |
|---|---|---|---|
| ESS Portal | Visible | Visible | Pass |
| Profile | Visible | Visible | Pass |
| Leave | Visible | Visible | Pass |
| Payslip | Visible as own payslip only | Opens Payroll page with payroll heading | Fail |
| Attendance | Own attendance only | Opens full Attendance page with Lock Month / Save controls | Fail |
| Shift Roster | Own schedule only or hidden | Direct route opens roster admin page | Fail |
| Employee Directory | Policy-dependent | Visible | Review |

Result: **Fail**.

## 7. Button Permission Audit

| Role | Page | Buttons Observed | Expected | Result |
|---|---|---|---|---|
| Admin | Company | New Company, Save Company | Allowed | Pass |
| Admin | Employees | Export, Add Employee | Allowed | Pass |
| Admin | Attendance | Lock Month, Unlock, Save controls | Allowed | Pass |
| Admin | Shift Roster | Copy Previous Week, Bulk Assign, Publish Roster | Allowed | Pass |
| Admin | Recruitment | Post Job, Job Openings, Candidates | Allowed | Pass |
| Admin | Logs | Refresh, Errors only, Field Audit | Allowed | Pass |
| HR | Employees | Export, Add Employee | Allowed | Pass |
| HR | Company | New/Save/Add controls | Usually restricted | Fail / Policy Risk |
| HR | Payroll | Setup Wizard, Run Payroll, Payroll Tools | Should be permission-scoped | Partial / High Risk |
| HR | Attendance | Lock Month disabled, Unlock visible | Depends on HR permission | Partial |
| Employee | Attendance | Lock Month, Save controls | Should be hidden | Fail |
| Employee | Shift Roster | Publish Roster | Should be hidden | Fail |
| Employee | Payroll | Payslip Viewer, Bulk publish disabled | Own payslip only, no bulk publish | Fail |
| Employee | Profile | Submit change request disabled until input, Upload document disabled until file | Acceptable | Pass / Partial |

## 8. Unauthorized Access Test Results

| Test | Expected | Actual | Pass/Fail |
|---|---|---|---|
| Employee opens `/hrms/company` | Access denied | Redirected to ESS without denial message | Partial |
| Employee opens `/hrms/employees` | Access denied | Redirected to ESS without denial message | Partial |
| Employee opens `/hrms/employees/1` | Access denied | Redirected to ESS without denial message | Partial |
| Employee opens `/hrms/payroll` | Access denied or own payslip-only screen | Payroll page opens | Fail |
| Employee opens `/hrms/payroll?tab=runs` | Access denied | Payroll page opens | Fail |
| Employee opens `/hrms/logs` | Access denied | Redirected to ESS without denial message | Partial |
| Employee opens `/hrms/settings` | Access denied | Redirected to ESS without denial message | Partial |
| HR opens `/hrms/logs` | Restricted | Redirected to HR Home without denial message | Partial |
| HR opens `/hrms/settings` | Restricted | Redirected to HR Home without denial message | Partial |

## 9. API / Runtime Issues Seen During UI UAT

| Role | Screen | API Error | Risk |
|---|---|---|---|
| Employee | Company direct URL | `403 /api/v1/reports/dashboard` | Redirect still triggers an unauthorized dashboard API call. |
| Employee | Shift Roster | `403 /api/v1/attendance/locks?month=6&year=2026` | Employee can open a screen that then backend-blocks admin lock data. UI should hide/deny before API call. |
| Employee | Profile | `500 /api/v1/auth/sessions/me` | Employee profile session list endpoint fails from UI. |

## 10. Security Risks

| Priority | Risk | Impact | Recommendation |
|---|---|---|---|
| P0 | Employee can open Payroll page | Employee may see payroll operational UI or future exposed data beyond own payslip. | Split employee payslip route from payroll operations and block `/hrms/payroll` for employee role unless rendered in strict own-payslip mode. |
| P0 | Employee can open Attendance Register and Shift Roster admin-style pages | Employee sees lock/roster controls and backend 403 calls. | Create employee-only attendance view and roster view; hide admin controls and block admin routes. |
| P1 | HR sees Company and platform setup screens | HR may alter organization master/setup beyond intended HR operations. | Separate HR Admin from HR Executive permissions; restrict Company, Workflow Designer, Custom Fields and Enterprise by granular permissions. |
| P1 | Blocked routes silently redirect | Users cannot distinguish denied access from navigation behavior; QA cannot certify explicit denial. | Add standard Access Denied page with role, attempted route and support guidance. |
| P1 | Employee profile sessions API returns 500 | Security/session page unreliable for employees. | Fix session endpoint or hide session panel until endpoint is stable. |
| P2 | Buttons visible when action is not allowed | Users see controls they cannot use, increasing support tickets and audit confusion. | Hide unauthorized actions; only disable actions for missing input/state, not permission. |

## 11. Recommended Permission Changes

1. Create explicit route groups:
   - `hrms.admin`
   - `hrms.hr_operations`
   - `hrms.payroll_processor`
   - `hrms.payroll_approver`
   - `hrms.employee_self_service`

2. Split payroll UI routes:
   - Admin/processor route: `/hrms/payroll`
   - Employee route: `/hrms/ess/payslips` or `/hrms/my-payslips`

3. Split attendance UI routes:
   - HR route: `/hrms/attendance`
   - Employee route: `/hrms/my-attendance`

4. Hide permission-denied buttons instead of showing disabled admin buttons to employees.

5. Add a real Access Denied route for direct URL attempts.

6. Add automated RBAC route tests for each role in CI:
   - menu visibility
   - route access
   - button visibility
   - API 403/500 route-load checks

## 12. Final Scores

| Area | Score |
|---|---:|
| Admin Readiness | 92% |
| HR Readiness | 78% |
| Employee Readiness | 58% |
| RBAC Readiness | 66% |
| Security Readiness | 62% |

## 13. Final Decision

Final decision: **RBAC NOT CERTIFIED**.

Release should not be treated as RBAC-certified until:

1. Employee role cannot open payroll operations, attendance register or shift roster admin screens.
2. HR setup/platform permissions are explicitly narrowed or approved by policy.
3. Direct unauthorized URLs show a clear Access Denied state.
4. Employee profile session API no longer returns 500.
5. Button-level permissions hide unauthorized actions instead of merely disabling or backend-blocking them.
