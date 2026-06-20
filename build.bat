@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  AI STT Studio - Windows Build Script
echo ============================================================
echo.

:: --- Check Python ---
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo         Please install Python 3.11+ from https://www.python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER%

:: --- Create build venv ---
if not exist ".build_venv\Scripts\activate.bat" (
    echo [*] Creating build venv...
    python -m venv .build_venv
)
call .build_venv\Scripts\activate.bat

:: --- Install PyInstaller ---
echo [*] Installing PyInstaller...
pip install pyinstaller pillow --quiet --upgrade

:: --- Generate icon if missing ---
if not exist "assets\icon.ico" (
    echo [*] Generating default icon...
    mkdir assets 2>nul
    python make_icon.py
)

:: --- PyInstaller build ---
echo.
echo [*] Building launcher.exe with PyInstaller...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "AISTTStudio" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --version-file "version_info.txt" ^
    launcher.py

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

:: --- Assemble distribution folder ---
echo.
echo [*] Assembling distribution package...

if exist "dist\AISTTStudio_Package" rmdir /s /q "dist\AISTTStudio_Package"
mkdir "dist\AISTTStudio_Package"

copy "dist\AISTTStudio.exe" "dist\AISTTStudio_Package\"

xcopy /e /i /q "engines"   "dist\AISTTStudio_Package\engines\"
xcopy /e /i /q "audio"     "dist\AISTTStudio_Package\audio\"
xcopy /e /i /q "subtitle"  "dist\AISTTStudio_Package\subtitle\"
xcopy /e /i /q "ui"        "dist\AISTTStudio_Package\ui\"
xcopy /e /i /q "workers"   "dist\AISTTStudio_Package\workers\"
xcopy /e /i /q "benchmark" "dist\AISTTStudio_Package\benchmark\"
xcopy /e /i /q "config"    "dist\AISTTStudio_Package\config\"

copy "app.py"           "dist\AISTTStudio_Package\"
copy "requirements.txt" "dist\AISTTStudio_Package\"

mkdir "dist\AISTTStudio_Package\logs"       2>nul
mkdir "dist\AISTTStudio_Package\error_logs" 2>nul
mkdir "dist\AISTTStudio_Package\output"     2>nul

echo.
echo ============================================================
echo  Build complete!
echo  Package : dist\AISTTStudio_Package\
echo  Launcher: dist\AISTTStudio_Package\AISTTStudio.exe
echo.
echo  To create an installer, run:
echo    ISCC.exe installer.iss
echo ============================================================
echo.

deactivate
pause
