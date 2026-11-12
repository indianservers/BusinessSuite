param([string[]]$Tests = @(
    'tests/test_business_suite_pos_integrity.py',
    'tests/test_business_suite_gst_matrix.py',
    'tests/test_business_suite_contact_retention.py',
    'tests/test_business_suite_pagination.py',
    'tests/test_business_suite_pos_concurrency.py',
    'tests/test_business_suite_live_browser.py',
    'tests/test_business_suite_commercial_links.py',
    'tests/test_common_task_scope.py',
    'tests/test_contact_directory.py',
    'tests/test_master_data.py',
    'tests/test_shared_catalog.py',
    'tests/test_pos_shared_catalog.py',
    'tests/test_srm_inventory_product_master.py',
    'tests/test_srm_pos_sessions.py',
    'tests/test_srm_pos_held_bills.py',
    'tests/test_srm_contracts.py',
    'tests/test_srm_recurrence.py',
    'tests/test_fam_gst_calculation.py',
    'tests/test_fam_srm_posting_idempotency.py',
    'tests/test_fam_srm_posting_reversal.py',
    'tests/test_module_scheduling.py',
    'tests/test_cross_module_audit.py'
))
$ErrorActionPreference = 'Stop'
$qaBackend = Split-Path $PSScriptRoot -Parent
$qaRepo = Split-Path $qaBackend -Parent
$qaBin = Join-Path $qaRepo '.local\postgresql\pgsql\bin'
$qaPython = Join-Path $qaBackend 'venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath (Join-Path $qaBin 'initdb.exe'))) { throw 'Bundled PostgreSQL runtime is missing.' }
$qaRoot = Join-Path $qaRepo ('.local\business-suite-qa-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $qaRoot | Out-Null
$qaData = Join-Path $qaRoot 'data'
& (Join-Path $qaBin 'initdb.exe') -D $qaData -U qa_suite --auth=trust --encoding=UTF8 --no-locale *> (Join-Path $qaRoot 'initdb.log')
if ($LASTEXITCODE -ne 0) { throw "QA cluster initialization failed; see $qaRoot" }
$qaListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$qaListener.Start(); $qaPort = $qaListener.LocalEndpoint.Port; $qaListener.Stop()
Add-Content -LiteralPath (Join-Path $qaData 'postgresql.conf') -Value "`nlisten_addresses = '127.0.0.1'`nport = $qaPort`nmax_locks_per_transaction = 512"
function Invoke-QaPgCtl([string]$operation) {
    $qaArguments = '-D "' + $qaData + '" -l "' + (Join-Path $qaRoot 'server.log') + '" -w ' + $operation
    $qaProcess = Start-Process -FilePath (Join-Path $qaBin 'pg_ctl.exe') -ArgumentList $qaArguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $qaRoot ($operation + '.log')) -RedirectStandardError (Join-Path $qaRoot ($operation + '-error.log'))
    # Wait for pg_ctl itself; Start-Process -Wait would also wait for the server.
    $qaProcess.WaitForExit()
    if ($qaProcess.ExitCode -ne 0) { throw "QA server $operation failed; see $qaRoot" }
}
$qaOriginal = @{}
foreach ($qaName in @('TEST_DATABASE_URL','FAST_TEST_PASSWORD_HASHES','UPLOAD_DIR')) { $qaOriginal[$qaName] = [Environment]::GetEnvironmentVariable($qaName, 'Process') }
$qaResult = 1
try {
    Invoke-QaPgCtl 'start'
    & (Join-Path $qaBin 'createdb.exe') -h 127.0.0.1 -p $qaPort -U qa_suite business_suite_qa_test
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated QA database.' }
    $env:TEST_DATABASE_URL = "postgresql+psycopg://qa_suite@127.0.0.1:$qaPort/business_suite_qa_test"
    $env:FAST_TEST_PASSWORD_HASHES = '1'
    $env:UPLOAD_DIR = Join-Path $qaRoot 'uploads'
    Push-Location $qaBackend
    try {
        & $qaPython -m pytest @Tests -q --disable-warnings ('--junitxml=' + (Join-Path $qaRoot 'results.xml'))
        $qaResult = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    foreach ($qaName in $qaOriginal.Keys) { [Environment]::SetEnvironmentVariable($qaName, $qaOriginal[$qaName], 'Process') }
    Invoke-QaPgCtl 'stop'
    Write-Output "QA artifacts retained at $qaRoot"
}
exit $qaResult
