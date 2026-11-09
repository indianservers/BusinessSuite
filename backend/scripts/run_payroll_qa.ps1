# SQLite baseline phase. Use run_payroll_postgresql_qa.ps1 for the PostgreSQL follow-up.
$ErrorActionPreference = 'Stop'
$suiteRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$evidenceRoot = Join-Path $suiteRoot '.tmp'
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
Push-Location (Join-Path $suiteRoot 'backend')
try {
    $env:FAST_TEST_PASSWORD_HASHES = '1'
    $core = @(Get-ChildItem tests/test_payroll*.py | Where-Object { $_.Name -notlike 'test_payroll_qa*' } | ForEach-Object { $_.FullName })
    & ./venv/Scripts/python.exe -m pytest @core tests/test_hrms_leave_payroll_feeds.py tests/test_expense_payroll_linkage.py tests/test_payslip_workflow.py -q --junitxml=../.tmp/payroll-final-core.xml
    & ./venv/Scripts/python.exe -m pytest tests/test_payroll_qa_boundaries.py tests/test_leave.py tests/test_leave_accrual_carry_forward.py tests/test_employees.py tests/test_attendance.py tests/test_attendance_logging.py tests/test_attendance_punch_api.py tests/test_salary_structure_versioning.py tests/test_security_employee_scope.py tests/test_employee_roles_managers.py -q --junitxml=../.tmp/payroll-extended-results.xml
    & ./venv/Scripts/python.exe -m pytest tests/test_payroll_qa_leave_matrix.py -q --junitxml=../.tmp/payroll-leave-matrix-results.xml
    & ./venv/Scripts/python.exe -m pytest tests/test_payroll_qa_lop_matrix.py tests/test_payroll_qa_statutory_matrix.py -q --junitxml=../.tmp/payroll-calculation-matrices-results.xml
} finally { Pop-Location }
Push-Location (Join-Path $suiteRoot 'frontend')
try {
    & npx playwright test --config=playwright.payroll-delivery.config.ts --reporter=json > ../.tmp/payroll-browser-results.json
    & npx playwright test --config=playwright.payslips.config.ts --reporter=json > ../.tmp/payroll-payslips-browser-results.json
    & npx playwright test --config=playwright.payroll-qa.config.ts --reporter=json > ../.tmp/payroll-live-browser-results.json
} finally { Pop-Location }
& (Join-Path $suiteRoot 'backend/venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'report_payroll_qa.py')
