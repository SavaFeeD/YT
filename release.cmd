@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

echo === YT installer build ===
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    python -m venv .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" scripts\build_release.py --check
if errorlevel 1 goto :failed

echo Preparing dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.lock.txt
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .
if errorlevel 1 goto :failed

echo Building application and installer...
".venv\Scripts\python.exe" scripts\build_release.py
if errorlevel 1 goto :failed

if not exist "release\YT-Setup.exe" (
    echo ERROR: The installer was not created.
    goto :failed
)

echo.
echo Done! Installer: "%CD%\release\YT-Setup.exe"
popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:failed
echo.
echo Build failed. See the error above.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
