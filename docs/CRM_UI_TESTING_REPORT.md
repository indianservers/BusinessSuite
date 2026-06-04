# CRM UI Testing Report

Date: 2026-06-04

## Certification Status

Status: Passed with fixes applied at suite RBAC level.

CRM passed focused UI smoke, backend REST testing, role isolation testing, and build regression.

## Tested Pages and Routes

Browser-smoke tested routes:

- `/crm`
- `/crm/leads`
- `/crm/contacts`
- `/crm/companies`
- `/crm/deals`
- `/crm/pipeline`
- `/crm/tasks`
- `/crm/calendar`
- `/crm/reports`
- `/crm/lead-scoring`
- `/crm/settings`
- `/crm/leads/1`
- `/crm/deals/1`

Backend-tested CRM flows:

- Lead CRUD, required-field validation, organization scoping
- Contact, company/account, deal/opportunity operations
- Lead conversion to contact/company/deal
- Pipeline and stage management
- Notes, mentions, notifications, activities, tasks, meetings
- Email/SMS/WhatsApp logging and templates
- Products, campaigns, tickets, files
- Custom fields and custom field values
- Duplicates scan/merge
- Territories and owner/team scoping
- Approval workflows and approval actions
- Calendar integrations and CRM reports
- Webhooks and delivery logging

## Role-Wise Access Matrix

| Role | CRM UI Access | CRM API Access |
| --- | --- | --- |
| Super Admin | Allowed after fix | Allowed through admin/superuser policy |
| CRM Sales User | Allowed | CRM permission scoped |
| CRM Viewer | Route policy supports CRM viewer roles | Read/manage split enforced by API permissions |
| PMS User | Blocked from CRM direct routes | Cross-module denial verified in UI smoke |
| HR/Employee | Not broadened by this pass | Existing HRMS regression passed |

## UI Issues Found

- Super Admin frontend route/nav policy did not grant CRM module access unless the role string was CRM-specific.

## Bugs Fixed

- [roles.ts](../frontend/src/lib/roles.ts): superusers are now accepted by CRM route checks and CRM navigation generation.

## API/Table Independence Findings

- CRM APIs are under `/api/v1/crm`.
- CRM models use `crm_*` tables.
- CRM intentionally references common `users`, `employees`, `companies/branches`, `audit_logs`, and `notifications` for ownership, organization scope, audit, and notifications.
- No PMS or HRMS operational table dependency was found in CRM data models.

## Pending Issues

- Python/Pydantic deprecation warnings remain in backend tests. They are not CRM functional blockers.

## Evidence

- `pytest tests\test_crm_rest_api.py tests\test_pms_project_access.py tests\test_pms_readiness_features.py`: 50 passed.
- `npm run test:rbac -- --grep "PMS and CRM UI certification smoke"`: 3 passed.
- `npm run build`: passed.
