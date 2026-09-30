<#
    verify.ps1 - One-command greenlight health check for the Alberto Grocers POS.

    Read-only. Safe to run at any time, from any session, while the server is up.
    It never modifies code, never touches the database, and never starts/stops
    the dev server.

    Usage:
        .\scripts\verify.ps1
#>

$ErrorActionPreference = 'Continue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python      = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$ManagePy    = Join-Path $ProjectRoot 'alberto_system\manage.py'
$BaseUrl     = 'http://127.0.0.1:8000'

$script:Failures = 0
$script:Warnings = 0

function Write-Head {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Pass { param($m) Write-Host "  [PASS] $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  [WARN] $m" -ForegroundColor Yellow; $script:Warnings++ }
function Fail { param($m) Write-Host "  [FAIL] $m" -ForegroundColor Red;   $script:Failures++ }

function Test-Page {
    param($Path, $Expect = 200, $Name = $Path)
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl$Path" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        if ($r.StatusCode -eq $Expect) { Pass "$Name -> $($r.StatusCode)" }
        else { Fail "$Name -> $($r.StatusCode) (expected $Expect)" }
    } catch {
        if ($_.Exception.Response) { Fail "$Name -> HTTP $([int]$_.Exception.Response.StatusCode)" }
        else { Fail "$Name -> unreachable: $($_.Exception.Message)" }
    }
}

Write-Host "Alberto Grocers POS - health check" -ForegroundColor Cyan
Write-Host "Root: $ProjectRoot"

# --- 1. Environment -------------------------------------------------------
Write-Head "1. Environment"
if (Test-Path $Python)   { Pass "venv python present" }        else { Fail "venv python MISSING: $Python" }
if (Test-Path $ManagePy) { Pass "manage.py present" }          else { Fail "manage.py MISSING: $ManagePy" }
if (Test-Path (Join-Path $ProjectRoot 'alberto_system\.env')) { Pass ".env present" } else { Warn ".env missing" }
if (Test-Path (Join-Path $ProjectRoot 'alberto_system\db.sqlite3')) { Pass "db.sqlite3 present" } else { Fail "db.sqlite3 MISSING" }
if (Test-Path (Join-Path $ProjectRoot 'richland_inventory')) {
    Fail "stale 'richland_inventory' folder exists again - it will confuse BASE_DIR resolution"
} else { Pass "no stale richland_inventory folder" }

# --- 2. Django ------------------------------------------------------------
Write-Head "2. Django system check"
if (Test-Path $Python) {
    $out = & $Python $ManagePy check 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { Pass "manage.py check clean" }
    else { Fail "manage.py check reported issues:`n$out" }

    $out = & $Python $ManagePy makemigrations --check --dry-run 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { Pass "no model changes missing a migration" }
    else { Fail "model changes without a migration:`n$out" }

    $out = & $Python $ManagePy showmigrations 2>&1 | Out-String
    $unapplied = @($out -split "`n" | Where-Object { $_ -match '\[ \]' })
    if ($unapplied.Count -eq 0) { Pass "all migrations applied" }
    else { Fail "$($unapplied.Count) unapplied migration(s):`n$($unapplied -join "`n")" }
}

# --- 3. Server ------------------------------------------------------------
Write-Head "3. Dev server"
$port = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port) {
    Pass "port 8000 listening (PID $($port.OwningProcess))"
    $procs = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like '*alberto_system*' -and $_.CommandLine -like '*runserver*' })
    if ($procs.Count -le 2) { Pass "server process count sane ($($procs.Count))" }
    else { Warn "$($procs.Count) runserver processes - possible duplicates on port 8000" }
    if ($procs | Where-Object { $_.CommandLine -like '*richland_inventory*' }) {
        Fail "a runserver process is using the DELETED richland_inventory path - its BASE_DIR is invalid"
    } else { Pass "all runserver processes use alberto_system" }
} else {
    Warn "dev server is DOWN - start it with: .\scripts\server.ps1 start"
}

# --- 4. HTTP smoke test ---------------------------------------------------
Write-Head "4. HTTP smoke test"
if ($port) {
    Test-Page '/accounts/login/' 200 'login page'
    Test-Page '/'                200 'home page'
    Test-Page '/admin/login/'     200 'admin login'
    Test-Page '/api/docs/'        200 'swagger api docs'
} else {
    Warn "skipped - server is not running"
}

# --- 5. Tests -------------------------------------------------------------
Write-Head "5. Test suite"
if (Test-Path $Python) {
    $out = & $Python -m pytest -q 2>&1 | Out-String
    $tail = ($out -split "`n" | Where-Object { $_ -match 'passed|failed|error' } | Select-Object -Last 1)
    if ($LASTEXITCODE -eq 0) { Pass "pytest: $($tail.Trim())" }
    else { Fail "pytest failing: $($tail.Trim())" }
}

# --- Summary --------------------------------------------------------------
Write-Host "`n================================" -ForegroundColor Cyan
if ($script:Failures -eq 0) {
    Write-Host " GREENLIGHT  - 0 failures, $script:Warnings warning(s)" -ForegroundColor Green
    Write-Host " Ready for real work." -ForegroundColor Green
} else {
    Write-Host " NOT GREEN  - $($script:Failures) failure(s), $script:Warnings warning(s)" -ForegroundColor Red
}
Write-Host "================================" -ForegroundColor Cyan

exit $script:Failures
