<#
start.ps1 - open the video editor in the browser. Double-click start.bat, or let any AI assistant run it
(Claude Code, Codex, OpenCode, Gemini CLI, a local model).

    powershell -ExecutionPolicy Bypass -File start.ps1 [-Detached] [-Videos <folder>] [-Port 8765] [-NoBrowser]

- Already running for this folder? It only opens the browser on it (no second copy).
- Otherwise it opens a "getting ready" page in the browser at once, installs on the first run (5 to 10 minutes),
  then starts the editor; the browser page switches to it by itself.
- -Detached (for AI assistants): does the above in its own window and returns at once, so the editor keeps
  running after the assistant's command ends.
Uploaded videos and finished edits go to -Videos (default: Videos\pro-video-editor in your user folder).
#>
param(
  [string]$Videos = (Join-Path $HOME "Videos\pro-video-editor"),
  [int]$Port = 8765,
  [switch]$NoBrowser,
  [switch]$Detached
)
$ErrorActionPreference = "Stop"
$here = (Resolve-Path $PSScriptRoot).Path

function Open-Url($u) { if (-not $NoBrowser) { try { Start-Process $u } catch { Write-Host "Open $u in your browser" } } }

# 1. this folder's editor already running? just show it
function Test-Open($p) { $c = [System.Net.Sockets.TcpClient]::new(); try { $c.ConnectAsync("127.0.0.1", $p).Wait(150) -and $c.Connected } catch { $false } finally { $c.Close() } }
for ($p = 8765; $p -lt 8785; $p++) {
  if (-not (Test-Open $p)) { continue }
  try {
    $w = Invoke-RestMethod "http://127.0.0.1:$p/api/whoami" -TimeoutSec 1
    if ($w.app -eq "pro-video-editor" -and ((Resolve-Path $w.install).Path -eq $here)) {
      Write-Host "The editor is already running: http://127.0.0.1:$p/"
      Open-Url "http://127.0.0.1:$p/"; exit 0
    }
  } catch {}
}

if ($Detached) {   # its own window, so it outlives the assistant's command
  $a = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-Videos", "`"$Videos`"", "-Port", "$Port")
  if ($NoBrowser) { $a += "-NoBrowser" }
  Start-Process powershell -ArgumentList $a -WindowStyle Minimized
  Write-Host "The editor is opening in the browser (its own window keeps it running). Link: http://127.0.0.1:$Port/ or the next free port."
  exit 0
}

# 2. a free port (another install's editor may hold 8765)
function Test-Free($p) { try { $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p); $l.Start(); $l.Stop(); $true } catch { $false } }
while (-not (Test-Free $Port)) { $Port++ }

# 3. show something at once
$wait = (Join-Path $here "templates\starting.html") -replace '\\', '/'
Open-Url "file:///$($wait)?port=$Port"
$Host.UI.RawUI.WindowTitle = "Video editor - keep this window open"

# 4. first run: install into this folder
$py = Join-Path $here ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "First run: setting up the editor in this folder (5 to 10 minutes)..."
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here "install.ps1") -Target $here
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) { Write-Host "Setup did not finish. Read the message above."; Read-Host "Press Enter to close"; exit 1 }
}

# 5. the editor (the browser page switches to it when it answers)
New-Item -ItemType Directory -Force $Videos | Out-Null
Write-Host "Editor running at http://127.0.0.1:$Port/  - your videos go to $Videos. Close this window to stop it."
& $py -u (Join-Path $here "scripts\live.py") --home $Videos --port $Port
