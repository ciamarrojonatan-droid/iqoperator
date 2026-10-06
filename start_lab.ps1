# IQ Operator - Laboratório & Grid Search (PowerShell)
$Host.UI.RawUI.WindowTitle = "IQ Operator - Laboratorio (30 Ativos)"
Set-Location $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    IQ OPERATOR - BANCADA DE TESTES & LABORATORIO  " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERRO] Ambiente virtual .venv nao encontrado em $pythonExe" -ForegroundColor Red
    pause
    exit 1
}

# Define as variaveis de isolamento
$env:ENV_FILE = ".env.lab"
$env:TRADE_LOG = "data/trades_lab.csv"

Write-Host "[1/3] Iniciando Cockpit do Laboratorio na porta 3000..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/c set TRADE_LOG=data/trades_lab.csv && npm --prefix cockpit-next start -- -p 3000" -WindowStyle Minimized

Write-Host "[2/3] Abrindo Centro de Inteligencia em http://localhost:3000..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

Write-Host "[3/3] Iniciando o Bot de Mineracao de Dados..." -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
& $pythonExe "main.py"
