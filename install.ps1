<#
  pro-video-editor installer (Windows, PowerShell 5.1+)

    powershell -ExecutionPolicy Bypass -File install.ps1 [-Target <skills dir>] [-WithRNNoise] [-AllowNonMIT] [-NoModels] [-NoBigSpeech] [-WithFilmCraft]

  - Copies this folder to %USERPROFILE%\.claude\skills\pro-video-editor (or -Target).
  - Python env (.venv) from the python.org Python 3.10-3.12 already installed (signed, so Windows Smart App
    Control allows it - no downloaded interpreters).
  - npm deps (playwright-core, three) + Playwright's headless Chromium for rendering graphics.
  - Pre-downloads the Whisper "small" model unless -NoModels.
  - Bundles the big speech model (large-v3-turbo, MIT, ~1.6 GB) for Tamil, Hindi and other languages unless -NoModels or -NoBigSpeech.
  - -WithRNNoise: fetches RNNoise voice-denoise models (GregorR/rnnoise-models; no explicit licence file - opt-in).
  - -AllowNonMIT: also installs optional libs that are NOT MIT/ISC (postprocessing: Zlib, @dimforge/rapier3d-compat:
    Apache-2.0, p5: LGPL-2.1) for the React Three / Claude Animation Base workflows. Off by default.
  - -WithFilmCraft: downloads FilmCraft (free video editor, MIT or Apache-2.0, portable, ~115 MB) from its official
    GitHub release, checks its SHA-256 against the published list, unzips it to <skill>\tools\filmcraft. Used by
    scripts/filmcraft_open.py to open an edit on a real timeline for hand tweaks. Optional.
  Never disables Windows security features. If something is blocked, it stops and tells you.
#>
param(
  [string]$Target = "$env:USERPROFILE\.claude\skills\pro-video-editor",
  [switch]$WithRNNoise,
  [switch]$WithMatte,
  [switch]$AllowNonMIT,
  [switch]$NoModels,
  [switch]$NoBigSpeech,
  [switch]$WithFilmCraft,
  [string]$FilmCraftVersion = "0.20.1"
)
$ErrorActionPreference = "Stop"
$Src = Split-Path -Parent $MyInvocation.MyCommand.Path
function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found. $hint" } }

Step "Checking tools"
Need ffmpeg "Install it: winget install Gyan.FFmpeg"
Need node   "Install Node.js LTS: winget install OpenJS.NodeJS.LTS"
$py = $null
foreach ($v in "3.12", "3.11", "3.10") {
  try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $py = $p.Trim(); break } } catch {}
}
if (-not $py) {
  $c = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python31[012]\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) { $py = $c.FullName }
}
if (-not $py) { throw "Python 3.10-3.12 from python.org not found. Install: winget install Python.Python.3.12" }
Write-Host "  ffmpeg ok, node $(node -v), python $py"

Step "Copying skill to $Target"
if ((Resolve-Path $Src).Path -ne $Target) {
  New-Item -ItemType Directory -Force $Target | Out-Null
  robocopy $Src $Target /E /XD .venv node_modules __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "copy failed (robocopy $LASTEXITCODE)" }
}

Step "Python environment"
$venvPy = Join-Path $Target ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & $py -m venv (Join-Path $Target ".venv") }
& $venvPy -c "print('  venv runs')"
if ($LASTEXITCODE -ne 0) { throw "The new Python environment was blocked from running. Check Windows Security notifications; do not disable protection - tell the skill author." }
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -q -r (Join-Path $Target "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
# Smart App Control checks each new DLL's reputation online; a first import can be blocked and pass a minute later.
$ok = $false
$warm = "import numpy as np, av, faster_whisper, librosa, PIL, fontTools; y=np.random.default_rng(0).standard_normal(88200).astype('float32'); librosa.beat.beat_track(y=y, sr=22050); librosa.onset.onset_detect(y=y, sr=22050)"
foreach ($try in 1..6) {
  & $venvPy -c $warm 2>$null
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
  Write-Host "  a library was blocked by Windows Smart App Control - waiting 30 s for Windows to check it (try $try/6)" -ForegroundColor Yellow
  Start-Sleep 30
}
if (-not $ok) { throw "Windows Smart App Control is still blocking a Python library. Do not turn protection off. Run: $venvPy -c ""import av, faster_whisper, librosa"" to see which one, and report it." }

Step "Node packages + headless browser"
Push-Location $Target
npm install --silent
node node_modules/playwright-core/cli.js install chromium-headless-shell
if ($AllowNonMIT) {
  Write-Host "  installing optional non-MIT libs (Zlib / Apache-2.0 / LGPL)" -ForegroundColor Yellow
  npm install --silent postprocessing @dimforge/rapier3d-compat p5 p5.brush
}
Pop-Location

if ($WithRNNoise) {
  Step "RNNoise voice models"
  $d = Join-Path $Target "assets\rnnoise"; New-Item -ItemType Directory -Force $d | Out-Null
  $base = "https://raw.githubusercontent.com/GregorR/rnnoise-models/master"
  Invoke-WebRequest "$base/somnolent-hogwash-2018-09-01/sh.rnnn" -OutFile "$d\sh.rnnn"
  Invoke-WebRequest "$base/conjoined-burgers-2018-08-28/cb.rnnn" -OutFile "$d\cb.rnnn"
}

if (-not $NoModels -or $WithMatte) {
  Step "Person model for auto face framing + background matte (BiRefNet-lite, MIT, 224 MB) + onnxruntime (MIT)"
  & $venvPy -m pip install -q onnxruntime
  $m = Join-Path $Target "assets\models"; New-Item -ItemType Directory -Force $m | Out-Null
  if (-not (Test-Path (Join-Path $m "birefnet_lite.onnx"))) {
    Invoke-WebRequest "https://huggingface.co/onnx-community/BiRefNet_lite-ONNX/resolve/main/onnx/model.onnx" -OutFile (Join-Path $m "birefnet_lite.onnx")
  }
  Invoke-WebRequest "https://raw.githubusercontent.com/ZhengPeng7/BiRefNet/main/LICENSE" -OutFile "$m\LICENSE-BiRefNet.txt"
}

Step "Sound effects"
& $venvPy (Join-Path $Target "scripts\make_sfx.py") (Join-Path $Target "assets\sfx")
if ($LASTEXITCODE -ne 0) { throw "sound effects step failed" }

if (-not $NoModels) {
  Step "Whisper speech model (small, ~480 MB, first time only)"
  & $venvPy -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('  whisper ready')"
  if ($LASTEXITCODE -ne 0) { throw "whisper model step failed" }
}

if (-not $NoModels -and -not $NoBigSpeech) {
  $bd = Join-Path $Target "assets\models\whisper-large-v3-turbo"
  if (-not (Test-Path (Join-Path $bd "model.bin"))) {
    Step "Big speech model for Tamil, Hindi, Telugu and more (large-v3-turbo, MIT, ~1.6 GB, first time only)"
    New-Item -ItemType Directory -Force $bd | Out-Null
    $base = "https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main"
    foreach ($f in "config.json","preprocessor_config.json","tokenizer.json","vocabulary.json","README.md","model.bin") {
      Invoke-WebRequest "$base/$f" -OutFile (Join-Path $bd $f)
    }
  }
}

if ($WithFilmCraft) {
  Step "FilmCraft $FilmCraftVersion (optional hand-editing app, MIT or Apache-2.0, ~115 MB)"
  $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
  $zipName = "filmcraft-$FilmCraftVersion-windows-$arch-portable.zip"
  $base = "https://github.com/storytold/filmcraft/releases/download/v$FilmCraftVersion"
  $fcDir = Join-Path $Target "tools\filmcraft"; New-Item -ItemType Directory -Force $fcDir | Out-Null
  $zip = Join-Path $fcDir $zipName
  if (-not (Test-Path $zip)) { Invoke-WebRequest "$base/$zipName" -OutFile $zip }
  $sums = (Invoke-WebRequest "$base/SHA256SUMS.txt" -UseBasicParsing).Content
  $want = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($zipName) } | ForEach-Object { ($_ -split "\s+")[0] }) | Select-Object -First 1
  $got = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
  if (-not $want -or $got -ne $want.ToLower()) { Remove-Item $zip -Force; throw "FilmCraft download failed its checksum check - not installed" }
  Expand-Archive $zip -DestinationPath (Join-Path $fcDir "app") -Force
  $exe = Get-ChildItem (Join-Path $fcDir "app") -Recurse -Filter filmcraft.exe | Select-Object -First 1
  if (-not $exe) { throw "filmcraft.exe not found in the download" }
  $cfgDir = Join-Path $env:USERPROFILE ".pro-video-editor"; New-Item -ItemType Directory -Force $cfgDir | Out-Null
  @{ exe = $exe.FullName; version = $FilmCraftVersion } | ConvertTo-Json | Out-File (Join-Path $cfgDir "filmcraft.json") -Encoding utf8
  Write-Host "  FilmCraft ready: $($exe.FullName)"
  Write-Host "  If Windows Smart App Control blocks it on first start, wait a minute and try again - never turn protection off."
}

Step "Self-test"
& $venvPy (Join-Path $Target "scripts\music.py") "$env:TEMP\pve_test.wav" --seconds 4 --mood lofi
node (Join-Path $Target "scripts\render_gfx.mjs") x '{\"type\":\"title\",\"l1\":\"Install\",\"money\":\"OK\"}' --still 1 "$env:TEMP\pve_test.png" | Out-Null
if (Test-Path "$env:TEMP\pve_test.png") { Write-Host "  graphics renderer ok" } else { throw "graphics renderer failed" }

Write-Host "`nInstalled: $Target" -ForegroundColor Green
Write-Host "In Claude Code: give it a video and say what you want (or just 'edit this video')."
Write-Host "Command line:   $venvPy $Target\scripts\autoedit.py <video>"
