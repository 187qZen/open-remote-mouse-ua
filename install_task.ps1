param(
  [Parameter(Mandatory=$true)][string]$Exe,
  [string]$Script = ""
)
$ErrorActionPreference = "Stop"
$user = "$env:USERDOMAIN\$env:USERNAME"
if ($Script -ne "") {
  $action = New-ScheduledTaskAction -Execute $Exe -Argument ('"' + $Script + '"') -WorkingDirectory (Split-Path -Parent $Script)
} else {
  $action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory (Split-Path -Parent $Exe)
}
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $user
# no time limit (schtasks default stops the task after 3 days) and no stop on battery
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "PCRemoteServer" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Task registered."
