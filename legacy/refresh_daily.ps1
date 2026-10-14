# --- OpenAlex Daily Data Robot (v2) ----------------------------------------
# Task Scheduler -> Program: powershell.exe
#                   Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\projects\openalex-pattern-miner\refresh_daily.ps1"
#
# What it does:
#   1. downloads papers from the last 45 days that match $CORPUS_ARGS
#      (duplicates are skipped, so re-scanning is safe and catches late arrivals)
#   2. only if something new arrived: rebuild the database and re-mine patterns
#
# refresh.py exit codes:  0 = new data, 2 = nothing new, 1 = failure.

. "$PSScriptRoot\pipeline_common.ps1"

$LOG = Join-Path $LOG_DIR ("daily_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
Write-Log $LOG "=== daily run started ==="

if (-not (Test-Prerequisites $LOG)) { exit 1 }
if (-not (Enter-Lock $LOG)) { exit 0 }

try {
    Import-DotEnv
    if (-not $env:OPENALEX_API_KEY) { Write-Log $LOG "WARNING: OPENALEX_API_KEY missing from .env" }
    if (-not $env:OPENALEX_MAILTO)  { Write-Log $LOG "WARNING: OPENALEX_MAILTO missing from .env" }

    $refreshArgs = @('refresh.py', '--sync-mode', 'published',
                     '--lookback-days', '45', '--output', $JSONL_PATH) + $CORPUS_ARGS
    $code = Invoke-Python $LOG $refreshArgs

    if ($code -eq 2) {
        Write-Log $LOG "No new works today; nothing to rebuild."
        exit 0
    }
    if ($code -ne 0) {
        Write-Log $LOG "refresh.py FAILED (exit $code). Read the lines above."
        exit 1
    }

    Write-Log $LOG "New data found. Rebuilding the database..."
    $code = Invoke-Python $LOG @('build_db.py', '--input', $JSONL_PATH, '--db', $DB_PATH)
    if ($code -ne 0) { Write-Log $LOG "build_db.py FAILED (exit $code)"; exit 1 }

    $code = Invoke-Python $LOG (@('mine_windows.py') + $MINE_ARGS)
    if ($code -ne 0) { Write-Log $LOG "mine_windows.py FAILED (exit $code)"; exit 1 }

    $code = Invoke-Python $LOG @('mine_countries.py', '--db', $DB_PATH)
    if ($code -ne 0) { Write-Log $LOG "mine_countries.py FAILED (exit $code)"; exit 1 }

    Write-Log $LOG "=== daily run finished OK ==="
    exit 0
}
finally {
    Exit-Lock
    Remove-OldLogs
}
