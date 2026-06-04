# Attendance, Leave and Payslip Recovery Report

Date: 2026-06-03  
Scope: Last three failing HRMS user workflows only  
Mode: UI-first customer workflow verification with API confirmation

## Executive Result

| Workflow | Final Status | Evidence |
|---|---|---|
| HR Attendance Entry | PASS | HR entered Recovery03 attendance from Attendance Register, saved successfully, refreshed page, row remained visible, and API returned the persisted half-day row. |
| Leave Application Chain | PASS | HR created and linked an employee login for Recovery03, employee submitted leave from UI, refreshed page, HR approved it from approvals UI, and API returned Approved. |
| Payslip Viewer | PASS | Admin loaded Recovery03 payslip from Payslip Viewer, employee loaded own payslip, and API returned gross/net plus grouped earnings and deductions. |
| Overall User Workflow | PASS | All three workflows are working from UI with API-backed persistence. |

## Fixes Applied

| Area | Issue | Fix Applied |
|---|---|---|
| Attendance UI | HR could not manually enter attendance from the UI. | Added Attendance Register with employee code, employee name, department, branch, date, status, hours worked, OT hours, remarks, bulk status, Save Selected, Save All Visible and summary tiles. |
| Attendance API | UI needed a grid-style attendance source and bulk save endpoint. | Added `GET /attendance/register` and `POST /attendance/bulk-entry`, including half-day normalization, weekly-off mapping, lock protection and audit log creation. |
| Leave UI | Admin/HR pages were firing employee self-service calls without employee profile context. | Guarded employee-only leave balance and my-request queries. |
| Employee user mapping | HR needed to create/link employee login without using superuser-only auth APIs. | Added `POST /employees/{employee_id}/user-account` and wired Employee Account Wizard to it. |
| Leave type selection | Employee apply form could show global leave types ahead of allocated leave types. | Leave application dropdown now uses employee balance-backed leave types first. |
| Payslip viewer | Admin viewer did not load payslip unless employee selection was mapped into the payslip query. | Wired employee search/dropdown to payslip query and retained employee self-service access for own payslip. |
| Payroll page noise | Payslip page caused an unrelated tax projection 400 in the background. | Scoped tax projection query to employee tax tab only. |

## UI Verification

| Screen | Data Entered / Selected | Saved Successfully? | Visible After Refresh? | API Verified? | Result |
|---|---|---:|---:|---:|---|
| Attendance Register | Employee `EMP00012 - Recovery03 Employee`, date `2026-07-10`, status `Half-day`, hours `4.00`, OT `1.25`, remarks `UI recovery attendance 1780502933498` | Yes | Yes | Yes, `GET /attendance/register?date=2026-07-10&search=Recovery03` | PASS |
| Employee Account Wizard | Employee `EMP00012 - Recovery03 Employee`, login `recovery03.uat.1780502933498@example.com` | Yes | Yes | Yes, `GET /employees/12` returned `user_id: 18` | PASS |
| Leave Application | Employee login submitted `Certification Paid Leave`, date `2026-07-12`, reason `UI recovery leave final 1780503016946` | Yes | Yes | Yes, `GET /leave/my-requests` returned request `2` as `Pending` | PASS |
| Leave Approval | HR approved request `2` from Approvals UI | Yes | Yes | Yes, `GET /leave/requests?status=Approved` returned `Approved` | PASS |
| Payslip Viewer - Admin | HR loaded `EMP00012 - Recovery03 Employee` payslip | Yes | Yes | Yes, `GET /payroll/payslip?month=6&year=2026&employee_id=12` returned gross `50000`, net `48200`, 3 earnings, 1 deduction | PASS |
| Payslip Viewer - Employee | Employee loaded own June 2026 payslip | Yes | Yes | Yes, `GET /payroll/payslip?month=6&year=2026` returned gross `50000`, net `48200`, 3 earnings, 1 deduction | PASS |

## Validation Commands

| Check | Result |
|---|---|
| `pytest -q tests/test_attendance.py tests/test_hrms_leave_payroll_feeds.py tests/test_payroll_components.py` | PASS, 8 passed |
| `npm run lint` | PASS |
| `npm run build` | PASS |
| Browser UI verification via Playwright | PASS for attendance, leave and payslip workflows |

## Final Status

| Chain | Status |
|---|---|
| Attendance | PASS |
| Leave | PASS |
| Payslip | PASS |
| Overall User Workflow | PASS |

