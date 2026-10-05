@echo off
REM Double-click to start SmartAgri AI. The browser opens at http://localhost:5000
cd /d "%~dp0"
python -c "import flask, torch, transformers" 2>nul
if errorlevel 1 (
  echo Installing required packages...
  python -m pip install -r requirements.txt
)
if not exist "models\plant-disease-mobilenetv2\model.safetensors" python scripts\download_model.py
start "" cmd /c "timeout /t 10 /nobreak >nul & start http://localhost:5000"
python run.py
pause
