<#
.SYNOPSIS
    Reproducible Windows Task Scheduler setup for the trading agent. Replaces one-off manual
    task creation so the automation can be rebuilt identically on any machine (or after this
    one is reimaged) straight from the repo.

.DESCRIPTION
    Registers/updates four tasks, all running as the current user, all pointed at pythonw.exe
    (no console window) inside this repo's working directory:
      - TradingAgent-Asia       weekdays, Asian session
      - TradingAgent-NY         weekdays, New York session
      - TradingAgent-Dashboard  at logon, keeps the dashboard server running
      - TradingAgent-Watchdog   every 5 minutes, dead-man's-switch (see ops/watchdog.py)

    Safe to re-run: every task is registered with -Force, so re-running this script just
    re-applies the same definition rather than erroring on "already exists".

.PARAMETER Only
    Optional: register a single task by short name (Asia, NY, Dashboard, Watchdog) instead of
    all four. Useful for adding Watchdog to a machine that already has the other three set up
    by hand, without touching (and risking) the ones already running correctly.

.EXAMPLE
    # Add just the new watchdog task to an existing setup, without touching Asia/NY/Dashboard:
    .\ops\register_tasks.ps1 -Only Watchdog
#>
param(
    [ValidateSet("Asia", "NY", "Dashboard", "Watchdog")]
    [string]$Only
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonW = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\pythonw.exe"
if (-not (Test-Path $PythonW)) {
    # Fall back to whatever pythonw is on PATH if the pinned interpreter path doesn't exist
    # on this machine.
    $PythonW = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
    if (-not $PythonW) { throw "pythonw.exe not found - set `$PythonW manually at the top of this script." }
}

function Register-BotTask {
    param($Name, $ScriptArgs, $StartTime)
    $action = New-ScheduledTaskAction -Execute $PythonW `
        -Argument "`"$RepoRoot\$ScriptArgs`"" -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
        -At $StartTime
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
        -MultipleInstances IgnoreNew -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings `
        -Force | Out-Null
    Write-Host "Registered $Name"
}

if (-not $Only -or $Only -eq "Asia") {
    # 10:30 AM Sydney is a fixed local wall-clock trigger, but the session itself is
    # anchored to 10:00 JST (Asia/Tokyo, no DST) -- config.json's sessions.asia.open_time_note
    # has the full rationale. That JST anchor lands at ~11:00 Sydney during AEST (30 min lead,
    # matching bot.py's "~30 min before" comment) and ~12:00 Sydney during AEDT (1.5h lead,
    # still safe -- bot.py just waits longer). Nothing to adjust twice a year: bot.py works out
    # the exact open itself via zoneinfo every run.
    Register-BotTask -Name "TradingAgent-Asia" -ScriptArgs "bot.py`" --session asia" -StartTime "10:30"
}
if (-not $Only -or $Only -eq "NY") {
    Register-BotTask -Name "TradingAgent-NY" -ScriptArgs "bot.py`" --session newyork" -StartTime "23:30"
}
if (-not $Only -or $Only -eq "Dashboard") {
    $action = New-ScheduledTaskAction -Execute $PythonW `
        -Argument "`"$RepoRoot\dashboard_server.py`"" -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName "TradingAgent-Dashboard" -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null
    Write-Host "Registered TradingAgent-Dashboard"
}
if (-not $Only -or $Only -eq "Watchdog") {
    $action = New-ScheduledTaskAction -Execute $PythonW `
        -Argument "`"$RepoRoot\ops\watchdog.py`"" -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
        -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName "TradingAgent-Watchdog" -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null
    Write-Host "Registered TradingAgent-Watchdog (every 5 min)"
}
