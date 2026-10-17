@echo off
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Run this file as administrator: right click - Run as administrator.
  pause
  exit /b 1
)

schtasks /end /tn "PCRemoteServer" >nul 2>&1
taskkill /f /im PCRemote.exe >nul 2>&1

if exist "%~dp0PCRemote.exe" goto EXE

set PY=python
python --version >nul 2>&1 || set PY=py
%PY% -m pip install -r requirements.txt
set "PYW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if not defined PYW (
  echo [ERROR] pythonw not found. Install Python from python.org with "Add to PATH", or run build.bat first to get PCRemote.exe.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1" -Exe "%PYW%" -Script "%~dp0server.py"
goto CHECK

:EXE
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1" -Exe "%~dp0PCRemote.exe"

:CHECK
if errorlevel 1 (
  echo [ERROR] Could not create the scheduled task. Copy the error text above.
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="PC Remote 8765" >nul 2>&1
netsh advfirewall firewall add rule name="PC Remote 8765" dir=in action=allow protocol=TCP localport=8765 profile=private
schtasks /run /tn "PCRemoteServer"

echo.
echo DONE. The PC Remote icon will appear in the system tray near the clock.
echo Click the icon to see the address and PIN.
pause
