param(
    [string]$PatientEmail = '',

    [ValidatePattern('^[A-Za-z0-9._:-]{3,80}$')]
    [string]$DeviceUid = 'FETAL-GUARD-001'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($PatientEmail)) {
    $PatientEmail = Read-Host 'Email akun pasien lokal yang akan memakai ESP32'
}

if ($PatientEmail -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') {
    throw 'Email pasien tidak valid.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendDirectory 'venv\Scripts\python.exe'
$localDatabase = Join-Path $backendDirectory 'fetal_guard.local-mobile.db'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python backend tidak ditemukan.'
}

if (-not (Test-Path -LiteralPath $localDatabase)) {
    throw 'Database lokal mobile belum ada. Jalankan run-backend-local-mobile.ps1 terlebih dahulu.'
}

$env:ENVIRONMENT = 'development'
$env:AUTO_CREATE_DB = 'false'
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///$($localDatabase.Replace('\', '/'))"

Push-Location $backendDirectory
try {
    & $python provision_local_mobile_device.py --patient-email $PatientEmail --device-uid $DeviceUid
    if ($LASTEXITCODE -ne 0) {
        throw 'Provisioning perangkat lokal gagal.'
    }
}
finally {
    Pop-Location
}
