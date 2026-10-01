@echo off
REM Clean previous build artifacts
echo Cleaning previous build folders...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q ContourMapApp_GUI.spec 2>nul

REM Build using PyInstaller (via python -m to avoid PATH problems)
echo Building ContourMapApp.exe (onefile, hidden console) ...
python -m PyInstaller --onefile --noconsole --name "ContourMapApp" --icon "contour.ico" "ContourMapApp_GUI.py"

if %ERRORLEVEL% neq 0 (
  echo ERROR: PyInstaller failed.
  pause
  exit /b %ERRORLEVEL%
)

echo Build finished. Output: dist\ContourMapApp.exe
pause
