param(
    [ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    [string]$AdminEmail = 'admin@fetalguard.id',

    [ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    [string]$ClinicianEmail = 'dokter@fetalguard.com'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function ConvertTo-PlainText {
    param(
        [Parameter(Mandatory = $true)]
        [Security.SecureString]$SecureValue
    )

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Read-ConfirmedPassword {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AccountLabel
    )

    while ($true) {
        $firstSecure = Read-Host "$AccountLabel - password sementara (minimal 8 karakter)" -AsSecureString
        $secondSecure = Read-Host "$AccountLabel - ulangi password" -AsSecureString
        $firstPlain = ConvertTo-PlainText -SecureValue $firstSecure
        $secondPlain = ConvertTo-PlainText -SecureValue $secondSecure

        try {
            if ($firstPlain.Length -lt 8) {
                Write-Warning 'Password minimal 8 karakter. Silakan ulangi.'
                continue
            }
            if ($firstPlain -cne $secondPlain) {
                Write-Warning 'Konfirmasi password tidak sama. Silakan ulangi.'
                continue
            }
            return $firstPlain
        }
        finally {
            $firstSecure.Dispose()
            $secondSecure.Dispose()
            $secondPlain = $null
        }
    }
}

function Restore-EnvironmentValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
        return
    }
    Set-Item -LiteralPath "Env:$Name" -Value $Value
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot 'backend'
$python = Join-Path $backendDirectory 'venv\Scripts\python.exe'
$localDatabase = Join-Path $backendDirectory 'fetal_guard.local-mobile.db'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Python backend tidak ditemukan.'
}
if (-not (Test-Path -LiteralPath $localDatabase -PathType Leaf)) {
    throw 'Database local-mobile belum ada. Jalankan run-backend-local-mobile.ps1 terlebih dahulu.'
}

$environmentNames = @(
    'ENVIRONMENT',
    'AUTO_CREATE_DB',
    'SQLALCHEMY_DATABASE_URI',
    'FG_ADMIN_EMAIL',
    'FG_ADMIN_PASSWORD',
    'FG_CLINICIAN_EMAIL',
    'FG_CLINICIAN_PASSWORD'
)
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$pushedLocation = $false
$adminPassword = $null
$clinicianPassword = $null
try {
    $env:ENVIRONMENT = 'development'
    $env:AUTO_CREATE_DB = 'false'
    $env:SQLALCHEMY_DATABASE_URI = "sqlite:///$($localDatabase.Replace('\', '/'))"

    $adminPassword = Read-ConfirmedPassword -AccountLabel "Admin ($AdminEmail)"
    $clinicianPassword = Read-ConfirmedPassword -AccountLabel "Nakes ($ClinicianEmail)"
    $env:FG_ADMIN_EMAIL = $AdminEmail.ToLowerInvariant()
    $env:FG_ADMIN_PASSWORD = $adminPassword

    Push-Location $backendDirectory
    $pushedLocation = $true
    & $python seed_admin.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Provisioning akun admin gagal.'
    }
    Remove-Item -LiteralPath 'Env:FG_ADMIN_PASSWORD' -ErrorAction SilentlyContinue
    $adminPassword = $null

    $env:FG_CLINICIAN_EMAIL = $ClinicianEmail.ToLowerInvariant()
    $env:FG_CLINICIAN_PASSWORD = $clinicianPassword
    & $python seed_clinician.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Provisioning akun nakes gagal.'
    }

    Write-Host ''
    Write-Host 'Provisioning local-mobile selesai.' -ForegroundColor Green
    Write-Host "Admin : $($AdminEmail.ToLowerInvariant())"
    Write-Host "Nakes : $($ClinicianEmail.ToLowerInvariant())"
    Write-Host 'Keduanya wajib mengganti password saat login pertama.'
}
finally {
    $adminPassword = $null
    $clinicianPassword = $null
    if ($pushedLocation) {
        Pop-Location
    }
    foreach ($name in $environmentNames) {
        Restore-EnvironmentValue -Name $name -Value $previousEnvironment[$name]
    }
}
