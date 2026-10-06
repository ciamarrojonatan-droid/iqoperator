# IQ Operator - Bot & Cockpit Next.js Runner (PowerShell)
$Host.UI.RawUI.WindowTitle = "IQ Operator - Bot & Cockpit Next.js"
Set-Location $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    IQ OPERATOR - CENTRO DE INTELIGENCIA (M1)      " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERRO] Ambiente virtual .venv nao encontrado em $pythonExe" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[1/3] Iniciando Cockpit Next.js na porta 3000..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm --prefix cockpit-next start -- -p 3000" -WindowStyle Minimized

Write-Host "[2/3] Abrindo navegador em http://localhost:3000..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

Write-Host "[3/3] Iniciando o Bot M1 MHI Sniper..." -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
& $pythonExe "main.py"
