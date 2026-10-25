# Keep this a plain script so PowerShell does not consume Flutter's -v flag
# as the advanced-function Verbose common parameter.
$FlutterArguments = $args

$ErrorActionPreference = 'Stop'
$appDirectory = Split-Path $PSScriptRoot -Parent
$localSdk = Join-Path $env:USERPROFILE '.local/share/flutter/bin/flutter.bat'
$flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
if ($flutterCommand) {
    $flutterExecutable = $flutterCommand.Source
} elseif (Test-Path -LiteralPath $localSdk) {
    $flutterExecutable = $localSdk
} else {
    throw 'Install the stable Flutter SDK and add its bin directory to PATH.'
}

# Windows native hooks need an SDK executable path without spaces. The JDK
# also needs a non-virtualized temporary path for its local domain sockets.
$taskFso = New-Object -ComObject Scripting.FileSystemObject
$flutterExecutable = $taskFso.GetFile($flutterExecutable).ShortPath
$socketDirectory = Join-Path $appDirectory '.dart_tool/java-sockets'
New-Item -ItemType Directory -Path $socketDirectory -Force | Out-Null
$socketShortPath = $taskFso.GetFolder($socketDirectory).ShortPath.Replace('\', '/')
$originalJavaOptions = $env:JAVA_TOOL_OPTIONS
$originalEngineRepository = $env:FLUTTER_LOCAL_ENGINE_MAVEN
$verifiedEngineRepository = Join-Path $appDirectory '.dart_tool/verified-engine-maven'
$flutterExitCode = 1
Push-Location $appDirectory
try {
    if (Test-Path -LiteralPath (Join-Path $verifiedEngineRepository 'engine.version')) {
        $env:FLUTTER_LOCAL_ENGINE_MAVEN = $verifiedEngineRepository
    }
    $env:JAVA_TOOL_OPTIONS = "$originalJavaOptions -Djdk.net.unixdomain.tmpdir=$socketShortPath".Trim()
    if (!$FlutterArguments) { $FlutterArguments = @('--version') }
    & $flutterExecutable @FlutterArguments
    $flutterExitCode = $LASTEXITCODE
} finally {
    $env:JAVA_TOOL_OPTIONS = $originalJavaOptions
    $env:FLUTTER_LOCAL_ENGINE_MAVEN = $originalEngineRepository
    Pop-Location
}
exit $flutterExitCode
