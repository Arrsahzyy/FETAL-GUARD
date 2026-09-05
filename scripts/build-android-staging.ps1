param(
    # Public HTTPS backend the APK talks to. Defaults to the staging custom domain.
    [ValidatePattern('^https://[a-z0-9.-]+$')]
    [string]$ApiBaseUrl = 'https://api.pkmkcfetalguard.app'
)

# Produces a sideloadable debug APK that points at a public HTTPS backend
# (staging by default). Unlike scripts/build-android-local.ps1 this build:
#   - runs the default production Vite mode (import.meta.env.PROD = true), so
#     apiRuntimeConfig.js treats the URL as a real deployment
#   - sets NO cleartext / insecure-local flags: the app must reach the backend
#     over HTTPS, which every .app-domain endpoint already enforces
#   - still assembleDebug (unsigned) - fine for internal sideload / demo, not
#     for Play Store distribution

$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$androidStudioJava = 'C:\Program Files\Android\Android Studio\jbr'
$apkSource = Join-Path $repositoryRoot 'android\app\build\outputs\apk\debug\app-debug.apk'
$artifactDirectory = Join-Path $repositoryRoot 'artifacts'
$artifactPath = Join-Path $artifactDirectory 'FETAL-GUARD-staging-debug.apk'

if (-not (Test-Path -LiteralPath (Join-Path $androidStudioJava 'bin\java.exe'))) {
    throw 'Android Studio JBR tidak ditemukan. Install Android Studio atau set JAVA_HOME secara manual.'
}

$env:JAVA_HOME = $androidStudioJava
$env:Path = "$androidStudioJava\bin;$env:Path"
$env:VITE_API_BASE_URL = $ApiBaseUrl.TrimEnd('/')
# Explicitly clear anything a previous local build may have left in the session.
Remove-Item Env:\VITE_ALLOW_INSECURE_LOCAL_API -ErrorAction SilentlyContinue
Remove-Item Env:\CAPACITOR_ALLOW_LOCAL_CLEARTEXT_API -ErrorAction SilentlyContinue
Remove-Item Env:\CAPACITOR_DEV_SERVER_URL -ErrorAction SilentlyContinue

Push-Location $repositoryRoot
try {
    & (Join-Path $PSScriptRoot 'generate-android-icons.ps1')

    & npm.cmd run build
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
    Write-Output "APK_STAGING=$artifactPath"
    Write-Output "API_BASE_URL=$env:VITE_API_BASE_URL"
}
finally {
    Pop-Location
}
