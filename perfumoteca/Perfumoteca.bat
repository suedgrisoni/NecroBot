@echo off
chcp 65001 >nul
title Perfumoteca
rem Duplo clique para abrir a Perfumoteca no Windows.
cd /d "%~dp0"

rem Uma atualizacao anterior trouxe um atalho novo: troca e reabre.
if exist "Perfumoteca.novo.bat" (
  move /y "Perfumoteca.novo.bat" "Perfumoteca.bat" >nul
  start "" "%~f0"
  exit /b 0
)

if exist ".venv\Scripts\python.exe" goto abrir

echo Primeira execucao: instalando a Perfumoteca. Isso leva alguns minutos...
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python nao encontrado.
  echo Instale em https://www.python.org/downloads/ marcando "Add Python to PATH"
  echo e depois abra este atalho de novo.
  pause
  exit /b 1
)
%PY% -m venv .venv
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto erro

:abrir
".venv\Scripts\python.exe" atualizar.py
if exist "Perfumoteca.novo.bat" goto reabrir
echo.
echo Perfumoteca aberta em http://127.0.0.1:5000
echo Deixe esta janela aberta enquanto usa o app. Para fechar, feche esta janela.
echo.
".venv\Scripts\python.exe" main.py
pause
exit /b 0

:reabrir
start "" "%~f0"
exit /b 0

:erro
echo.
echo Algo deu errado na instalacao. Tire um print desta janela e envie.
if exist .venv rmdir /s /q .venv
pause
exit /b 1
