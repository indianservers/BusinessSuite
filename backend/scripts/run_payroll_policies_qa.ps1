$ErrorActionPreference = 'Stop'
$suiteRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $suiteRoot 'backend/venv/Scripts/python.exe'
$previousResult = $env:PAYROLL_PG_RESULT_FILE
$previousTestDatabase = $env:TEST_DATABASE_URL
$failed = $false
Push-Location $suiteRoot
try {
    $env:PAYROLL_PG_RESULT_FILE = 'payroll-policy-regression-postgresql.xml'
    & $python backend/scripts/run_payroll_postgresql_qa.py
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    $env:PAYROLL_PG_RESULT_FILE = 'payroll-policy-concurrency-postgresql.xml'
    & $python backend/scripts/run_payroll_postgresql_qa.py tests/test_payroll_qa_concurrency.py
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    & $python backend/scripts/run_payroll_postgresql_qa.py --browser
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    Push-Location frontend
    try {
        & npm run typecheck
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    } finally { Pop-Location }
    Push-Location backend
    try {
        Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
        $env:FAST_TEST_PASSWORD_HASHES = '1'
        $tests = @(Get-ChildItem tests/test_payroll*.py | Where-Object { $_.Name -ne 'test_payroll_qa_concurrency.py' } | ForEach-Object { $_.FullName }) + @('tests/test_hrms_leave_payroll_feeds.py', 'tests/test_leave.py', 'tests/test_leave_accrual_carry_forward.py')
        & $python -m pytest @tests -q --tb=short -o junit_family=xunit1 --junitxml=../.tmp/payroll-followup-sqlite.xml
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    } finally { Pop-Location }
    & $python backend/scripts/report_payroll_postgresql_qa.py
    if ($LASTEXITCODE -ne 0) { $failed = $true }
} finally {
    $env:PAYROLL_PG_RESULT_FILE = $previousResult
    $env:TEST_DATABASE_URL = $previousTestDatabase
    Pop-Location
}
if ($failed) { exit 1 }
