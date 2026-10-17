@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Run this file as administrator.
  pause
  exit /b 1
)
schtasks /end /tn "PCRemoteServer" >nul 2>&1
schtasks /delete /tn "PCRemoteServer" /f
netsh advfirewall firewall delete rule name="PC Remote 8765"
echo.
echo Autostart removed.
pause
