@echo off
cd /d "%~dp0"

set PY=python
python --version >nul 2>&1 || set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Using: %PY%
%PY% --version

echo.
echo [1/3] Installing packages...
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo [ERROR] Package install failed. Copy the error text above.
  pause
  exit /b 1
)

echo.
taskkill /f /im PCRemote.exe >nul 2>&1
echo [2/3] Building PCRemote.exe - this takes a few minutes...
%PY% -m PyInstaller --noconfirm --onefile --noconsole --name PCRemote --add-data "index.html;." --hidden-import pystray._win32 --collect-submodules zeroconf server.py
if errorlevel 1 (
  echo [ERROR] Build failed. Copy the error text above.
  pause
  exit /b 1
)

echo.
echo [3/3] Copying...
copy /y dist\PCRemote.exe PCRemote.exe
if errorlevel 1 (
  echo [ERROR] Could not copy the exe.
  pause
  exit /b 1
)

echo.
echo DONE. PCRemote.exe is in this folder.
echo Next: run install_autostart.bat as administrator.
pause
