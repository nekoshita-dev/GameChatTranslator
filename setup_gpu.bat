@echo off
cd /d %~dp0
call venv\Scripts\activate
echo Installing CUDA libraries for NVIDIA GPU...
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
echo Done.
pause
