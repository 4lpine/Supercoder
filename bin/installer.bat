@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: SuperCoder Installer Batch Script
:: This script downloads and installs SuperCoder with the same functionality
:: as the installer.exe
:: ============================================================================

set "REPO_ZIP=https://github.com/4lpine/Supercoder/archive/refs/heads/main.zip"
set "DEFAULT_INSTALL=%USERPROFILE%\supercoder"

:: Print banner
echo.
echo   ==================================================
echo    SuperCoder Setup
echo   ==================================================
echo.

:: ============================================================================
:: [1/4] Check Python
:: ============================================================================
echo   [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo         Python not found!
    echo         Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo         Found: !PYTHON_VERSION!

:: ============================================================================
:: Get install directory
:: ============================================================================
echo.
set /p "INSTALL_DIR=  Install directory [%DEFAULT_INSTALL%]: "
if "!INSTALL_DIR!"=="" set "INSTALL_DIR=%DEFAULT_INSTALL%"

:: ============================================================================
:: [2/4] Download SuperCoder
:: ============================================================================
echo.
echo   [2/4] Downloading SuperCoder...
set "TEMP_ZIP=%TEMP%\supercoder.zip"
set "TEMP_EXTRACT=%TEMP%\supercoder-extract"

:: Download using PowerShell with TLS 1.2
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try {Invoke-WebRequest -Uri '%REPO_ZIP%' -OutFile '%TEMP_ZIP%' -UseBasicParsing -ErrorAction Stop} catch {exit 1}}" >nul 2>&1
if errorlevel 1 (
    echo         Error: Failed to download SuperCoder
    echo         Please check your internet connection
    echo.
    pause
    exit /b 1
)

:: Extract using PowerShell
if exist "%TEMP_EXTRACT%" rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {try {Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_EXTRACT%' -Force -ErrorAction Stop} catch {exit 1}}" >nul 2>&1
if errorlevel 1 (
    echo         Error: Failed to extract archive
    del "%TEMP_ZIP%" >nul 2>&1
    echo.
    pause
    exit /b 1
)

:: Find extracted folder (should be Supercoder-main)
for /d %%i in ("%TEMP_EXTRACT%\*") do set "EXTRACTED_FOLDER=%%i"

:: Copy to install directory
if exist "%INSTALL_DIR%" (
    echo         Removing old installation...
    rmdir /s /q "%INSTALL_DIR%" >nul 2>&1
)
xcopy "%EXTRACTED_FOLDER%" "%INSTALL_DIR%\" /E /I /Q /Y >nul 2>&1
if errorlevel 1 (
    echo         Error: Failed to copy files to %INSTALL_DIR%
    echo         Make sure you have write permissions
    del "%TEMP_ZIP%" >nul 2>&1
    rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1
    echo.
    pause
    exit /b 1
)

:: Cleanup temporary files
del "%TEMP_ZIP%" >nul 2>&1
rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1
echo         Downloaded to %INSTALL_DIR%

:: ============================================================================
:: [3/4] Install dependencies
:: ============================================================================
echo   [3/4] Installing dependencies...
python -m pip install requests colorama -q >nul 2>&1
if errorlevel 1 (
    echo         Warning: Failed to install some dependencies
    echo         You may need to run: pip install requests colorama
) else (
    echo         Done
)

:: ============================================================================
:: [4/4] Create launcher
:: ============================================================================
echo   [4/4] Creating launcher...
set "BIN_DIR=%INSTALL_DIR%\bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
set "LAUNCHER=%BIN_DIR%\supercoder.cmd"

:: Create launcher batch file
(
echo @echo off
echo python "%%~dp0..\main.py" %%*
) > "%LAUNCHER%"

echo         Created %LAUNCHER%

:: Add to PATH using PowerShell (more reliable than reg commands)
echo         Adding to PATH...
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {$path = [Environment]::GetEnvironmentVariable('Path', 'User'); if ($path -notlike '*%BIN_DIR%*') {[Environment]::SetEnvironmentVariable('Path', $path + ';%BIN_DIR%', 'User'); Write-Host '        PATH updated'} else {Write-Host '        Already in PATH'}}" 2>&1 | findstr /V "^$"

:: ============================================================================
:: Success message
:: ============================================================================
echo.
echo   ==================================================
echo    Setup Complete!
echo   ==================================================
echo.
echo   To start using SuperCoder:
echo   1. Open a NEW terminal window
echo   2. Type: supercoder
echo.
echo   Installation directory: %INSTALL_DIR%
echo.
pause
exit /b 0

