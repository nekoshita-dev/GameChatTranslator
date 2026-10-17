@echo off
rem GameChat Translator の動作チェック（ゲームは起動しなくてOK）
cd /d %~dp0
if not exist venv\Scripts\activate.bat (
  echo Please run setup.bat first.
  pause
  exit /b
)
call venv\Scripts\activate
python -m gamechat --check %*
pause
