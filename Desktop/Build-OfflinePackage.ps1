param(
    [string]$PostgresRoot = (Join-Path $PSScriptRoot '..\.local\postgresql\pgsql'),
    [string]$Python = (Join-Path $PSScriptRoot '..\backend\venv\Scripts\python.exe')
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$PostgresRoot = (Resolve-Path -LiteralPath $PostgresRoot).Path
$Python = (Resolve-Path -LiteralPath $Python).Path
if (-not (Test-Path -LiteralPath (Join-Path $PostgresRoot 'bin\initdb.exe'))) {
    throw 'Supply the root of a Windows PostgreSQL binary distribution with -PostgresRoot.'
}
$pythonInfo = & $Python -I -c "import sys, sysconfig, struct; print(sys.base_prefix); print(sysconfig.get_path('purelib')); print(struct.calcsize('P') * 8)"
if ($LASTEXITCODE -ne 0 -or $pythonInfo.Count -ne 3 -or $pythonInfo[2] -ne '64') {
    throw 'Use the 64-bit Python virtual environment with the Business Suite backend dependencies installed.'
}

# Build into a new folder so stale binaries or local data cannot enter the package.
$release = Join-Path $workspace ('.local\desktop-release\BusinessSuite-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $release | Out-Null

function Copy-Tree($Source, $Destination, $ExcludeDirectories = @(), $ExcludeFiles = @()) {
    $arguments = @($Source, $Destination, '/E', '/R:1', '/W:1', '/NJH', '/NJS', '/NFL', '/NDL', '/NP', '/XJ')
    if ($ExcludeDirectories.Count) { $arguments += @('/XD') + $ExcludeDirectories }
    if ($ExcludeFiles.Count) { $arguments += @('/XF') + $ExcludeFiles }
    & robocopy @arguments
    if ($LASTEXITCODE -ge 8) { throw "Could not copy $Source." }
}

$backend = Join-Path $workspace 'backend'
$packageBackend = Join-Path $release 'backend'
$excludedSource = @('__pycache__', '.git', '.local', '.secrets', '.venv', 'venv', 'node_modules', 'uploads', 'vyapara_erp')
foreach ($directory in @('app', 'alembic_postgresql', 'alembic_platform')) {
    Copy-Tree (Join-Path $backend $directory) (Join-Path $packageBackend $directory) $excludedSource @('.env', '.env.*', '*.pyc')
}
Copy-Item -LiteralPath @(
    (Join-Path $backend 'create_db.py'), (Join-Path $backend 'suite_email_transport.py'),
    (Join-Path $backend 'alembic.ini'),
    (Join-Path $backend 'alembic_platform.ini'), (Join-Path $backend 'requirements.txt')
) -Destination $packageBackend

$pythonHome = $pythonInfo[0]
$pythonPackage = Join-Path $release 'python'
New-Item -ItemType Directory -Path $pythonPackage | Out-Null
Get-ChildItem -LiteralPath $pythonHome -File |
    Where-Object { $_.Name -match '^(python\.exe|python\d*\.dll|vcruntime.*\.dll|LICENSE\.txt)$' } |
    Copy-Item -Destination $pythonPackage
Copy-Tree (Join-Path $pythonHome 'Lib') (Join-Path $pythonPackage 'Lib') @('site-packages', '__pycache__', 'test', 'tests') @('*.pyc')
Copy-Tree (Join-Path $pythonHome 'DLLs') (Join-Path $pythonPackage 'DLLs')
Copy-Tree $pythonInfo[1] (Join-Path $pythonPackage 'Lib\site-packages') @('__pycache__') @('*.pyc')
& (Join-Path $pythonPackage 'python.exe') -I -c "import uvicorn, fastapi, psycopg, sqlalchemy, alembic"
if ($LASTEXITCODE -ne 0) { throw 'Bundled Python could not import the backend dependencies.' }

$pgPackage = Join-Path $release 'postgresql'
foreach ($directory in @('bin', 'lib', 'share')) {
    Copy-Tree (Join-Path $PostgresRoot $directory) (Join-Path $pgPackage $directory)
}
Get-ChildItem -LiteralPath $PostgresRoot -Filter '*license*.txt' -File | Copy-Item -Destination $pgPackage

Push-Location -LiteralPath (Join-Path $workspace 'frontend')
try {
    $previousApi = $env:VITE_API_BASE_URL
    $env:VITE_API_BASE_URL = '/api/v1'
    & node --max-old-space-size=4096 node_modules/vite/bin/vite.js build --mode desktop --outDir (Join-Path $release 'web')
    if ($LASTEXITCODE -ne 0) { throw 'The frontend build failed.' }
    $commit = & git -C $workspace rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate frontend release metadata.' }
    @{ commit = $commit } | ConvertTo-Json -Compress | Set-Content -Encoding ascii (Join-Path $release 'web\release.json')
}
finally {
    $env:VITE_API_BASE_URL = $previousApi
    Pop-Location
}

$desktopProject = Join-Path $PSScriptRoot 'Business Suite\Business Suite.csproj'
& dotnet publish $desktopProject -c Release -p:PlatformTarget=x64 -o $release
if ($LASTEXITCODE -ne 0) { throw 'The Windows app publish failed.' }
Copy-Item -LiteralPath @(
    (Join-Path $PSScriptRoot 'Start Local Workspace.cmd'),
    (Join-Path $PSScriptRoot 'local_workspace.py'),
    (Join-Path $PSScriptRoot 'OFFLINE.md')
) -Destination $release

Write-Output "Package ready: $release"
