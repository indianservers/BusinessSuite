$ErrorActionPreference='Stop'
$qaAdb='C:/Users/Sai Satish/AppData/Local/Android/Sdk/platform-tools/adb.exe'
$qaOriginal=(Get-Content -LiteralPath (Join-Path $PSScriptRoot '../.dart_tool/full-pms-original-stayawake.txt') -Raw).Trim()
if ($qaOriginal -notmatch '^\d+$') { throw 'Saved setting is invalid; no device setting was changed.' }
$qaDevices=(& $qaAdb devices) -join "`n"
if ($qaDevices -notmatch 'Q8G6ZLF6NR69Q85D\s+device') { throw 'Phone is unavailable; USB stay-awake restoration is still pending.' }
& $qaAdb -s Q8G6ZLF6NR69Q85D shell settings put global stay_on_while_plugged_in $qaOriginal
& $qaAdb -s Q8G6ZLF6NR69Q85D shell settings get global stay_on_while_plugged_in
