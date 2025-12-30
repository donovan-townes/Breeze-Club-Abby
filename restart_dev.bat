@echo off
REM restart_dev.bat
REM Batch script to auto-restart Abby on shutdown (for development)

echo 🐰 Abby Development Auto-Restart
echo Press Ctrl+C to stop the restart loop
echo.

:restart
echo [%TIME%] Starting Abby...
python launch.py

if %ERRORLEVEL% EQU 0 (
    echo [%TIME%] Abby exited gracefully
    echo [%TIME%] Restarting in 2 seconds...
    timeout /t 2 /nobreak >nul
) else (
    echo [%TIME%] Abby crashed with error code %ERRORLEVEL%
    echo [%TIME%] Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
)

goto restart
