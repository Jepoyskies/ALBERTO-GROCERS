<#
    server.ps1 - Shared dev-server control for the Alberto Grocers POS.

    This script is the ONLY sanctioned way to start/stop the Django dev server,
    because multiple AI agent sessions share this machine and port 8000.

    Usage:
        .\scripts\server.ps1 start     # idempotent: reuses a healthy server
        .\scripts\server.ps1 status
        .\scripts\server.ps1 restart
        .\scripts\server.ps1 stop

    Key behaviours:
      * start is IDEMPOTENT - if a healthy server is already up it reuses it and
        exits 0, so N sessions calling start still yield exactly ONE server.
      * The server is launched DETACHED from the calling session so it survives
        agent session restarts. Never start runserver as a session background job.
      * It will NOT kill a process it did not create; port conflicts are reported.
      * The dev server runs with TEMPLATE_CACHE=false so editing a template is
        visible on the next browser refresh. Python changes still need a restart
        (--noreload), so run: .\scripts\server.ps1 restart
#>

param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python      = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$ManagePy    = Join-Path $ProjectRoot 'alberto_system\manage.py'
$LogDir      = Join-Path $env:TEMP 'alberto_server'
$OutLog      = Join-Path $LogDir 'runserver.log'
$ErrLog      = Join-Path $LogDir 'runserver.err.log'
$ProbePath   = '/accounts/login/'   # returns 200 for anonymous users; good health probe
$BaseUrl     = "http://127.0.0.1:$Port"

# --- helpers ---------------------------------------------------------------

function Get-ServerProcesses {
    <# Returns python.exe processes running THIS project's manage.py runserver. #>
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object {
            $_.CommandLine -like '*manage.py*' -and
            $_.CommandLine -like '*runserver*' -and
            $_.CommandLine -like '*alberto_system*'
        }
}

function Get-PortOwner {
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Test-ServerAlive {
    <# TCP-level liveness. Any bound socket means the process is up. #>
    $null = Get-PortOwner
    return [bool](Get-PortOwner)
}

function Test-AppHealthy {
    <# Application-level health. Reachable HTTP response (even 500) == app is up. #>
    try {
        $null = Invoke-WebRequest -Uri "$BaseUrl$ProbePath" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return $true
    } catch {
        # An HTTP error status still proves the app responded.
        if ($_.Exception.Response) { return $true }
        return $false
    }
}

function Show-Status {
    $owner = Get-PortOwner
    $procs = @(Get-ServerProcesses)

    if (-not $owner) {
        Write-Host "[DOWN]   Nothing is listening on port $Port."
        if ($procs.Count) { Write-Host "         (stale processes present: $($procs.ProcessId -join ', '))" }
        return $false
    }

    $healthy = Test-AppHealthy
    $tag = if ($healthy) { 'HEALTHY' } else { 'UNHEALTHY' }
    Write-Host "[$tag]   Serving on $BaseUrl  (listening PID: $($owner.OwningProcess))"
    Write-Host "         PIDs: $($procs.ProcessId -join ', ')"
    Write-Host "         Logs: $OutLog"
    return $healthy
}

function Start-Server {
    if (Test-ServerAlive) {
        $healthy = Test-AppHealthy
        if ($healthy) {
            Write-Host "[OK]     A healthy server is already running on port $Port - reusing it."
            Write-Host "         No second server was started. (This is the expected multi-session behaviour.)"
            Show-Status | Out-Null
            return 0
        }

        Write-Host "[WARN]   Port $Port is occupied but the app did not respond."
        Write-Host "         Refusing to kill it (it may belong to another session)."
        Write-Host "         Ask the human before running: .\scripts\server.ps1 stop"
        return 1
    }

    if (-not (Test-Path $Python))   { Write-Host "[ERROR]  Python not found: $Python";   return 1 }
    if (-not (Test-Path $ManagePy)) { Write-Host "[ERROR]  manage.py not found: $ManagePy"; return 1 }

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    # DETACHED launch: independent of the calling agent session's lifetime.
    # --noreload avoids the extra autoreloader child process (lighter on this box).
    #
    # TEMPLATE_CACHE=false for the DEV server only: Django always wraps template
    # loaders in cached.Loader, so with --noreload a .html edit would stay invisible
    # until the next restart. Disabling the cache makes template edits show up on the
    # next browser refresh. The variable is restored immediately so it does not leak
    # into the calling shell or into any other session.
    $prevTemplateCache = $env:TEMPLATE_CACHE
    $env:TEMPLATE_CACHE = 'false'
    try {
        $proc = Start-Process -FilePath $Python `
            -ArgumentList $ManagePy, 'runserver', "$Port", '--noreload' `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $OutLog `
            -RedirectStandardError $ErrLog `
            -WindowStyle Hidden `
            -PassThru
    } finally {
        if ($null -eq $prevTemplateCache) { Remove-Item Env:TEMPLATE_CACHE -ErrorAction SilentlyContinue }
        else { $env:TEMPLATE_CACHE = $prevTemplateCache }
    }

    Write-Host "[START]  Launched detached (PID $($proc.Id)); waiting for it to accept requests..."

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-AppHealthy) {
            Write-Host "[OK]     Server is up and responding after ${i}s."
            Show-Status | Out-Null
            return 0
        }
    }

    Write-Host "[ERROR]  Server did not become healthy within 30s."
    Write-Host "         Check $ErrLog"
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 20 }
    return 1
}

function Stop-Server {
    $procs = @(Get-ServerProcesses)
    if (-not $procs.Count) {
        Write-Host "[OK]     No project server processes are running."
        return 0
    }

    Write-Host "[STOP]   Stopping $($procs.Count) process(es): $($procs.ProcessId -join ', ')"
    Write-Host "         NOTE: this is shared infrastructure - other sessions lose their server too."
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Show-Status | Out-Null
    return 0
}

# --- dispatch --------------------------------------------------------------

switch ($Action) {
    'start'   { exit (Start-Server) }
    'stop'    { exit (Stop-Server) }
    'restart' { Stop-Server | Out-Null; exit (Start-Server) }
    'status'  { if (Show-Status) { exit 0 } else { exit 1 } }
}
