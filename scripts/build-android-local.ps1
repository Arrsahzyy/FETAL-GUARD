param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^http://(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)')]
    [string]$ApiBaseUrl
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$androidStudioJava = 'C:\Program Files\Android\Android Studio\jbr'
$apkSource = Join-Path $repositoryRoot 'android\app\build\outputs\apk\debug\app-debug.apk'
$artifactDirectory = Join-Path $repositoryRoot 'artifacts'
$artifactPath = Join-Path $artifactDirectory 'FETAL-GUARD-local-debug.apk'

if (-not (Test-Path -LiteralPath (Join-Path $androidStudioJava 'bin\java.exe'))) {
    throw 'Android Studio JBR tidak ditemukan. Install Android Studio atau set JAVA_HOME secara manual.'
}

$env:JAVA_HOME = $androidStudioJava
$env:Path = "$androidStudioJava\bin;$env:Path"
$env:VITE_API_BASE_URL = $ApiBaseUrl.TrimEnd('/')
$env:VITE_ALLOW_INSECURE_LOCAL_API = 'true'
$env:CAPACITOR_ALLOW_LOCAL_CLEARTEXT_API = 'true'

Push-Location $repositoryRoot
try {
    & (Join-Path $PSScriptRoot 'generate-android-icons.ps1')

    & npm.cmd run build -- --mode android-local
    if ($LASTEXITCODE -ne 0) { throw 'Vite build gagal.' }

    & npx.cmd cap sync android
    if ($LASTEXITCODE -ne 0) { throw 'Capacitor sync gagal.' }

    & .\android\gradlew.bat --no-daemon --project-dir .\android assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Gradle assembleDebug gagal.' }

    if (-not (Test-Path -LiteralPath $apkSource)) {
        throw "APK tidak ditemukan pada $apkSource"
    }

    New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
    Copy-Item -LiteralPath $apkSource -Destination $artifactPath -Force
    Write-Output "APK_LOCAL=$artifactPath"
    Write-Output "API_BASE_URL=$env:VITE_API_BASE_URL"
}
finally {
    Pop-Location
}
