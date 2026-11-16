@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Run setup first: python -m venv .venv
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import yt.__main__" >nul 2>&1
if errorlevel 1 (
  echo Install the project first: .venv\Scripts\python.exe -m pip install -e ".[dev,build]"
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m yt %*
