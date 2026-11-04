$ErrorActionPreference = "Stop"

$taskName = "BITORA-Phase63-Certification-33c13cf"
$launcher = "C:\Users\Noxie-PC\.codex\worktrees\bitora-qr-latency-phase-6-2\qr white label\auditoria\bitora_5_8_2_phase_6_3\launch_phase63_campaign.ps1"
$powershell = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launcher`""
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$task = New-ScheduledTask -Action $action -Settings $settings -Principal $principal `
    -Description "BITORA 5.8.2 Phase 6.3 QR/APB autonomous lab certification; manual start only"
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Output $taskName
