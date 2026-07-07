@echo off
setlocal

cd /d "%~dp0"
set "KEY_FILE=.openai_api_key"

if not exist ".venv\Scripts\python.exe" (
  echo Local virtual environment not found at .venv\Scripts\python.exe
  echo Run: py -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if "%OPENAI_API_KEY%"=="" (
  if exist "%KEY_FILE%" (
    set /p OPENAI_API_KEY=<"%KEY_FILE%"
  )
)

if "%OPENAI_API_KEY%"=="" (
  echo AI Insights is not configured yet.
  echo To enable it, save your OpenAI API key in:
  echo   %CD%\%KEY_FILE%
  echo.
  echo The app will still open normally without AI Insights.
  echo.
)

set "SHOPFLOW_HOST=127.0.0.1"
set "SHOPFLOW_PORT=5000"
set "SHOPFLOW_THREADS=8"

start "ShopFlow Server" /min ".venv\Scripts\python.exe" serve_waitress.py

set "APP_URL=http://127.0.0.1:5000"
set "WAIT_SCRIPT=%TEMP%\shopflow_wait_%RANDOM%%RANDOM%.ps1"
(
  echo $url = '%APP_URL%'
  echo $deadline = ^(Get-Date^).AddSeconds^(30^)
  echo do {
  echo   Start-Sleep -Milliseconds 500
  echo   try {
  echo     $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2
  echo     if ^($response.StatusCode -ge 200 -and $response.StatusCode -lt 500^) {
  echo       Start-Process $url
  echo       exit 0
  echo     }
  echo   } catch {}
  echo } while ^((Get-Date^) -lt $deadline^)
  echo Start-Process $url
) > "%WAIT_SCRIPT%"

powershell -ExecutionPolicy Bypass -File "%WAIT_SCRIPT%"
del "%WAIT_SCRIPT%" >nul 2>nul
exit /b 0
