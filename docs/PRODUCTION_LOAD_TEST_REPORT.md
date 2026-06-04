# Production Load Test Report

Certification date: 2026-06-03  
Scope: Production release hardening - MySQL-backed API load validation  
Database engine: MySQL  
Certification database: `ai_hrms_load_cert`

## Executive Result

| Volume | Result | Payroll Run Duration | Notes |
|---:|---|---:|---|
| 1,000 employees | PASS | 2.68 seconds | API probes completed after route contracts were corrected. |
| 5,000 employees | PASS | 10.51 seconds | Employee search, attendance, payroll and reports remained responsive. |
| 10,000 employees | PASS | 21.81 seconds | Full corrected endpoint probe returned 0% error rate. |

Final load test status: **PASS** for the requested MySQL-backed API volume certification.

## Test Method

The load certification used the FastAPI application API with a real MySQL database. It did not use SQLite and did not use ORM-only simulation. Synthetic employee data was inserted into `ai_hrms_load_cert`, then validated through API endpoints with authenticated admin requests.

## 10,000 Employee Corrected API Probe

| API | Avg ms | p95 ms | p99 ms | Error Rate | Result |
|---|---:|---:|---:|---:|---|
| Login | 271.55 | 274.29 | 276.96 | 0% | PASS |
| Employee list/search | 145.64 | 170.93 | 171.19 | 0% | PASS |
| Employee detail | 25.51 | 20.57 | 47.42 | 0% | PASS |
| Attendance register | 417.43 | 429.17 | 462.65 | 0% | PASS |
| Attendance bulk save | 26.89 | 26.37 | 35.48 | 0% | PASS |
| Leave request list | 20.23 | 18.96 | 27.06 | 0% | PASS |
| Payroll runs | 16.82 | 16.87 | 19.43 | 0% | PASS |
| Payroll records | 114.44 | 116.90 | 138.15 | 0% | PASS |
| Payslip query | 22.82 | 22.46 | 28.21 | 0% | PASS |
| Payslip PDF generation | 167.41 | 49.81 | 651.31 | 0% | PASS |
| Salary register report | 22.80 | 23.00 | 26.84 | 0% | PASS |
| Attendance summary report | 16.85 | 16.77 | 18.34 | 0% | PASS |
| Bank advice preview | 61.55 | 64.91 | 68.65 | 0% | PASS |
| Bank exports list | 18.82 | 20.32 | 21.45 | 0% | PASS |
| Statutory PF template export | 24.27 | 24.63 | 29.22 | 0% | PASS |
| Reports dashboard | 24.01 | 23.57 | 29.00 | 0% | PASS |

## Earlier Volume Results

| Volume | Employee Search Avg | Attendance Register Avg | Payroll Summary Avg | Payroll Run Duration |
|---:|---:|---:|---:|---:|
| 1,000 employees | 53.73 ms | 73.39 ms | 42.84 ms | 2.68 seconds |
| 5,000 employees | 23.20 ms | 183.86 ms | 15.68 ms | 10.51 seconds |
| 10,000 employees | 102.11 ms | 802.08 ms | 20.66 ms | 21.81 seconds |

## Issues Found During Test Harness Cleanup

| Issue | Resolution |
|---|---|
| Direct-inserted synthetic employees had nullable fields that application-created employees normally default. | Corrected synthetic data defaults for schema-valid API detail responses. |
| Attendance register was initially called with `from_date`/`to_date`, but the endpoint requires `date`. | Retested with `date=2026-08-02`; result PASS. |
| Bank advice was initially called under the wrong prefix. | Retested under `/api/v1/hrms/payroll/{run_id}/bank-advice/preview`; result PASS. |
| Payslip list was initially treated as a list endpoint. | Retested using the actual `/api/v1/payroll/payslip` query and PDF endpoints; result PASS. |

## Bottleneck Observations

| Area | Observation | Recommendation |
|---|---|---|
| Attendance register | At 10k employees, full register response is the slowest measured read path. | Keep pagination/limits enforced and add indexed filters for branch/department/date in production usage. |
| Payroll run | 10k employee payroll completed in about 21.81 seconds in the certification environment. | Acceptable for batch processing; monitor DB CPU and transaction duration in production. |
| Payslip PDF | p99 was 651.31 ms during first generation. | Acceptable for on-demand generation; cache generated PDFs. |

## Certification Decision

MySQL-backed API load certification is **PASS**.

