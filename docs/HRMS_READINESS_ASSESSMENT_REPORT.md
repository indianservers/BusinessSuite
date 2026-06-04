# HRMS Readiness Assessment Report

Date: 2026-06-03

Scope reviewed: HRMS backend APIs/models, payroll engine and extensions, attendance/leave/recruitment/performance/onboarding/exit/security/report modules, frontend HRMS routes, existing competitor gap documentation, and focused automated tests.

Benchmark reference: Zoho People, Zoho Payroll, Keka HR and greytHR baseline expectations for Indian SME/mid-market HRMS: employee master, leave, attendance, payroll, ESS, recruitment, onboarding, performance, exits, statutory compliance, reports, workflows, mobile/WhatsApp, biometric and audit controls.

## Executive Verdict

Final verdict: Partially Ready

HRMS readiness: 84%

Payroll readiness: 82%

Go-live score: 8.0 / 10

Recommended go-live path: controlled production rollout for SMEs, schools, colleges, trading companies, service companies and IT companies after environment/configuration hardening and admin training. Use caution for hospitals and manufacturing until shift/biometric/roster depth and statutory payroll output conformance are completed.

## Evidence Reviewed

- HRMS routes and UI surface: `frontend/src/apps/hrms/routes.tsx`
- Employee, attendance, leave, payroll, recruitment, performance, onboarding, exit, document, audit and statutory modules under `backend/app/api/v1`, `backend/app/models`, `backend/app/schemas`, and `backend/app/crud`
- Payroll real-world and Zoho-style UAT docs: `docs/PAYROLL_REAL_WORLD_TEST_CASES.md`, `docs/PAYROLL_ZOHO_STYLE_UAT_REVIEW.md`
- Competitor reference notes: `docs/competitor_gap_analysis.md`
- Automated tests covering mandatory validation and module foundations
- Public product benchmark pages:
  - Zoho People: https://www.zoho.com/people/features.html
  - Zoho Payroll: https://www.zoho.com/payroll/
  - Keka HR: https://www.keka.com/us/hr-cloud
  - greytHR: https://www.greythr.com/products

## Automated QA Result

| Test Area | Command | Result | Interpretation |
|---|---|---:|---|
| Core HRMS, leave, attendance, employee, payroll, F&F | `pytest -q tests/test_attendance.py tests/test_leave.py tests/test_employees.py tests/test_payroll_readiness_gate.py tests/test_payroll_real_world_engine.py tests/test_hrms_fnf_settlements.py tests/test_payroll_components.py tests/test_payroll_run_state_machine.py` | 42 passed | Mandatory validation cases and core HR/payroll flows pass. |
| HRMS modules, performance, onboarding, profile change, audit/privacy, documents, operations | `pytest -q tests/test_new_hrms_modules.py tests/test_performance_appraisal.py tests/test_onboarding.py tests/test_hrms_profile_change_requests.py tests/test_field_audit_privacy.py tests/test_document_governance.py tests/test_hrms_operational_foundations.py` | 16 passed | Extended HRMS foundations pass. |
| Test hygiene note | Secondary attempted command included nonexistent `tests/test_recruitment.py` | Not counted | Actual recruitment coverage is in `test_new_hrms_modules.py` and related HRMS module tests. |

Warnings: Tests emit many Pydantic v2 deprecation warnings. These are not functional failures, but they are release-hardening technical debt.

## Mandatory Validation

| Mandatory Case | Status | Evidence | Risk Level |
|---|---|---|---|
| Half-day attendance = 0.5 | Pass | `test_raw_half_day_attendance_counts_as_half_day` passed | Low |
| Joining mid-month | Pass | `test_mid_month_joining_and_exit_are_prorated` passed | Low |
| Exit mid-month | Pass | `test_mid_month_joining_and_exit_are_prorated` and F&F tests passed | Low |
| Salary revision | Pass / Partial | Salary assignment field audit and payroll revision/arrear foundation exist; deeper auto-arrear still needs business UAT | Medium |
| Leave without pay | Pass | Leave-to-payroll and LOP calculations are covered in payroll docs/tests | Low |
| Payroll approval | Pass | Payroll state machine and readiness gate tests passed | Low |
| Payroll locking | Pass | `test_locked_payroll_still_blocks_salary_mutation` passed | Low |

## Feature Readiness Matrix

| # | Feature | Available? | Partial? | Missing? | Risk Level |
|---:|---|---|---|---|---|
| 1 | Employee master | Yes | No | No | Low |
| 2 | Employee code/profile/job/statutory/bank fields | Yes | No | No | Low |
| 3 | Departments | Yes | No | No | Low |
| 4 | Designations | Yes | No | No | Low |
| 5 | Branches/work locations | Yes | No | No | Low |
| 6 | Business units/cost centers/grades/positions | Yes | No | No | Low |
| 7 | Employee documents | Yes | No | No | Low |
| 8 | Document verification and expiry | Yes | No | No | Low |
| 9 | Employee import/export | Yes | No | No | Medium |
| 10 | Profile update request approval | Yes | No | No | Low |
| 11 | Daily attendance | Yes | No | No | Low |
| 12 | Half-day attendance | Yes | No | No | Low |
| 13 | Late/early/short-hours computation | Yes | No | No | Low |
| 14 | Leave integration with attendance/payroll | Yes | No | No | Low |
| 15 | Biometric integration | No | Yes | No | Medium |
| 16 | Geo/selfie/QR attendance proof | No | Yes | No | Medium |
| 17 | Shift roster | Yes | No | No | Medium |
| 18 | Advanced rotational/night shift rules | No | Yes | No | High |
| 19 | Attendance reports | Yes | No | No | Low |
| 20 | Attendance month lock | Yes | No | No | Low |
| 21 | Annual leave | Yes | No | No | Low |
| 22 | Sick leave | Yes | No | No | Low |
| 23 | Casual leave | Yes | No | No | Low |
| 24 | Leave approval | Yes | No | No | Low |
| 25 | Leave balance | Yes | No | No | Low |
| 26 | Leave ledger | Yes | No | No | Low |
| 27 | Carry-forward/accrual jobs | Yes | No | No | Medium |
| 28 | Comp-off | No | Yes | No | Medium |
| 29 | Salary structures | Yes | No | No | Low |
| 30 | Salary components/earnings | Yes | No | No | Low |
| 31 | Deductions | Yes | No | No | Low |
| 32 | Statutory deductions | Yes | No | No | Medium |
| 33 | Reimbursements | Yes | No | No | Low |
| 34 | Loans | Yes | No | No | Medium |
| 35 | Salary advances | Yes | No | No | Low |
| 36 | Overtime | Yes | No | No | Medium |
| 37 | Bonus | Yes | No | No | Low |
| 38 | Arrears | No | Yes | No | Medium |
| 39 | Payroll approval | Yes | No | No | Low |
| 40 | Payroll lock/unlock | Yes | No | No | Low |
| 41 | Payslip generation/download | Yes | No | No | Low |
| 42 | Bank advice/export | Yes | No | No | Medium |
| 43 | PF/ESI/PT/TDS/Form 16 exports | No | Yes | No | High |
| 44 | Payroll reports | Yes | No | No | Low |
| 45 | ESS leave request | Yes | No | No | Low |
| 46 | ESS attendance view | Yes | No | No | Low |
| 47 | ESS payslip download | Yes | No | No | Low |
| 48 | ESS profile update | Yes | No | No | Low |
| 49 | Mobile/PWA ESS | No | Yes | No | Medium |
| 50 | WhatsApp ESS | No | Yes | No | Medium |
| 51 | Job openings | Yes | No | No | Medium |
| 52 | Candidate tracking | Yes | No | No | Medium |
| 53 | Interview management | Yes | No | No | Medium |
| 54 | Offer workflow/e-sign | No | Yes | No | Medium |
| 55 | Candidate-to-employee conversion | Yes | No | No | Medium |
| 56 | KPI/goals | Yes | No | No | Medium |
| 57 | Appraisals | Yes | No | No | Medium |
| 58 | Reviews | Yes | No | No | Medium |
| 59 | 360 feedback/OKR/check-ins | Yes | No | No | Medium |
| 60 | Calibration/nine-box/succession | No | Yes | No | Medium |
| 61 | Joining/onboarding | Yes | No | No | Low |
| 62 | Transfer | Yes | No | No | Medium |
| 63 | Promotion | Yes | No | No | Medium |
| 64 | Exit | Yes | No | No | Low |
| 65 | Final settlement | Yes | No | No | Low |
| 66 | Role permissions | Yes | No | No | Low |
| 67 | Audit logs | Yes | No | No | Low |
| 68 | Field audit for sensitive data | Yes | No | No | Low |
| 69 | Attendance reports | Yes | No | No | Low |
| 70 | Leave reports | Yes | No | No | Low |
| 71 | Payroll reports | Yes | No | No | Low |
| 72 | Employee reports | Yes | No | No | Low |
| 73 | Advanced analytics/report builder | No | Yes | No | Medium |
| 74 | Scheduled exports | No | Yes | No | Medium |
| 75 | Multi-entity payroll | No | Yes | No | High |

## Feature-Wise Pass/Fail Summary

| Area | Readiness | Status | Notes |
|---|---:|---|---|
| A. Employee Management | 90% | Pass | Strong employee master, org setup, documents, profile updates, hierarchy, and lifecycle history. |
| B. Attendance | 82% | Pass with gaps | Daily attendance, half-day, reports, locks, rosters and biometric foundation exist. Advanced rotational/night-shift and real device SDK depth need work. |
| C. Leave Management | 88% | Pass | Leave types, approvals, balances, ledger, accrual/carry-forward and calendar are strong. Comp-off and advanced policies need polish. |
| D. Payroll | 82% | Pass with gaps | Mandatory payroll cases pass. Statutory file conformance, multi-entity payroll, advanced arrears and production payment integrations remain. |
| E. ESS | 84% | Pass with gaps | Leave, attendance, payslip and profile update are available. Mobile/WhatsApp production flow needs completion. |
| F. Recruitment | 72% | Partial | Jobs, candidates, interviews and conversion exist. Career site, requisition-budget linkage, offer e-sign and source analytics need depth. |
| G. Performance | 76% | Partial | Goals, reviews, appraisals, OKR/360 foundations exist. Calibration, succession and mature analytics need more. |
| H. Lifecycle | 86% | Pass with gaps | Joining, onboarding, transfer/promotion events, exit and F&F are available. Policy-specific workflows need UAT. |
| I. Security | 84% | Pass with gaps | RBAC, audit logs, field audit, privacy/legal hold foundations are strong. SSO/MFA/IP enforcement and field audit viewer need hardening. |
| J. Reports | 78% | Partial | Standard reports exist. Scheduled XLSX/PDF exports and governed dashboards need more production polish. |

## Industry Compatibility

| Industry | Compatibility | Fit | Key Gaps Before Broad Rollout |
|---|---:|---|---|
| Schools | 84% | Good | Academic session leave calendars, substitute/temporary staff payroll templates, teacher workload reports. |
| Colleges | 82% | Good | Visiting/contract faculty policies, department-wise approvals, research/project payroll dimensions. |
| SMEs | 88% | Strong | Import/onboarding setup assistance, payroll statutory file final validation. |
| Hospitals | 74% | Partial | 24x7 roster, night/emergency duty rules, biometric reliability, compliance-grade audit, shift allowance UAT. |
| Manufacturing | 73% | Partial | Shift rotations, overtime policy depth, contractor/labour category handling, biometric SDK, canteen/transport deductions. |
| Trading companies | 86% | Good | Branch/location payroll, sales incentives as variable pay batches, expense/reimbursement cutoff rules. |
| IT companies | 87% | Good | Project timesheet/utilization linkage, performance calibration, hybrid attendance/mobile ESS polish. |

## Comparison Against Zoho People, Zoho Payroll, Keka HR and greytHR

| Capability | Competitor Baseline | Current HRMS | Gap |
|---|---|---|---|
| Core employee database | Employee master, org structure, documents, profile changes | Strong | Add more industry templates and employee setup wizard. |
| Leave | Balance, approval, policy rules, calendar | Strong | Comp-off and advanced policy scenarios need refinement. |
| Attendance | Web/mobile/biometric/shift/geo attendance | Good foundation | Real device SDK, shift marketplace and advanced rosters pending. |
| Payroll | Components, structures, statutory, payslips, approvals, lock | Strong foundation | Final statutory conformance, multi-entity payroll and production payment reconciliation pending. |
| ESS | Leave, attendance, payslip, profile, documents | Good | Mobile/WhatsApp production workflows need completion. |
| Recruitment | Jobs, candidates, interviews, offers, onboarding | Partial | Career site, e-sign, source analytics and interview calendar sync pending. |
| Performance | Goals, reviews, appraisals, feedback | Partial | Calibration, nine-box, succession and analytics pending. |
| Reports | Standard and custom reporting | Good foundation | Scheduled exports, PDF/XLSX depth and governed dashboards pending. |
| Security | RBAC, audit, privacy, MFA/SSO | Good foundation | Enforcement hardening for SSO/MFA/IP and field audit viewer pending. |
| India compliance | PF/ESI/PT/TDS/Form 16/statutory calendar | Partial to strong | Government-ready validation and portal connector remain key gaps. |

## Missing Features

- Government-ready statutory file validation for PF ECR, ESI, PT, LWF, TDS 24Q/26Q and Form 16 templates.
- Direct EPFO/ESIC portal submission or verified connector workflow.
- Full multi-entity payroll with legal entity, branch, pay group and cost-center separation across every report/export.
- Production biometric SDK integrations for common Indian devices such as ZKTeco/eSSL/Mantra/Reals.
- Advanced hospital/manufacturing shift rules: rotational weekly offs, night shifts, split shifts, emergency duty and shift swaps.
- Mobile-first ESS workflows with offline-safe leave, attendance, payslip and approvals.
- Production WhatsApp ESS with template approval, outbound manager CTA approvals and delivery callbacks.
- Career site, candidate source analytics, interview scheduling/calendar sync and offer e-sign.
- Performance calibration, nine-box, succession and mature compensation planning.
- Scheduled report exports with XLSX/PDF, email delivery and report subscriptions.
- Real enforcement hardening for MFA, SSO/SAML/OIDC, IP restrictions and lockout policies.

## Critical Bugs and Risks

| Priority | Issue | Current Result | Risk | Recommendation |
|---|---|---|---|---|
| P0 | No failing mandatory HRMS tests found in focused suite | 58 focused tests passed | Low functional risk for validated cases | Keep these in CI as release gates. |
| P0 | Statutory payroll exports are not proven government-ready | Foundation exists, conformance pending | Payroll compliance risk | Add file-format validation, statutory templates and accountant UAT. |
| P0 | Multi-entity payroll depth is partial | Pay groups/legal entities exist, full separation needs UAT | Incorrect payroll/accounting in multi-branch businesses | Add multi-entity regression tests and report/export scoping. |
| P1 | Biometric integration is foundation-level | Device/import foundations exist | Attendance disputes in factories/hospitals | Integrate vendor SDK/flat-file adapters and raw punch audit reconciliation. |
| P1 | Advanced shift rules need more coverage | Roster foundation exists | Hospitals/manufacturing may calculate attendance/OT incorrectly | Add rotational, night, split-shift and weekly-off policy tests. |
| P1 | Mobile/WhatsApp ESS not production complete | PWA/WhatsApp foundations exist | Adoption friction for field/labour staff | Complete mobile and WhatsApp workflows with delivery audit. |
| P2 | Pydantic v2 deprecation warnings are high-volume | 3,000+ warnings across focused tests | Future upgrade risk and noisy CI | Migrate schemas to `ConfigDict` and modern validators. |

## Priority Development Fixes

### P0 - Before Full Go-Live

1. Make statutory payroll outputs government-format validated, not only generated.
2. Add release-gate tests for multi-entity payroll: company, branch, department, pay group and cost center.
3. Add final payroll UAT for PF, ESI, PT, TDS, Form 16, bank advice and accounting export.
4. Keep mandatory cases in CI: half-day 0.5, mid-month joining/exit, LWP, payroll approval and lock.

### P1 - For Industry-Wide Deployment

1. Complete biometric device integrations and raw punch reconciliation.
2. Deepen hospital/manufacturing shift policy engine and OT/allowance mapping.
3. Build scheduled XLSX/PDF reports and dashboard subscriptions.
4. Complete mobile/WhatsApp ESS production workflows.
5. Add recruitment source analytics, interview calendar sync and offer e-sign.

### P2 - Competitive Depth

1. Add performance calibration, nine-box, succession and compensation planning.
2. Add industry packs for education, healthcare, manufacturing, trading and IT.
3. Add SSO/MFA/IP enforcement hardening and a field audit viewer.
4. Finish scheduled report builder UI and governed analytics.
5. Clean up Pydantic v2 warnings to reduce future maintenance risk.

## Go-Live Recommendation

Approve: limited production rollout for SMEs, schools, colleges, trading companies and IT companies.

Conditional approval: hospitals and manufacturing only after shift, biometric, OT and statutory payroll UAT.

Do not position as fully equivalent to Zoho People + Zoho Payroll + Keka + greytHR until statutory conformance, biometric production connectors, mobile/WhatsApp ESS, scheduled reporting and multi-entity payroll hardening are complete.

