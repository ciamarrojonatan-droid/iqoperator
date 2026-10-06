# IQ Operator - Local Runner (PowerShell)
$Host.UI.RawUI.WindowTitle = "IQ Operator - Local Runner"
Set-Location $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "          IQ OPERATOR - SNIPER MHI M1              " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERRO] Ambiente virtual .venv nao encontrado em $pythonExe" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Iniciando Bot + Cockpit Web..." -ForegroundColor Yellow
Write-Host "Cockpit estara disponivel em: http://localhost:8080" -ForegroundColor Cyan

Start-Process "http://localhost:8080"
& $pythonExe "main.py"
