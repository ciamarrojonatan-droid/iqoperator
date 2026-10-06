@echo off
title IQ Operator - Bot & Cockpit Next.js
cd /d "%~dp0"

echo ===================================================
echo     IQ OPERATOR - CENTRO DE INTELIGENCIA & AUDITORIA
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    pause
    exit /b 1
)

echo [1/3] Iniciando o Cockpit Next.js na porta 3000...
start "Cockpit Next.js" /min cmd /c "npm --prefix cockpit-next start -- -p 3000"

echo [2/3] Abrindo navegador em http://localhost:3000...
timeout /t 3 /nobreak >nul
start "" http://localhost:3000

echo [3/3] Iniciando o motor Bot M1 MHI Sniper...
echo ===================================================
".venv\Scripts\python.exe" main.py

echo Encerrando Cockpit...
taskkill /fi "WINDOWTITLE eq Cockpit Next.js*" /f /t >nul 2>&1
pause
