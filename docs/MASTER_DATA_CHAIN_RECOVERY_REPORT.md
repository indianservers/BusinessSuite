# Master Data Chain Recovery Report

Date: 2026-06-03  
Scope: Company -> Branch -> Department -> Designation -> Employee  
Role: Senior Product Architect and Root Cause Analyst  
Method: UI creation first, followed by API response, database persistence, refresh/relogin persistence, endpoint and build validation.

## Executive Root Cause

The HRMS master-data chain was broken at the first node.

`POST /api/v1/company/` created companies successfully, but `GET /api/v1/company/` returned 500 because legacy company records had `NULL` values in fields that the response schema declared as non-nullable defaults. FastAPI raised a response validation error while serializing the company list. Because the company list API failed, company dropdowns were empty, branch creation submitted invalid parent data, and the downstream Branch -> Department -> Designation -> Employee chain could not be completed reliably.

A secondary UI bug made the failure look worse: validation errors from FastAPI 422 responses were arrays/objects, and the Settings/Company pages attempted to render them directly inside toast descriptions. React then crashed with "Objects are not valid as a React child" instead of showing a readable validation message.

## Fixes Applied

| Issue | Root Cause | Affected Screen | Affected API | Affected Table | Fix Applied | Retest Result |
|---|---|---|---|---|---|---|
| Company disappears after refresh | Company list serializer failed on nullable legacy default fields | HRMS Company, HRMS Settings | `GET /api/v1/company/` | `companies` | Added migration `20260603_005_master_data_chain_defaults.py` to backfill `country`, `working_days_per_week`, `fiscal_year_start_month`, `default_timezone`, `default_currency`; relaxed response schema fields to tolerate legacy nulls. | PASS |
| Company dropdown empty | Dropdown source depended on failing company list endpoint | Branch forms, Settings hierarchy forms | `GET /api/v1/company/` | `companies`, `branches` | Fixed company list serialization and verified company dropdown/list returns active companies. | PASS |
| Branch save 422 causes UI crash | Toast rendered FastAPI validation object/array directly | HRMS Company, HRMS Settings | Branch/department/designation create APIs | UI error handling | Added `apiError()` formatter to render API validation details as plain text. | PASS |
| Search missing for hierarchy lists | List endpoints did not support search even though UI/UAT requires search validation | Company hierarchy grids/dropdowns | Company, branch, department, designation list APIs | `companies`, `branches`, `departments`, `designations` | Added `search` filter to list endpoints. | PASS |
| Unsafe parent deletion | Parent records could be deactivated while active child records existed | Company hierarchy delete actions | Delete APIs | `companies`, `branches`, `departments`, `designations`, `employees` | Added 409 delete protection for company with branches, branch with departments/employees, department with designations/employees, designation with employees. | PASS |

## Test Data Created From UI

| Level | Record | ID / Code | Created From UI? | Persisted After Refresh? | Persisted After Relogin? |
|---|---|---|---:|---:|---:|
| Company | Indian Servers Chain Recovery 1780490262902 Pvt Ltd | Company ID 4 | Yes | Yes | Yes |
| Branch | Hyderabad Recovery Head Office | Branch ID 3, `HYD-REC` | Yes | Yes | Yes |
| Department | Recovery IT | Department ID 2, `REC-IT` | Yes | Yes | Yes |
| Designation | Recovery Software Developer | Designation ID 2, `REC-SD` | Yes | Yes | Yes |
| Employee | Recovery01 Employee through Recovery20 Employee | `EMP00010` through `EMP00029` | Yes | Yes | Yes |

## Endpoint Certification

| Level | UI Save | API Request / Response | DB Insert | DB Read | List Endpoint | Dropdown Endpoint | Search Endpoint | Edit Endpoint | Delete Endpoint |
|---|---|---|---|---|---|---|---|---|---|
| Company | Saved from HRMS Company screen; success toast shown. | `POST /company/` returned saved company; `GET /company/?search=...` returned 200 with 1 row. | Row inserted in `companies`, ID 4. | DB read confirmed legal name, city, state, country and default payroll/company fields. | `GET /company/` returned 200 with active companies. | Same endpoint feeds company dropdown; verified active company visible. | `GET /company/?search=Indian Servers Chain Recovery...` returned 200. | `PUT /company/4` returned 200 and DB read confirmed updated legal name/phone. | `DELETE /company/4` returned 409: company used by active branches. |
| Branch | Saved from HRMS Company screen under selected company; success toast shown. | `POST /company/branches/` returned saved branch; `GET /company/branches/?company_id=4` returned 200. | Row inserted in `branches`, ID 3. | DB read confirmed `company_id=4`, city/state/country and active status. | `GET /company/branches/?company_id=4` returned 200 with 1 row. | Same endpoint feeds branch dropdown; verified branch visible in UI after selecting company. | `GET /company/branches/?company_id=4&search=Hyderabad Recovery Head Office` returned 200. | `PUT /company/branches/3` returned 200 and DB read confirmed phone/email update. | `DELETE /company/branches/3` returned 409: branch used by departments or employees. |
| Department | Saved from HRMS Company screen using the new branch; success toast shown. | `POST /company/departments/` returned saved department; `GET /company/departments/?branch_id=3` returned 200. | Row inserted in `departments`, ID 2. | DB read confirmed `branch_id=3`, code and active status. | `GET /company/departments/?branch_id=3` returned 200 with 1 row. | Same endpoint feeds department dropdown; verified department visible in UI. | `GET /company/departments/?branch_id=3&search=Recovery IT` returned 200. | `PUT /company/departments/2` returned 200 and DB read confirmed description update. | `DELETE /company/departments/2` returned 409: department used by designations or employees. |
| Designation | Saved from HRMS Company screen using the new department; success toast shown. | `POST /company/designations/` returned saved designation; `GET /company/designations/?department_id=2` returned 200. | Row inserted in `designations`, ID 2. | DB read confirmed `department_id=2`, grade `G5`, level `5`, active status. | `GET /company/designations/?department_id=2` returned 200 with 1 row. | Same endpoint feeds designation dropdown; verified designation visible in UI. | `GET /company/designations/?department_id=2&search=Recovery Software Developer` returned 200. | `PUT /company/designations/2` returned 200 and DB read confirmed description update. | `DELETE /company/designations/2` returned 409: designation used by employees. |
| Employee | 20 employees saved from HRMS Employees UI; each opened on detail page after save. | `GET /employees/?search=Recovery&limit=25` returned 200; individual `GET /employees/10` returned 200. | 20 rows inserted in `employees`, IDs 10-29. | DB read confirmed all 20 employees have `branch_id=3`, `department_id=2`, `designation_id=2`. | `GET /employees/` returned 200 and employee list showed Recovery employees after relogin. | Employee form dropdowns used branch, department and designation chain successfully. | `GET /employees/?search=Recovery&limit=25` returned 200. | `PUT /employees/10` returned 200 and DB read confirmed phone/work location update. | Disposable employee `EMP00030` was created and deleted; `DELETE /employees/30` returned 200, subsequent `GET /employees/30` returned 404. The certified 20 employees remained active. |

## Database Evidence

| Check | Result |
|---|---|
| Company row | `companies.id=4`, city `Hyderabad`, state `Telangana`, country `India`, working days `5`, fiscal start month `4`, timezone `Asia/Kolkata`, currency `INR`. |
| Branch row | `branches.id=3`, `company_id=4`, active, city `Hyderabad`, state `Telangana`, country `India`. |
| Department row | `departments.id=2`, `branch_id=3`, active. |
| Designation row | `designations.id=2`, `department_id=2`, grade `G5`, level `5`, active. |
| Employee rows | 20 active employees found with `branch_id=3`, `department_id=2`, `designation_id=2`, employee codes `EMP00010` through `EMP00029`. |
| Employee edit | `employees.id=10` updated to phone `9888810000` and work location `Hyderabad Recovery Office`. |
| Employee delete probe | Disposable `EMP00030` was soft-deleted; certified 20 active chain employees remained intact. |

## Refresh And Relogin Certification

| Step | Result |
|---|---|
| Save company from UI | PASS |
| Verify company visible immediately | PASS |
| Refresh browser and verify company remains | PASS |
| Login again and open HRMS Company | PASS |
| Select recovered company and verify branch, department, designation render | PASS |
| Open HRMS Employees after relogin and verify Recovery employees remain | PASS |
| Verify API after relogin | PASS |
| Verify database records after relogin | PASS |

## Validation Commands

| Validation | Result |
|---|---|
| `alembic upgrade head` | PASS |
| `pytest -q backend/tests/test_top_gap_closure.py backend/tests/test_new_hrms_modules.py` | PASS, 3 passed |
| `npm run lint` in `frontend` | PASS |
| `npm run build` in `frontend` | PASS |
| Live backend server | PASS, `uvicorn app.main:app --host 127.0.0.1 --port 8001` served API retest |
| Live frontend server | PASS, `http://127.0.0.1:5173` used for UI retest |

## Final Status

| Module | Status | Reason |
|---|---|---|
| Company | PASS | UI save, list, search, edit, DB read and protected delete passed. `GET /api/v1/company/` no longer returns 500. |
| Branch | PASS | Company dropdown populated, branch save passed, list/dropdown/search/edit/protected delete passed. |
| Department | PASS | Created under new branch, persisted, visible and endpoint checks passed. |
| Designation | PASS | Created under new department, persisted, visible and endpoint checks passed. |
| Employee | PASS | 20 UI-created employees persisted with correct branch, department and designation; edit/search/delete probe passed. |
| Overall Chain | PASS | Complete Company -> Branch -> Department -> Designation -> Employee chain works after refresh and fresh login. |

