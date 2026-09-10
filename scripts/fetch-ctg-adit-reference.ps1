<#
.SYNOPSIS
  Fetch Adit's CTG CNN-LSTM repository at a pinned commit into ai/vendor/ (gitignored).

.DESCRIPTION
  The Adit model (Adityakknn/ctg_cnn_lstm_adit) is a RESEARCH baseline and a
  training-methodology reference only. It is trained 100% on synthetic data and
  has no real-CTG validation, so it is NOT vendored into this repo. Run this
  script when you actually need it -- Fase 1 (register as an AIModelVersion in
  the `research` slot) or Fase 2 (finish external_validation.py against CTU-UHB /
  JNU-CTG). See docs/ai/model-cards/ctg_cnn_lstm_adit.md and
  docs/ai/hybrid-dl-integration-prd.md.

  What lands in ai/vendor/ctg_cnn_lstm_adit/:
    - the full repo at the pinned commit (checkpoints + synthetic dataset included)
  What this repo deliberately does NOT adopt from it (PRD section 8):
    - app/signal_processing/, app/services/  -> we have backend/services/signal_processing.py
    - main.py                                -> no-auth FastAPI prototype, CORS *
    - aiService.js, deploy/, esp32_*.ino     -> not ours

.NOTES
  torch.load(weights_only=False) in app/ai/inference.py executes arbitrary code
  on checkpoint load. Only load checkpoints you generated yourself
  (training/generate_sequences.py -> training/train.py, seed 42 reproduces them).
#>
[CmdletBinding()]
param(
    # Pinned to the reviewed commit. Bump deliberately, and re-review, never silently.
    [string]$Ref = "25e60611b17426b10a4fd76a41c08bcaa5a5c76d",
    [string]$Repo = "https://github.com/Adityakknn/ctg_cnn_lstm_adit.git"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $repoRoot "ai\vendor\ctg_cnn_lstm_adit"

if (Test-Path $dest) {
    Write-Host "ai/vendor/ctg_cnn_lstm_adit already exists. Remove it first to re-fetch." -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null

Write-Host "Cloning $Repo @ $Ref ..." -ForegroundColor Cyan
git clone --no-checkout $Repo $dest
Push-Location $dest
try {
    git checkout $Ref --
    $actual = (git rev-parse HEAD).Trim()
    if ($actual -ne $Ref) { throw "Checked out $actual, expected $Ref" }
    Write-Host ""
    Write-Host "Fetched to ai/vendor/ctg_cnn_lstm_adit at $actual" -ForegroundColor Green
    Write-Host "This path is gitignored. Read docs/ai/model-cards/ctg_cnn_lstm_adit.md before using it." -ForegroundColor Green
}
finally {
    Pop-Location
}
