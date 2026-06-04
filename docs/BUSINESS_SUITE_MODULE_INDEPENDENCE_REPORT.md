# Business Suite Module Independence Report

Date: 2026-06-04

## Certification Status

Status: Passed with minor suite RBAC/nav fixes.

## Table Separation Review

| Module | Primary Tables | Shared Tables Used |
| --- | --- | --- |
| HRMS | HRMS/domain tables under `backend/app/models/*` | `users`, roles/permissions, companies, notifications, audit |
| PMS | `pms_clients`, `pms_projects`, `pms_tasks`, `pms_sprints`, `pms_milestones`, `pms_files`, `pms_timesheets`, `pms_risks`, and other `pms_*` tables | `users`, `notifications`, `branches`, `departments`, employee identity fields |
| CRM | `crm_leads`, `crm_contacts`, `crm_companies`, `crm_deals`, `crm_pipelines`, `crm_tasks`, `crm_quotations`, and other `crm_*` tables | `users`, `employees`, `companies/branches`, `notifications`, `audit_logs` |

No PMS table depends on CRM tables. No CRM table depends on PMS tables. Shared references are common identity, organization, notification, audit, and master data references.

## API Separation Review

- HRMS routers are loaded through HRMS module registry entries.
- CRM router is loaded from `app.apps.crm.api.router` with prefix `/crm`.
- PMS router is loaded from `app.apps.project_management.api.router` with prefix `/project-management`.
- Common routers are limited to auth, logs, users, workflow engine, and AI agents.

## CSS and UI Separation Review

- Frontend module routes are split under `frontend/src/apps/hrms`, `frontend/src/apps/crm`, and `frontend/src/apps/project-management`.
- Shared shell components are used for topbar/sidebar/layout.
- Product-specific shell styling exists for `.product-crm` and `.product-pms`.
- No HRMS-only CSS dependency was found driving PMS/CRM layouts.

## Route Separation Review

- CRM routes are under `/crm`.
- PMS routes are under `/pms`.
- HRMS routes are under `/hrms`.
- Suite module index remains shared.

## Permission Separation Review

- CRM route access is based on CRM role keys and API permissions such as `crm_view`, `crm_manage`, and `crm_admin`.
- PMS route access is based on PMS role keys and backend project access helpers.
- Superuser suite access was corrected for CRM/PMS frontend route and navigation access.

## Shared Components/Tables Justification

Shared use is acceptable for:

- Authentication and user identity
- Roles and permissions
- Company/branch/department organization scope
- Notifications, mentions, and audit logs
- Common layout, topbar, sidebar, error boundary, and global search shell

## Risky Coupling Found and Fixed

- Fixed: superuser route/nav policy did not consistently apply to CRM/PMS.
- Fixed: sidebar duplicate nav key could produce unstable rendering when same route appeared twice with different labels.

## Evidence

- Backend PMS/CRM focused suite: 50 passed.
- PMS/CRM UI smoke: 3 passed.
- HRMS RBAC regression: 6 passed.
- Frontend production build: passed.
