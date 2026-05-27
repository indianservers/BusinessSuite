# Multi-App Architecture

The suite now supports deployable product modules through environment-driven
registries.

Umbrella product name: **Business Suite**.

Apps:

- HRMS
- KaryaFlow: Project Management
- VyaparaCRM: CRM

## App Separation Rules

The three product apps must stay clearly separated. Only true platform services
belong in common code.

| Layer | Common platform | HRMS | KaryaFlow / PMS | VyaparaCRM |
| --- | --- | --- | --- | --- |
| Primary owner | Suite shell | HR and employee operations | Delivery/project operations | Sales/customer operations |
| Core records | Users, organizations, audit logs, sessions, workflow engine, notification events, integration events | Employees, payroll, attendance, leave, recruitment, onboarding, performance, benefits | Clients, projects, members, boards, tasks, sprints, milestones, dependencies, time logs, client approvals | Leads, contacts, companies, deals, quotations, campaigns, activities, support tickets |
| Route prefix | `/api/v1/auth`, `/api/v1/logs`, shared platform routes | `/api/v1/...` HRMS routes from `app.api.v1` | `/api/v1/project-management` | `/api/v1/crm` |
| Frontend base | Login, shell, common layout, global app registry | `/hrms` | `/project-management` | `/crm` |
| Table prefix | `common_` for new shared tables | `hrms_` for new HRMS tables | `pms_` | `crm_` |

Keep a feature common only when every installed app can use it without depending
on another app. Examples: auth, roles, audit, notifications, workflow engine,
files, integrations, and a future `common_people` or `common_profiles` table.

Do not place app-specific records in common code. Examples:

- HRMS owns payroll runs, leave requests, attendance punches, employee lifecycle,
  and statutory records.
- PMS owns project tasks, boards, releases, dependencies, client approvals, and
  delivery time logs.
- CRM owns leads, deals, quotations, sales activities, campaigns, and customer
  pipeline records.

Allowed cross-app links should be explicit references, not hidden ownership
mixing. Examples: a CRM deal can create a PMS project; a PMS billable timesheet
can create a CRM/accounting invoice draft; HRMS skills/holidays can feed PMS
capacity planning through a shared profile/resource view.

## Backend

Use `INSTALLED_APPS` to select backend routers, models, and seed behavior.

Examples:

```env
INSTALLED_APPS=hrms
```

```env
INSTALLED_APPS=crm,project_management
```

Current modules:

- `hrms`
- `crm`
- `project_management`

Common platform code is loaded for every deployment: auth, users, people,
profiles, audit, base database setup, security, logs, and workflow engine.

## Table Naming

Use lowercase prefixes so table names stay portable across MySQL, PostgreSQL,
Windows, and Linux deployments.

- Common/shared tables: `common_<name>`
- HRMS tables: `hrms_<name>`
- Project Management/KaryaFlow tables: `pms_<name>`
- CRM/VyaparaCRM tables: `crm_<name>`

Existing HRMS tables and the legacy common auth table `users` still use their
original names. New app tables should use the prefix rule immediately. Renaming
current HRMS/common tables should be done later with explicit Alembic
migrations, not by casual model edits.

Examples:

```txt
common_users
common_organizations
common_files
common_people
common_profiles
hrms_employees
hrms_payroll_runs
pms_projects
pms_tasks
crm_leads
crm_deals
```

## Frontend

Use `VITE_INSTALLED_APPS` to select visible routes and navigation.

Examples:

```env
VITE_INSTALLED_APPS=hrms
```

```env
VITE_INSTALLED_APPS=crm,project_management
```

HRMS pages now live under `frontend/src/apps/hrms/pages`. Login remains shared
under `frontend/src/pages/auth`.

## Shared Identity Boundary

Shared identity is centralized in common platform tables and exposed through
services:

- `users` remains the legacy common authentication table used by all modules.
- `common_people` stores cross-app person records linked to a user and optional
  source module record.
- `common_profiles` stores cross-app profile data such as display preferences,
  photo, bio, timezone, visibility, and extensible profile JSON.

Modules should use their own facade service instead of reading another app's
tables for identity concerns:

- HRMS: `HrmsIdentityService`
- CRM: `CrmIdentityService`
- Project Management: `ProjectIdentityService`

HRMS may still own employee-specific employment, payroll, attendance, and
statutory records. CRM/PMS should refer to shared person/user identity through
the common services and keep their app-owned records independent.
