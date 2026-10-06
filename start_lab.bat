@echo off
title IQ Operator - LABORATORIO & GRID SEARCH (30 ATIVOS)
cd /d "%~dp0"

echo ===================================================
echo     IQ OPERATOR - BANCADA DE TESTES & LABORATORIO
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    pause
    exit /b 1
)

if not exist ".env.lab" (
    echo [ERRO] Arquivo .env.lab nao encontrado!
    pause
    exit /b 1
)

:: Define as variaveis de isolamento do laboratorio
set ENV_FILE=.env.lab
set TRADE_LOG=data/trades_lab.csv

echo [1/3] Iniciando o Cockpit Next.js apontado para o LABORATORIO (porta 3000)...
start "Cockpit Lab" /min cmd /c "set TRADE_LOG=data/trades_lab.csv && npm --prefix cockpit-next start -- -p 3000"

echo [2/3] Abrindo Centro de Inteligencia & Auditoria em http://localhost:3000...
timeout /t 3 /nobreak >nul
start "" http://localhost:3000

echo [3/3] Iniciando o Bot de Mineracao (30 ativos / Banca 50k)...
echo ===================================================
".venv\Scripts\python.exe" main.py

echo Encerrando Cockpit do Laboratorio...
taskkill /fi "WINDOWTITLE eq Cockpit Lab*" /f /t >nul 2>&1
pause
