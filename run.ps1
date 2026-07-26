# Starts the backend + frontend and opens the dashboard in Chrome.
# Usage: right-click > Run with PowerShell, or `.\run.ps1` from a terminal.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

Write-Host "Starting backend (FastAPI)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
)

Write-Host "Starting frontend (Next.js)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$frontend'; npm run dev"
)

Write-Host "Waiting for the dashboard to come up..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if ($ready) {
    Write-Host "Opening http://localhost:3000 in Chrome..." -ForegroundColor Green
    if (Test-Path $chrome) {
        Start-Process $chrome "http://localhost:3000"
    } else {
        Start-Process "http://localhost:3000"
    }
} else {
    Write-Host "Dashboard didn't respond within 60s. Check the two new terminal windows for errors." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Two terminal windows are now running the backend and frontend." -ForegroundColor Cyan
Write-Host "Close those windows (or Ctrl+C inside them) to stop the app." -ForegroundColor Cyan
