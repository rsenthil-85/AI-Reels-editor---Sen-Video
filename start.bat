@echo off
rem Double-click to open the edit page (first run installs everything). Keep this window open while you edit.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
