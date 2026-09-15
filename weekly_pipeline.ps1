# --- OpenAlex Weekly Robot (v2): catch-up -> rebuild -> ML -> export -> GitHub
# Task Scheduler -> Program: powershell.exe
#                   Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\projects\openalex-pattern-miner\weekly_pipeline.ps1"
#
# Replaces train_weekly.ps1. Steps:
#   1. CATCH-UP download: papers from the last 3 years that match $CORPUS_ARGS.
#      Why: with --min-cited 20, a 2025 paper is invisible until it collects
#      20 citations, which can take months. Re-scanning 3 years once a week
#      picks it up the week it crosses the line. (~a few hundred API calls;
#      the free key allows about 10,000 list calls per day.)
#   2. rebuild database + re-mine patterns (whole corpus AND per country)
#   3. retrain link prediction
#   4. export small results (CSV/JSON/PNG) into docs/
#   5. commit + push docs/ to GitHub   (skip with:  -NoPush)

param([switch]$NoPush)

. "$PSScriptRoot\pipeline_common.ps1"

$LOG = Join-Path $LOG_DIR ("weekly_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
Write-Log $LOG "=== weekly run started ==="

if (-not (Test-Prerequisites $LOG)) { exit 1 }
if (-not (Enter-Lock $LOG)) { exit 0 }

try {
    Import-DotEnv

    # 1. catch-up download (exit 2 = nothing new is fine, we still rebuild/export)
    $refreshArgs = @('refresh.py', '--sync-mode', 'published',
                     '--lookback-days', '1095', '--output', $JSONL_PATH) + $CORPUS_ARGS
    $code = Invoke-Python $LOG $refreshArgs
    if ($code -eq 1) {
        Write-Log $LOG "refresh.py FAILED. Continuing with the data already on disk."
    }

    # 2. rebuild + mine
    $code = Invoke-Python $LOG @('build_db.py', '--input', $JSONL_PATH, '--db', $DB_PATH)
    if ($code -ne 0) { Write-Log $LOG "build_db.py FAILED (exit $code)"; exit 1 }

    $code = Invoke-Python $LOG (@('mine_windows.py') + $MINE_ARGS)
    if ($code -ne 0) { Write-Log $LOG "mine_windows.py FAILED (exit $code)"; exit 1 }

    # per-country patterns for the country dropdown in the app
    $code = Invoke-Python $LOG @('mine_countries.py', '--db', $DB_PATH)
    if ($code -ne 0) { Write-Log $LOG "mine_countries.py FAILED (exit $code)"; exit 1 }

    # 3. link prediction
    $code = Invoke-Python $LOG @('linkpred.py', '--db', $DB_PATH, '--graph-split', "$SPLIT_YEAR")
    if ($code -ne 0) { Write-Log $LOG "linkpred.py FAILED (exit $code)"; exit 1 }

    # 4. export the small, shareable results
    $code = Invoke-Python $LOG @('export_snapshot.py', '--db', $DB_PATH, '--out', 'docs')
    if ($code -ne 0) { Write-Log $LOG "export_snapshot.py FAILED (exit $code)"; exit 1 }

    # 5. publish
    if ($NoPush) {
        Write-Log $LOG "-NoPush given: skipping GitHub."
    } else {
        & "$PSScriptRoot\publish_github.ps1" -LogFile $LOG
        if ($LASTEXITCODE -ne 0) { Write-Log $LOG "GitHub push FAILED"; exit 1 }
    }

    Write-Log $LOG "=== weekly run finished OK ==="
    exit 0
}
finally {
    Exit-Lock
    Remove-OldLogs
}
