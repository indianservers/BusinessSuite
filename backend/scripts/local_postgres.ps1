param([ValidateSet('start','stop','status')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pgRoot = Join-Path $workspaceRoot '.local\postgresql'
$pgCtl = Join-Path $pgRoot 'pgsql\bin\pg_ctl.exe'
$pgData = Join-Path $pgRoot 'data'
if (-not (Test-Path -LiteralPath $pgCtl)) { throw 'PostgreSQL binaries missing. Install PostgreSQL or provision the local runtime; see POSTGRESQL_SETUP.md.' }
if ($Action -eq 'start') {
    & $pgCtl -D $pgData status *> $null
    if ($LASTEXITCODE -eq 0) { Write-Output 'PostgreSQL is running'; exit 0 }
    $arguments = '-D "' + $pgData + '" -l "' + (Join-Path $pgRoot 'server.log') + '" -w start'
    $process = Start-Process -FilePath $pgCtl -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    exit $process.ExitCode
}
& $pgCtl -D $pgData $Action
exit $LASTEXITCODE
