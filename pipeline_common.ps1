# --- Shared settings and helpers for the scheduled jobs ---------------------
# Dot-source this file:   . "$PSScriptRoot\pipeline_common.ps1"
#
# EDIT ONLY THE "SETTINGS" BLOCK. Everything else is plumbing.

# ============================== SETTINGS ====================================
$PROJECT_ROOT = "C:\projects\openalex-pattern-miner"

# The ONE definition of your corpus. It must match how works_real.jsonl was
# first downloaded (python check_corpus.py tells you). Both the daily and the
# weekly job use exactly these filters, so the dataset never gets mixed.
#   AI subfield, cited 20+  ->  @('--subfield-id', '1702', '--min-cited', '20')
#   All of CS, cited 20+    ->  @('--min-cited', '20')
$CORPUS_ARGS = @('--subfield-id', '1702', '--min-cited', '20')

$DB_PATH     = "data\openalex.duckdb"
$JSONL_PATH  = "data\works_real.jsonl"
$MINE_ARGS   = @('--db', $DB_PATH, '--min-support', '0.005')
$SPLIT_YEAR  = 2021
$KEEP_LOG_DAYS = 30
# ============================================================================

$PYTHON_EXE = Join-Path $PROJECT_ROOT ".venv\Scripts\python.exe"
$LOG_DIR    = Join-Path $PROJECT_ROOT "logs"
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null
Set-Location $PROJECT_ROOT

# Python prints UTF-8 even when its output goes to a file instead of a console.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# IMPORTANT: "Continue", not "Stop". In Windows PowerShell 5.1 (the one Task
# Scheduler starts), "Stop" turns ANY line a program writes to stderr - even a
# harmless warning - into a fatal error. We check exit codes ourselves instead.
$ErrorActionPreference = "Continue"

function Write-Log([string]$LogFile, [string]$Text) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Import-DotEnv {
    # Scheduled tasks start with an empty environment: load .env ourselves.
    $envFile = Join-Path $PROJECT_ROOT ".env"
    if (-not (Test-Path $envFile)) { return }
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$') {
            $val = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($matches[1], $val, "Process")
        }
    }
}

function Invoke-Python([string]$LogFile, [string[]]$PyArgs) {
    # Runs python, copies stdout AND stderr into the log, returns the exit code.
    $out = Join-Path $LOG_DIR "_last_stdout.txt"
    $err = Join-Path $LOG_DIR "_last_stderr.txt"
    Write-Log $LogFile ("RUN  python " + ($PyArgs -join ' '))
    $p = Start-Process -FilePath $PYTHON_EXE -ArgumentList $PyArgs `
            -WorkingDirectory $PROJECT_ROOT -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $out -RedirectStandardError $err
    Get-Content $out -Encoding UTF8 | Add-Content -Path $LogFile -Encoding UTF8
    Get-Content $err -Encoding UTF8 | Add-Content -Path $LogFile -Encoding UTF8
    Write-Log $LogFile ("EXIT {0}" -f $p.ExitCode)
    return $p.ExitCode
}

function Enter-Lock([string]$LogFile) {
    # Stops the daily and weekly jobs from rebuilding the database at the same
    # time. A lock older than 6 hours is treated as left over from a crash.
    $lock = Join-Path $LOG_DIR "pipeline.lock"
    if (Test-Path $lock) {
        $age = (Get-Date) - (Get-Item $lock).LastWriteTime
        if ($age.TotalHours -lt 6) {
            Write-Log $LogFile "Another job is running (logs\pipeline.lock). Exiting."
            return $false
        }
    }
    Set-Content -Path $lock -Value $PID
    return $true
}

function Exit-Lock {
    Remove-Item (Join-Path $LOG_DIR "pipeline.lock") -ErrorAction SilentlyContinue
}

function Remove-OldLogs {
    Get-ChildItem $LOG_DIR -Filter "*.log" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KEEP_LOG_DAYS) } |
        Remove-Item -ErrorAction SilentlyContinue
}

function Test-Prerequisites([string]$LogFile) {
    if (-not (Test-Path $PYTHON_EXE)) {
        Write-Log $LogFile "python.exe not found at $PYTHON_EXE - is the venv created?"
        return $false
    }
    # Streamlit runs inside python.exe, so look at the command line, not the name.
    $streamlit = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*streamlit*" }
    if ($streamlit) {
        Write-Log $LogFile "WARNING: Streamlit is running. It may lock $DB_PATH and make the rebuild fail."
    }
    return $true
}
