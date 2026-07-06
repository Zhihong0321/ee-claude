# One-time setup: creates a dedicated PostgreSQL role + database for the
# EE Finance Agent app, on the existing local PostgreSQL 18 install.
#
# Must be run as Administrator (right-click PowerShell -> Run as Administrator,
# then run this script), because it restarts the postgresql-x64-18 service.
#
# What it does:
#   1. Backs up pg_hba.conf
#   2. Temporarily switches local auth to "trust" (no password) so we can
#      connect without knowing the existing postgres superuser password
#   3. Creates role `finance_agent_app` and database `finance_agent`
#      (does NOT touch the existing postgres user's password)
#   4. Restores the original pg_hba.conf (back to scram-sha-256)
#   5. Restarts PostgreSQL again to re-apply secure auth
#
# Safe to re-run if it fails partway - it restores the backup either way.

$ErrorActionPreference = "Stop"
Start-Transcript -Path "D:\EE-Finance-Agent\setup_local_db.log" -Force
$dataDir = "C:\Program Files\PostgreSQL\18\data"
$hba = Join-Path $dataDir "pg_hba.conf"
$backup = Join-Path $dataDir "pg_hba.conf.bak_finance_agent_setup"
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$appPassword = "GsKTIOGgbxIgd5w9iX0EFboM"

try {
    Write-Host "Backing up pg_hba.conf..."
    Copy-Item $hba $backup -Force

    Write-Host "Switching local auth to trust (temporary)..."
    (Get-Content $hba) -replace 'scram-sha-256', 'trust' | Set-Content $hba

    Write-Host "Restarting PostgreSQL service..."
    Restart-Service postgresql-x64-18
    Start-Sleep -Seconds 3

    Write-Host "Creating role and database..."
    & $psql -U postgres -h 127.0.0.1 -p 5432 -v ON_ERROR_STOP=1 -c "CREATE ROLE finance_agent_app LOGIN PASSWORD '$appPassword';"
    & $psql -U postgres -h 127.0.0.1 -p 5432 -v ON_ERROR_STOP=1 -c "CREATE DATABASE finance_agent OWNER finance_agent_app;"

    Write-Host "Done creating role/database."
}
finally {
    Write-Host "Restoring original pg_hba.conf..."
    Copy-Item $backup $hba -Force

    Write-Host "Restarting PostgreSQL service to restore secure auth..."
    Restart-Service postgresql-x64-18

    Write-Host "Finished. Auth restored to scram-sha-256."
}

Write-Host ""
Write-Host "If you saw 'Done creating role/database.' above with no errors, setup succeeded."
Write-Host "Database: finance_agent | Role: finance_agent_app | Password: $appPassword"
Stop-Transcript
