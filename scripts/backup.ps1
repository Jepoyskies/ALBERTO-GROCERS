<#
    backup.ps1 - Consistent, verified backup of the local SQLite database.

    WHY THIS EXISTS: the system is local-only, so alberto_system\db.sqlite3 is the
    ONLY copy of the shop's data. A disk failure, a bad migration, or an accidental
    deletion loses everything - there is no cloud copy and no hosting provider to
    restore from. This is the cheapest insurance in the project.

    Usage:
        .\scripts\backup.ps1                # back up, verify, keep the newest 14
        .\scripts\backup.ps1 -Keep 30       # keep more history
        .\scripts\backup.ps1 -List          # list existing backups, make nothing
        .\scripts\backup.ps1 -Restore .\backups\db-20260930-120000.sqlite3

    DESIGN NOTES:
      * It uses SQLite's ONLINE BACKUP API (sqlite3.Connection.backup), not a file
        copy. A plain copy of a live database can capture a half-written transaction;
        the backup API is safe to run while the dev server is serving requests.
      * Every backup is verified with PRAGMA integrity_check before being kept. An
        unverified backup is not a backup.
      * Read-only with respect to the live database. It never writes to db.sqlite3.
#>

param(
    [int]$Keep = 14,
    [switch]$List,
    [string]$Restore
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python      = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$DbPath      = Join-Path $ProjectRoot 'alberto_system\db.sqlite3'
$BackupDir   = Join-Path $ProjectRoot 'backups'

function Get-Backups {
    if (-not (Test-Path $BackupDir)) { return @() }
    return @(Get-ChildItem -Path $BackupDir -Filter 'db-*.sqlite3' -File -ErrorAction SilentlyContinue |
             Sort-Object Name -Descending)
}

if ($Restore) {
    if (-not (Test-Path $Restore)) { Write-Host "[ERROR]  No such backup: $Restore"; exit 1 }
    if (-not (Test-Path $DbPath))   { Write-Host "[ERROR]  No database to restore into: $DbPath"; exit 1 }

    # Refuse to clobber the live database without an explicit, unmissable confirmation.
    Write-Host "[DANGER] This OVERWRITES the live database:" -ForegroundColor Red
    Write-Host "           $DbPath"
    Write-Host "         from backup: $Restore"
    Write-Host "         The running server holds the old file open - stop it first:"
    Write-Host "           .\scripts\server.ps1 stop"
    $answer = Read-Host "         Type YES to continue"
    if ($answer -cne 'YES') { Write-Host "[ABORT]  Cancelled - nothing was changed."; exit 1 }

    Copy-Item -Path $Restore -Destination $DbPath -Force
    Write-Host "[OK]     Restored. Start the server again: .\scripts\server.ps1 start"
    exit 0
}

if ($List) {
    $items = Get-Backups
    if (-not $items.Count) { Write-Host "[INFO]   No backups yet in $BackupDir"; exit 0 }
    Write-Host "Backups in $BackupDir :"
    $items | ForEach-Object {
        Write-Host ("  {0}  {1,8:N0} bytes  {2}" -f $_.Name, $_.Length, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))
    }
    exit 0
}

if (-not (Test-Path $Python)) { Write-Host "[ERROR]  Python not found: $Python"; exit 1 }
if (-not (Test-Path $DbPath)) { Write-Host "[ERROR]  Database not found: $DbPath"; exit 1 }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$py = @'
import sqlite3, sys, os, datetime

src_path, out_dir, keep = sys.argv[1], sys.argv[2], int(sys.argv[3])
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
dest = os.path.join(out_dir, 'db-%s.sqlite3' % stamp)

src = sqlite3.connect(src_path)
try:
    dst = sqlite3.connect(dest)
    try:
        # Online backup API: consistent snapshot even while the server is writing.
        src.backup(dst)
        # Verify the copy before we trust it.
        result = dst.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        dst.close()
finally:
    src.close()

if result != 'ok':
    os.remove(dest)
    print('FAILED: integrity_check said %r' % result)
    sys.exit(1)

# Prune old backups, newest first.
existing = sorted(
    (f for f in os.listdir(out_dir) if f.startswith('db-') and f.endswith('.sqlite3')),
    reverse=True)
removed = 0
for old in existing[keep:]:
    os.remove(os.path.join(out_dir, old))
    removed += 1

print('OK\t%s\t%d\t%d' % (dest, os.path.getsize(dest), removed))
'@

$result = & $Python -c $py $DbPath $BackupDir $Keep 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR]  Backup failed: $result" -ForegroundColor Red
    exit 1
}

$parts = ($result | Select-Object -Last 1) -split "`t"
$sizeKb = [math]::Round(([double]$parts[2]) / 1KB, 1)
Write-Host "[OK]     Backup verified (integrity_check = ok)"
Write-Host "         $((Split-Path -Leaf $parts[1]))  ($sizeKb KB)"
if ([int]$parts[3] -gt 0) { Write-Host "         Pruned $($parts[3]) old backup(s), keeping newest $Keep" }
Write-Host "         Restores with: .\scripts\backup.ps1 -Restore $($parts[1])"
exit 0
