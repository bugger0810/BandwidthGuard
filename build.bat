@echo off
REM ===========================================================================
REM  BandwidthGuard - one-click build
REM  Creates dist\BandwidthGuard\ (the program) and installer\Output\*.exe (the setup).
REM
REM  Requirements:
REM    - Python 3.10 - 3.12 (python.org, "Add to PATH" ticked)
REM    - Inno Setup 6.3+  (https://jrsoftware.org/isdl.php) - only for the setup.exe
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/5] Creating virtual environment (.venv) ...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || goto :error
)
set "PY=%~dp0.venv\Scripts\python.exe"

echo.
echo [2/5] Installing dependencies ...
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements.txt -r requirements-dev.txt || goto :error

echo.
echo [3/5] Checking translations ...
"%PY%" tools\check_locales.py || goto :error

echo.
echo [4/5] Building the program with PyInstaller ...
"%PY%" tools\build.py || goto :error

echo.
echo [5/5] Building the setup with Inno Setup ...
for /f "delims=" %%v in ('"%PY%" -c "import sys; sys.path.insert(0,'src'); import bandwidthguard; print(bandwidthguard.__version__)"') do set "VERSION=%%v"

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo Inno Setup was not found - the setup.exe was NOT created.
    echo The program itself is ready in dist\BandwidthGuard\BandwidthGuard.exe
    echo Install Inno Setup 6 from https://jrsoftware.org/isdl.php and run build.bat again.
    goto :end
)

"%ISCC%" "/DMyAppVersion=%VERSION%" installer\BandwidthGuard.iss || goto :error

echo.
echo ===========================================================================
echo  Done!  Setup: installer\Output\BandwidthGuard-Setup-%VERSION%.exe
echo ===========================================================================
goto :end

:error
echo.
echo BUILD FAILED - see the messages above.
exit /b 1

:end
endlocal
