# PMS RBAC Report

Verification date: 2026-06-04

Status: Partially Passed

## Roles Verified

- Project Manager: project creation, planning, reports, financial views.
- Project Director: portfolio/resource/capacity oversight.
- Team Lead: task, backlog, sprint, dependency execution.
- Developer: task/time/file execution.
- Client: client portal only.
- Finance Manager: reports, profitability, invoice workflow check.

## Backend RBAC Evidence

Passed:
- `test_department_scoped_project_visibility`
- `test_project_creator_becomes_manager_and_can_add_member`
- `test_non_member_cannot_view_or_create_project_tasks`
- `test_all_tasks_endpoint_scopes_by_accessible_organization`
- `test_task_attachments_are_project_scoped_and_log_activity`
- `test_task_saved_views_store_filters_columns_and_permissions`
- `test_pms_weekly_timesheet_submit_approve_reject_flow`
- `test_portfolio_dashboard_is_accessible_scoped_and_calculates_health`
- `test_pms_risk_register_is_project_scoped_and_affects_health`
- `test_pms_reports_are_real_data_and_access_scoped`

Backend access helpers checked:
- `backend/app/apps/project_management/access.py`
- `get_project_for_action` and permission guards in `backend/app/apps/project_management/api/router.py`

## Frontend RBAC Finding and Fix

Finding:
- PMS frontend route guard previously allowed every PMS role to access all `/pms/*` routes, including `/pms/admin`, `/pms/settings`, `/pms/security`, `/pms/apps`, `/pms/workflows`, and template/settings routes.

Fix applied:
- Added role-tiered PMS route filtering in `frontend/src/lib/roles.ts`.
- Added admin-only, manager-only, delivery/viewer, and client portal route classes.
- Updated `getRoleNav` to hide inaccessible PMS nav items.
- Updated `canAccessRoute` to call PMS-specific route access.

Browser evidence:
- `pms_team_member` -> `/pms/admin`: blocked with `403 ACCESS DENIED`.
- `pms_client` -> `/pms/admin`: blocked with `403 ACCESS DENIED`.
- `pms_client` -> `/pms/client-portal`: rendered.
- `pms_org_admin` -> `/pms/admin`: rendered.
- `pms_project_manager` -> `/pms/admin`: blocked after fix.

## Remaining RBAC Risks

- Frontend route guard is coarse-grained and cannot evaluate project membership for dynamic routes such as `/pms/projects/{id}`. Backend access checks remain the authoritative control.
- Client-specific data filtering in client portal needs seeded end-to-end verification against a real backend tenant.
- Finance Manager is represented by report/financial scenarios, but no distinct PMS finance role mapping was found in frontend role definitions.

Final RBAC status: Partially Passed. Backend RBAC is strong in focused tests; frontend route-level RBAC gap was fixed; client/finance persona mapping needs production role design validation.

