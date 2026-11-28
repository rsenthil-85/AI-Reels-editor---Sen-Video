<#
start.ps1 - open the edit page in your browser. Works on its own or from any AI assistant (Claude Code, Codex,
OpenCode, Gemini CLI, a local model).

    powershell -ExecutionPolicy Bypass -File start.ps1 [-Videos <folder>] [-Port 8765] [-NoBrowser]

First run: installs everything into this folder (install.ps1 -Target here, 5 to 10 minutes).
Then starts the page with the upload screen and opens http://127.0.0.1:8765 in your normal browser.
Uploaded videos and finished edits go to -Videos (default: Videos\pro-video-editor in your user folder).
Keep this window open while you edit; close it to stop the page.
#>
param(
  [string]$Videos = (Join-Path $HOME "Videos\pro-video-editor"),
  [int]$Port = 8765,
  [switch]$NoBrowser
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$py = Join-Path $here ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "First run: installing the editor into this folder (5 to 10 minutes)..."
  & powershell -ExecutionPolicy Bypass -File (Join-Path $here "install.ps1") -Target $here
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) { throw "Install did not finish. Read the message above, fix it, then run start.ps1 again." }
}
New-Item -ItemType Directory -Force $Videos | Out-Null
$args2 = @((Join-Path $here "scripts\live.py"), "--home", $Videos, "--port", "$Port")
if (-not $NoBrowser) { $args2 += "--open" }
Write-Host "Edit page starting. Your videos go to $Videos"
& $py -u @args2
