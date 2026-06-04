# Role-Based Suite UAT Report

Date: 2026-06-04

## Certification Status

Status: Passed for tested role scenarios.

## Role-Wise PMS Access

| Role | Result |
| --- | --- |
| Super Admin | Allowed after frontend policy fix |
| PMS Project Manager | Allowed; project routes render |
| PMS Viewer | PMS route access verified |
| CRM User | Blocked from PMS direct URL |
| HRMS Employee | Existing HRMS self-service isolation regression passed |

## Role-Wise CRM Access

| Role | Result |
| --- | --- |
| Super Admin | Allowed after frontend policy fix |
| CRM Sales User | Allowed; CRM workspace routes render |
| PMS Project Manager | Blocked from CRM direct URL |
| PMS Viewer | Blocked from CRM direct URL |
| HRMS Employee | Existing HRMS self-service isolation regression passed |

## Unauthorized Access Tests

- CRM user direct URL to `/pms/projects`: blocked with 403.
- PMS user direct URL to `/crm/leads`: blocked with 403.
- PMS viewer direct URL to `/crm/deals`: blocked with 403.
- HRMS employee direct URLs to restricted HRMS routes: blocked by existing regression.

## Direct URL/API Bypass Tests

- PMS backend tests verify project access scoping and member/viewer restrictions.
- CRM backend tests verify organization scoping, permissions, and record visibility.
- UI smoke verifies route-level denial for cross-module direct navigation.

## Final RBAC Certification

Passed for automated UAT coverage in this pass.

Remaining caveat: exhaustive manual testing for every named business role against every button-level action was not performed; the report reflects automated route/API/role coverage available in this repository.

## Evidence

- `npm run test:rbac -- --grep "PMS and CRM UI certification smoke"`: 3 passed.
- `npm run test:rbac -- --grep "HRMS RBAC all-role UI verification"`: 6 passed.
- `pytest tests\test_crm_rest_api.py tests\test_pms_project_access.py tests\test_pms_readiness_features.py`: 50 passed.
