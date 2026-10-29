@echo off
rem Startet Mountain Memories lokal. Beim ersten Mal wird die Python-Umgebung eingerichtet.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Richte Python-Umgebung ein ...
    python -m venv .venv || (echo Python wurde nicht gefunden. Bitte Python 3.12 oder neuer installieren. & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py
pause
