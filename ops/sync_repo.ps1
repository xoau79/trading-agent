<#
.SYNOPSIS
    Keeps this machine's checkout in sync with origin/main, and restarts the dashboard
    server whenever new code lands, so localhost never silently serves stale code again.

.DESCRIPTION
    Registered as scheduled task "TradingAgent-RepoSync" (every 15 minutes -- see
    ops/register_tasks.ps1 -Only RepoSync). Each run, in order:

      1. Skips entirely if a live bot.py process is currently running from this repo.
         Never touch the on-disk code while the bot has it loaded -- switching branches
         under a live process previously corrupted the working tree and broke a
         scheduled task (see project history / CLAUDE memory for the incident).
      2. Skips if the working tree has uncommitted changes to tracked files -- never
         overwrites local work in progress.
      3. Skips if HEAD isn't on main -- a different branch checked out here is assumed
         to be intentional manual work, not something to auto-switch away from.
      4. Fetches origin. If origin/main has moved, fast-forwards main and restarts
         dashboard_server.py (via the existing TradingAgent-Dashboard task) so the new
         dashboard/API code is live within 15 minutes of merging, not "whenever someone
         happens to remember to git pull."

    Never force-pushes, never discards local changes, never `reset --hard`. If a
    fast-forward isn't possible (local main has diverged from origin), it logs the
    problem and stops rather than guessing.

    Every run appends one line to logs/repo_sync.log (skips are logged too, so a silent
    "nothing happened for days" is visible in the log rather than invisible).
#>

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogFile = Join-Path $RepoRoot "logs\repo_sync.log"

function Write-Log($msg) {
    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
}

Set-Location $RepoRoot

# 1. Never touch the working tree while the live bot has it loaded.
$botRunning = Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*$RepoRoot*bot.py*" }
if ($botRunning) {
    Write-Log "SKIP: bot.py is live (PID $($botRunning.ProcessId)) -- not touching the working tree."
    exit 0
}

# 2. Never overwrite uncommitted work (ignores untracked files -- journal/logs/etc. are
#    gitignored anyway, this only cares about changes to files git already tracks).
$dirty = git status --porcelain --untracked-files=no
if ($dirty) {
    Write-Log "SKIP: working tree has uncommitted changes to tracked files:`n$dirty"
    exit 0
}

# 3. Only auto-sync main; a different branch here is assumed intentional.
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne "main") {
    Write-Log "SKIP: currently on '$branch', not main -- leaving it alone."
    exit 0
}

git fetch origin --quiet
$behind = [int](git rev-list HEAD..origin/main --count)
if ($behind -eq 0) {
    exit 0  # already up to date -- don't spam the log every 15 minutes
}

$before = git rev-parse --short HEAD
git pull --ff-only *>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: git pull --ff-only failed -- local main may have diverged from origin. Needs a human look."
    exit 1
}
$after = git rev-parse --short HEAD
Write-Log "SYNCED: $before -> $after ($behind commit(s)) -- restarting dashboard"

# Restart so server-side (dashboard_server.py) and static (dashboard/*) changes take
# effect now instead of waiting for the next logon.
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*$RepoRoot*dashboard_server.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Sleep -Seconds 1
Start-ScheduledTask -TaskName "TradingAgent-Dashboard"
Write-Log "Dashboard restarted."
