@echo off
rem Duplo clique para abrir a Perfumoteca no Windows.
cd /d "%~dp0"
if not exist .venv (
  echo Primeira execucao: instalando, aguarde alguns minutos...
  python -m venv .venv || (echo Instale o Python em https://www.python.org/downloads/ e marque "Add Python to PATH". & pause & exit /b 1)
  .venv\Scripts\python -m pip install -r requirements.txt
  .venv\Scripts\python -m playwright install chromium
)
.venv\Scripts\python main.py
pause
