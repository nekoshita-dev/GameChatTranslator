@echo off
rem GameChat Translator を管理者権限で起動します
rem 別のゲームで起動する例:  run.bat --game apex
net session >nul 2>&1
if %errorlevel% neq 0 (
  if "%~1"=="" (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  ) else (
    powershell -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
  )
  exit /b
)
cd /d %~dp0
if not exist venv\Scripts\activate.bat (
  echo Please run setup.bat first.
  pause
  exit /b
)
call venv\Scripts\activate
python -m gamechat %*
if errorlevel 1 pause
