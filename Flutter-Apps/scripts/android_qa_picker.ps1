param([int]$Minutes=20)
$ErrorActionPreference='Stop'
$qaAdb='C:/Users/Sai Satish/AppData/Local/Android/Sdk/platform-tools/adb.exe'
$qaDeadline=(Get-Date).AddMinutes($Minutes)
$qaDump='/sdcard/pms-qa-picker.xml'
function Click-QaNode($node) {
  if ($null -eq $node) { return $false }
  $qaBounds=[regex]::Match($node.bounds,'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
  if (!$qaBounds.Success) { return $false }
  $qaX=[int](([int]$qaBounds.Groups[1].Value+[int]$qaBounds.Groups[3].Value)/2)
  $qaY=[int](([int]$qaBounds.Groups[2].Value+[int]$qaBounds.Groups[4].Value)/2)
  & $qaAdb -s Q8G6ZLF6NR69Q85D shell input tap $qaX $qaY | Out-Null
  return $true
}
while ((Get-Date) -lt $qaDeadline) {
  $qaFocus=(& $qaAdb -s Q8G6ZLF6NR69Q85D shell dumpsys window | Select-String 'mCurrentFocus') -join ' '
  $qaCheckpoint=(& $qaAdb -s Q8G6ZLF6NR69Q85D exec-out run-as com.businesssuite.business_suite_mobile cat app_flutter/full-pms-checkpoint.json 2>$null) -join "`n"
  if ($qaCheckpoint.StartsWith('{')) {
    try { $null=$qaCheckpoint | ConvertFrom-Json; Set-Content -LiteralPath '.dart_tool/full-pms-live-checkpoint.json' -Value $qaCheckpoint } catch { }
  }
  if ($qaFocus -match 'com\.(google\.)?android\.documentsui') {
    & $qaAdb -s Q8G6ZLF6NR69Q85D shell uiautomator dump $qaDump 2>$null | Out-Null
    $qaXmlText=& $qaAdb -s Q8G6ZLF6NR69Q85D shell cat $qaDump
    try { [xml]$qaXml=$qaXmlText -join "`n" } catch { Start-Sleep -Seconds 1; continue }
    $qaFile=$qaXml.SelectSingleNode("//node[@text='PMS-QA-upload.txt']")
    if ($qaFocus -match 'PickActivity|FilesActivity' -and (Click-QaNode $qaFile)) {
      Write-Output "$(Get-Date -Format o) selected QA upload fixture"
    } elseif ($qaFocus -match 'FilesActivity|PickActivity') {
      $qaDownloads=$qaXml.SelectSingleNode("//node[@text='Downloads']")
      $qaRoots=$qaXml.SelectSingleNode("//node[@content-desc='Show roots']")
      if (Click-QaNode $qaDownloads) { } elseif (Click-QaNode $qaRoots) { }
    }
    if ($qaFocus -match 'CreateActivity') {
      if ($qaXmlText -match 'PMS-QA-upload' -and (Click-QaNode ($qaXml.SelectSingleNode("//node[@text='Replace' or @text='REPLACE']")))) { continue }
      $qaName=$qaXml.SelectSingleNode("//node[@resource-id='android:id/text1' or @class='android.widget.EditText']")
      if ($null -ne $qaName -and $qaName.text -match '^(pms-|PMS-QA)') {
        $qaSave=$qaXml.SelectSingleNode("//node[@text='SAVE' or @text='Save']")
        if (Click-QaNode $qaSave) { Write-Output "$(Get-Date -Format o) saved PMS QA download" }
      }
    }
  }
  Start-Sleep -Seconds 2
}
