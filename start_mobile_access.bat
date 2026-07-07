@echo off
setlocal

cd /d "%~dp0"
call "%~dp0start_app.bat"

set "TAILSCALE_EXE="
where tailscale >nul 2>nul
if not errorlevel 1 set "TAILSCALE_EXE=tailscale"
if "%TAILSCALE_EXE%"=="" if exist "C:\Program Files\Tailscale\tailscale.exe" set "TAILSCALE_EXE=C:\Program Files\Tailscale\tailscale.exe"

if "%TAILSCALE_EXE%"=="" (
  echo.
  echo Tailscale is not installed or not on PATH yet.
  echo Install Tailscale on this PC and on the phone/iPad, then run:
  echo   tailscale serve --bg localhost:5000
  echo.
  pause
  exit /b 0
)

echo.
echo Enabling private mobile access through Tailscale...
"%TAILSCALE_EXE%" serve --bg localhost:5000
if errorlevel 1 (
  echo.
  echo Tailscale Serve could not be enabled automatically.
  echo Try this manually in PowerShell:
  echo   tailscale serve --bg localhost:5000
  echo   tailscale serve status
  echo.
  pause
  exit /b 1
)

echo.
echo Tailscale Serve is on. Your private access URL should appear below:
"%TAILSCALE_EXE%" serve status
echo.
echo Open that HTTPS Tailscale URL on your iPad or phone after signing into Tailscale there.
pause
exit /b 0
