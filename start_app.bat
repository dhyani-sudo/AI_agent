@echo off
cd /d "%~dp0"

echo ================================================
echo   AI Video Reels Agent
echo ================================================

if /i "%~1"=="skip" goto app

echo.
echo [1/3] Pulling the latest version from GitHub...
git pull
if errorlevel 1 echo    (git pull failed - continuing with the local version)

echo.
echo [2/3] Running diagnostics (a report is uploaded to GitHub if all tests pass)...
python diagnose.py
if errorlevel 1 (
    echo.
    echo    Diagnostics FAILED - read the messages above.
    echo    The app will still start so you can look around.
)

:app
echo.
echo [3/3] Starting the app... your browser will open automatically.
python app.py

echo.
pause
