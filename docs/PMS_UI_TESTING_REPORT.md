# PMS UI Testing Report

Date: 2026-06-04

## Certification Status

Status: Passed with fixes applied.

PMS passed focused UI smoke, backend API/access testing, and build regression after the fixes listed below.

## Tested Pages and Routes

Browser-smoke tested routes:

- `/pms`
- `/pms/projects`
- `/pms/projects/new`
- `/pms/tasks`
- `/pms/reports`
- `/pms/timesheets`
- `/pms/workload`
- `/pms/risks`
- `/pms/projects/1`
- `/pms/projects/1/board`
- `/pms/projects/1/milestones`
- `/pms/projects/1/files`

Backend-tested PMS flows:

- Project creation and manager assignment
- Project member add/update and viewer/member access
- Task create/list/update/delete, status changes, bulk update
- Task comments, mentions, checklists, subtasks, tags, attachments
- Sprints, backlog movement, dependencies, roadmap objects
- Timesheets, time logs, submit/approve/reject
- Saved task views and saved filters
- Reports, portfolio, workload, risks, clone/archive/template

## Role-Wise Access Matrix

| Role | PMS UI Access | PMS API Access |
| --- | --- | --- |
| Super Admin | Allowed | Allowed |
| PMS Project Manager | Allowed | Project/member scoped |
| PMS Team Member | Allowed where project access permits | Project/member scoped |
| PMS Viewer | Read-only UI route access verified | Viewer-scoped access verified |
| CRM User | Blocked from PMS direct routes | Cross-module denial verified in UI smoke |
| HR/Employee | Not broadened by this pass | Existing HRMS regression passed |

## UI Issues Found

- React duplicate-key warning in PMS sidebar caused by two navigation entries sharing `/pms/projects`.

## Bugs Fixed

- [Sidebar.tsx](../frontend/src/components/layout/Sidebar.tsx): sidebar nav keys now combine route and label, removing duplicate-key UI warnings.
- Added focused PMS/CRM Playwright certification smoke: [pms-crm-ui-certification.spec.ts](../playwright/pms-crm-ui-certification.spec.ts).

## API/Table Independence Findings

- PMS APIs are under `/api/v1/project-management`.
- PMS models use `pms_*` tables.
- PMS intentionally references common `users`, `notifications`, `branches`, `departments`, and employee identity fields for assignment, org scoping, visibility, and mentions.
- No HRMS payroll/attendance/leave table dependency was found inside PMS module code.

## Pending Issues

- Python/Pydantic deprecation warnings remain in backend tests. They are not PMS functional blockers.

## Evidence

- `pytest tests\test_crm_rest_api.py tests\test_pms_project_access.py tests\test_pms_readiness_features.py`: 50 passed.
- `npm run test:rbac -- --grep "PMS and CRM UI certification smoke"`: 3 passed.
- `npm run build`: passed.
