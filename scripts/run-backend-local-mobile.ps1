param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)')]
    [string]$LaptopIp,

    [ValidateRange(1024, 65535)]
    [int]$Port = 3020
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot 'backend'
$uvicorn = Join-Path $backendDirectory 'venv\Scripts\uvicorn.exe'
$python = Join-Path $backendDirectory 'venv\Scripts\python.exe'
$localDatabase = Join-Path $backendDirectory 'fetal_guard.local-mobile.db'

if (-not (Test-Path -LiteralPath $uvicorn)) {
    throw 'Virtual environment backend tidak ditemukan.'
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python backend tidak ditemukan.'
}

$env:ENVIRONMENT = 'development'
$env:AUTO_CREATE_DB = 'false'
$env:SQLALCHEMY_DATABASE_URI = "sqlite:///$($localDatabase.Replace('\', '/'))"
$env:BACKEND_CORS_ORIGINS = @(
    'https://localhost',
    'capacitor://localhost',
    'http://localhost',
    'http://localhost:5173',
    'http://127.0.0.1:5173'
) | ConvertTo-Json -Compress
$env:TRUSTED_HOSTS = @('localhost', '127.0.0.1', $LaptopIp) | ConvertTo-Json -Compress

Push-Location $backendDirectory
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw 'Migrasi database lokal mobile gagal.'
    }

    Write-Output "LOCAL_MOBILE_DATABASE=$localDatabase"
    Write-Output "LOCAL_MOBILE_API=http://${LaptopIp}:${Port}"
    & $uvicorn main:app --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
