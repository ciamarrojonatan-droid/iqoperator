@echo off
title IQ Operator - Local Runner
cd /d "%~dp0"
echo ===================================================
echo           IQ OPERATOR - SNIPER MHI M1
echo ===================================================
echo Verificando ambiente Python virtual (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    pause
    exit /b 1
)

echo Iniciando o Bot + Cockpit Web...
echo Cockpit estara disponivel em: http://localhost:8080
timeout /t 3 /nobreak >nul
start "" http://localhost:8080
".venv\Scripts\python.exe" main.py
pause
