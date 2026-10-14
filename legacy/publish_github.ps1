# --- Commit and push the weekly snapshot to GitHub -------------------------
# Called by weekly_pipeline.ps1, but you can run it by hand too:
#   powershell -ExecutionPolicy Bypass -File .\publish_github.ps1
#
# It ONLY stages docs/ and README.md. Raw data (data/, *.jsonl, *.duckdb) and
# .env are never added, even by accident.

param([string]$LogFile = "")

$PROJECT_ROOT = "C:\projects\openalex-pattern-miner"
Set-Location $PROJECT_ROOT
$ErrorActionPreference = "Continue"
if (-not $LogFile) {
    New-Item -ItemType Directory -Force -Path "logs" | Out-Null
    $LogFile = Join-Path $PROJECT_ROOT ("logs\publish_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
}

function Say([string]$t) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $t
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Invoke-Git([string[]]$GitArgs) {
    # NOTE: this function must NOT be named "Git" - PowerShell names are
    # case-insensitive, so it would call itself forever instead of git.exe
    $output = & git.exe @GitArgs 2>&1 | Out-String
    if ($output.Trim()) { Add-Content -Path $LogFile -Value $output.TrimEnd() -Encoding UTF8 }
    return $LASTEXITCODE
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Say "git is not installed / not on PATH"; exit 1 }

# Safety net: refuse to continue if a secret or big data file is tracked.
$tracked = & git ls-files 2>$null
$bad = $tracked | Where-Object { $_ -match '(^|/)\.env$' -or $_ -match '\.(jsonl|duckdb|sqlite)$' }
if ($bad) {
    Say "STOP: these files are tracked by git and must not be: $($bad -join ', ')"
    Say "Fix with: git rm --cached <file>   (see the guide, Part 6)"
    exit 1
}

if ((Invoke-Git @('pull', '--rebase', '--autostash')) -ne 0) { Say "git pull failed"; exit 1 }
Invoke-Git @('add', '--', 'docs', 'README.md') | Out-Null

& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Say "Nothing changed since last week; no commit."
    exit 0
}

$msg = "Weekly data snapshot {0}" -f (Get-Date -Format "yyyy-MM-dd")
if ((Invoke-Git @('commit', '-m', $msg)) -ne 0) { Say "git commit failed"; exit 1 }
if ((Invoke-Git @('push')) -ne 0) { Say "git push failed (login expired? run 'git push' by hand once)"; exit 1 }
Say "Pushed: $msg"
exit 0
