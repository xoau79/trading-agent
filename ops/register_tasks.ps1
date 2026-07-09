<#
.SYNOPSIS
    Reproducible Windows Task Scheduler setup for the trading agent. Replaces one-off manual
    task creation so the automation can be rebuilt identically on any machine (or after this
    one is reimaged) straight from the repo.

.DESCRIPTION
    Registers/updates tasks, all running as the current user, all pointed at pythonw.exe
    (no console window) inside this repo's working directory:
      - TradingAgent-Asia        weekdays, Asian session
      - TradingAgent-NY          weekdays, New York session
      - TradingAgent-Dashboard   at logon, keeps the dashboard server running
      - TradingAgent-Watchdog    weekdays every 15 min, Discord alert if a session goes dead
      - TradingAgent-DigestAsia  weekdays, Discord summary after the Asian session closes
      - TradingAgent-DigestNY    weekdays (next morning), Discord summary after New York closes
      - TradingAgent-SmokeTest   weekdays, external feed health check -> Discord on failure
      - TradingAgent-WeeklyReport  Sunday evening, Discord stats/tuning-gate/suggestion report
      - TradingAgent-SuggestionEvidence  Sunday evening (after WeeklyReport), backtests each
                                          pending suggestion current-vs-proposed -> Discord

    Safe to re-run: every task is registered with -Force, so re-running this script just
    re-applies the same definition rather than erroring on "already exists".

.PARAMETER Only
    Optional: register a single task by short name (Asia, NY, Dashboard, Watchdog, DigestAsia,
    DigestNY, SmokeTest, WeeklyReport, SuggestionEvidence) instead of all of them.

.EXAMPLE
    # Add just the dashboard task to an existing setup, without touching the rest:
    .\ops\register_tasks.ps1 -Only Dashboard
#>
param(
    [ValidateSet("Asia", "NY", "Dashboard", "Watchdog", "DigestAsia", "DigestNY",
                 "SmokeTest", "WeeklyReport", "SuggestionEvidence")]
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
    param($Name, $ScriptArgs, $StartTime,
          $DaysOfWeek = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"),
          $ExecutionTimeLimit = (New-TimeSpan -Hours 10))
    $action = New-ScheduledTaskAction -Execute $PythonW `
        -Argument "`"$RepoRoot\$ScriptArgs`"" -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $StartTime
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit $ExecutionTimeLimit `
        -MultipleInstances IgnoreNew -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings `
        -Force | Out-Null
    Write-Host "Registered $Name"
}

function Register-RepeatingTask {
    # Runs every day (weekends included -- the script itself is a no-op when no session is
    # live, and Friday-night New York sessions spill into Saturday morning Sydney time, so a
    # weekday-only trigger would leave that spillover unwatched), every $IntervalMinutes,
    # around the clock.
    param($Name, $ScriptArgs, $IntervalMinutes, $ExecutionTimeLimit = (New-TimeSpan -Minutes 5))
    $action = New-ScheduledTaskAction -Execute $PythonW `
        -Argument "`"$RepoRoot\$ScriptArgs`"" -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At "00:00"
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "00:00" `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit $ExecutionTimeLimit `
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
    # Posts to Discord the moment a live session's dashboard/data.js goes stale (or the bot's
    # own status reports an emergency/aborted stop) -- see ops/watchdog.py's docstring for why
    # this exists (the in-process dead-man's-switch was removed in PR #6).
    Register-RepeatingTask -Name "TradingAgent-Watchdog" -ScriptArgs "ops\watchdog.py" `
        -IntervalMinutes 15
}
if (-not $Only -or $Only -eq "DigestAsia") {
    # 16:15 Sydney is safely after the Asian session's close in both AEST (~15:00) and AEDT
    # (~16:00) -- see config.json's sessions.asia.open_time_note for the DST rationale.
    Register-BotTask -Name "TradingAgent-DigestAsia" -ScriptArgs "ops\session_digest.py`" --session asia" `
        -StartTime "16:15" -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
}
if (-not $Only -or $Only -eq "DigestNY") {
    # New York closes ~06:00 Sydney the NEXT calendar day, so this runs the morning after each
    # weeknight session -- Tuesday through Saturday, one day later than the NY task's own
    # Mon-Fri trigger (a Friday-night session spills into Saturday morning). 06:30 gives a
    # safe margin; ops/session_digest.py works out the right day_key/log file itself, so the
    # exact trigger time only needs to be "after close," never an exact date.
    Register-BotTask -Name "TradingAgent-DigestNY" -ScriptArgs "ops\session_digest.py`" --session newyork" `
        -StartTime "06:30" -DaysOfWeek Tuesday,Wednesday,Thursday,Friday,Saturday `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
}
if (-not $Only -or $Only -eq "SmokeTest") {
    # Before the Asian session's 10:30 launch: confirms every external feed (Yahoo, ForexFactory,
    # CNBC RSS, TradingView) is reachable today, posting to Discord only on failure.
    Register-BotTask -Name "TradingAgent-SmokeTest" -ScriptArgs "ops\smoke_test.py`" --discord" `
        -StartTime "10:00" -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
}
if (-not $Only -or $Only -eq "WeeklyReport") {
    Register-BotTask -Name "TradingAgent-WeeklyReport" -ScriptArgs "ops\weekly_report.py" `
        -StartTime "18:00" -DaysOfWeek Sunday -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
}
if (-not $Only -or $Only -eq "SuggestionEvidence") {
    # 18:30, after WeeklyReport. suggestion_evidence.py runs two sandboxed backtests (30 min
    # subprocess timeout each -- see ops/suggestion_evidence.py's _run_backtest()) per pending
    # suggestion, so a single suggestion alone can take up to ~1h; three hours gives headroom
    # for more than one pending suggestion in the same run without Task Scheduler killing it
    # mid-way and silently dropping evidence for whatever's left. A no-op (prints "nothing to
    # evidence" and exits immediately) when nothing is pending.
    Register-BotTask -Name "TradingAgent-SuggestionEvidence" -ScriptArgs "ops\suggestion_evidence.py" `
        -StartTime "18:30" -DaysOfWeek Sunday -ExecutionTimeLimit (New-TimeSpan -Hours 3)
}
