@echo off
cd /d "%~dp0"
python run_pipeline.py
if errorlevel 1 (
  echo.
  echo Pipeline failed. See the error above.
  pause
  exit /b 1
)
echo.
echo Pipeline completed successfully.
pause
