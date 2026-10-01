@echo off
REM Builds the release files on Windows: a zip (folder build) and the single portable .exe.
REM Needs Python 3.12 and:  pip install -r requirements-build.txt
REM Output: release\ContourMapGenerator-<version>-win64.zip
REM         release\ContourMapGenerator-<version>-portable.exe
REM         release\SHA256SUMS.txt
python tools\build_release.py --licenses
if %ERRORLEVEL% neq 0 (
  echo ERROR: the build failed.
  pause
  exit /b %ERRORLEVEL%
)
echo.
echo Done. See the release folder.
pause
