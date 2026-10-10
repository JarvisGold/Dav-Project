@echo off
cd /d "%~dp0"
title Mumbai Mobility Dashboard

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python is not installed or not on PATH.
  echo Install it from https://www.python.org/downloads/
  echo During setup, tick the box: Add Python to PATH
  echo Then double-click run.bat again.
  echo.
  pause
  exit /b 1
)

if not exist "data\mumbai_air_quality.csv" (
  echo.
  echo The file data\mumbai_air_quality.csv was not found.
  echo Opening the data folder for you. Put the CSV there, then double-click run.bat again.
  echo.
  start "" "data"
  pause
  exit /b 1
)

if not exist ".venv\installed.flag" (
  echo.
  echo First-time setup. This takes a few minutes, only once...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Installing packages failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  echo done > ".venv\installed.flag"
)

echo.
echo Starting the dashboard. Your browser will open. Close this window to stop it.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
