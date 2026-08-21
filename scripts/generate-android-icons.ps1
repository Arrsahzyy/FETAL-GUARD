param(
    [string]$ForegroundSource = 'src\assets\fetal-guard-app-icon-foreground.png'
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repositoryRoot $ForegroundSource
$resourceRoot = Join-Path $repositoryRoot 'android\app\src\main\res'
$backgroundColor = [System.Drawing.ColorTranslator]::FromHtml('#EFF5FC')

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Foreground icon tidak ditemukan: $sourcePath"
}

$source = [System.Drawing.Bitmap]::FromFile($sourcePath)

function Write-LauncherBitmap {
    param(
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)][int]$Size,
        [Parameter(Mandatory = $true)][ValidateSet('legacy', 'round', 'foreground')][string]$Kind
    )

    $bitmap = New-Object System.Drawing.Bitmap(
        $Size,
        $Size,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
    )
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

        $graphics.Clear([System.Drawing.Color]::Transparent)
        if ($Kind -eq 'legacy') {
            $graphics.FillRectangle(
                (New-Object System.Drawing.SolidBrush($backgroundColor)),
                0,
                0,
                $Size,
                $Size
            )
        }
        elseif ($Kind -eq 'round') {
            $graphics.FillEllipse(
                (New-Object System.Drawing.SolidBrush($backgroundColor)),
                0,
                0,
                $Size,
                $Size
            )
        }

        $graphics.DrawImage($source, 0, 0, $Size, $Size)
        $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

try {
    $densities = @(
        @{ Name = 'mdpi'; Legacy = 48; Foreground = 108 },
        @{ Name = 'hdpi'; Legacy = 72; Foreground = 162 },
        @{ Name = 'xhdpi'; Legacy = 96; Foreground = 216 },
        @{ Name = 'xxhdpi'; Legacy = 144; Foreground = 324 },
        @{ Name = 'xxxhdpi'; Legacy = 192; Foreground = 432 }
    )

    foreach ($density in $densities) {
        $directory = Join-Path $resourceRoot "mipmap-$($density.Name)"
        Write-LauncherBitmap `
            -OutputPath (Join-Path $directory 'ic_launcher.png') `
            -Size $density.Legacy `
            -Kind 'legacy'
        Write-LauncherBitmap `
            -OutputPath (Join-Path $directory 'ic_launcher_round.png') `
            -Size $density.Legacy `
            -Kind 'round'
        Write-LauncherBitmap `
            -OutputPath (Join-Path $directory 'ic_launcher_foreground.png') `
            -Size $density.Foreground `
            -Kind 'foreground'
    }
}
finally {
    $source.Dispose()
}

Write-Output 'Android launcher icons generated.'
