@echo off
cd /d %~dp0
echo [1/3] Checking Python...
python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python 3.11 or 3.12 is required.
  echo Install it from https://www.python.org and check "Add python.exe to PATH".
  python --version 2>nul
  pause
  exit /b
)
echo [2/3] Creating virtual environment...
if not exist venv\Scripts\activate.bat (
  python -m venv venv
  if errorlevel 1 (
    echo Failed to create the virtual environment.
    pause
    exit /b
  )
)
call venv\Scripts\activate
echo [3/3] Installing packages...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package installation failed. Check your internet connection and try again.
  pause
  exit /b
)
echo.
echo Done. Start the app with run.bat
echo If you have an NVIDIA GPU, run setup_gpu.bat as well.
pause
