@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  AI STT Studio - Windows Build Script
echo ============================================================
echo.

:: ============================================================
:: CONFIG - edit these if the repo moves
:: ============================================================
set REPO_URL=https://github.com/kwkim-gif/5555.git
set REPO_BRANCH=claude/wonderful-dijkstra-ht66iw
set SOURCE_DIR=%~dp0src
:: ============================================================

:: --- Step 1: Check Python ---
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo         Install Python 3.11+ from https://www.python.org
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER%

:: --- Step 2: Download source from GitHub ---
echo.
echo [*] Downloading source from GitHub...
echo     %REPO_URL%  (branch: %REPO_BRANCH%)
echo.

git --version > nul 2>&1
if %errorlevel% equ 0 (
    goto :USE_GIT
) else (
    goto :USE_CURL
)

:USE_GIT
echo [*] git found - cloning repository...
if exist "%SOURCE_DIR%\.git" (
    echo [*] Repository already exists - pulling latest...
    git -C "%SOURCE_DIR%" fetch origin %REPO_BRANCH%
    git -C "%SOURCE_DIR%" checkout %REPO_BRANCH%
    git -C "%SOURCE_DIR%" pull origin %REPO_BRANCH%
) else (
    git clone --branch %REPO_BRANCH% --depth 1 %REPO_URL% "%SOURCE_DIR%"
)
if %errorlevel% neq 0 (
    echo [ERROR] git clone/pull failed.
    pause
    exit /b 1
)
echo [OK] Source downloaded via git.
goto :BUILD

:USE_CURL
echo [*] git not found - downloading via curl (zip archive)...
set ZIP_URL=https://github.com/kwkim-gif/5555/archive/refs/heads/claude/wonderful-dijkstra-ht66iw.zip
set ZIP_FILE=%~dp0_source.zip

curl -L -o "%ZIP_FILE%" "%ZIP_URL%"
if %errorlevel% neq 0 (
    echo [ERROR] curl download failed.
    echo         Install git from https://git-scm.com and retry.
    pause
    exit /b 1
)

echo [*] Extracting archive...
if exist "%SOURCE_DIR%" rmdir /s /q "%SOURCE_DIR%"
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%~dp0_extracted' -Force"
:: GitHub zip extracts to "reponame-branchname" folder - rename it
for /d %%D in ("%~dp0_extracted\*") do (
    move "%%D" "%SOURCE_DIR%"
    goto :extracted
)
:extracted
del "%ZIP_FILE%" 2>nul
rmdir /s /q "%~dp0_extracted" 2>nul
echo [OK] Source extracted.

:BUILD
:: --- Step 3: Create build venv ---
echo.
echo [*] Setting up build environment...
if not exist "%~dp0.build_venv\Scripts\activate.bat" (
    python -m venv "%~dp0.build_venv"
)
call "%~dp0.build_venv\Scripts\activate.bat"

:: --- Step 4: Install build tools ---
echo [*] Installing PyInstaller and Pillow...
pip install pyinstaller pillow --quiet --upgrade
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install build tools.
    pause
    exit /b 1
)

:: --- Step 5: Generate icon ---
if not exist "%SOURCE_DIR%\assets\icon.ico" (
    echo [*] Generating icon...
    mkdir "%SOURCE_DIR%\assets" 2>nul
    python "%SOURCE_DIR%\make_icon.py"
)

:: --- Step 6: PyInstaller build ---
echo.
echo [*] Building AISTTStudio.exe with PyInstaller...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "AISTTStudio" ^
    --icon "%SOURCE_DIR%\assets\icon.ico" ^
    --add-data "%SOURCE_DIR%\assets;assets" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --version-file "%SOURCE_DIR%\version_info.txt" ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build_tmp" ^
    --specpath "%~dp0build_tmp" ^
    "%SOURCE_DIR%\launcher.py"

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

:: --- Step 7: Assemble distribution package ---
echo.
echo [*] Assembling distribution package...

set PKG=%~dp0dist\AISTTStudio_Package
if exist "%PKG%" rmdir /s /q "%PKG%"
mkdir "%PKG%"

copy "%~dp0dist\AISTTStudio.exe" "%PKG%\"

xcopy /e /i /q "%SOURCE_DIR%\engines"   "%PKG%\engines\"
xcopy /e /i /q "%SOURCE_DIR%\audio"     "%PKG%\audio\"
xcopy /e /i /q "%SOURCE_DIR%\subtitle"  "%PKG%\subtitle\"
xcopy /e /i /q "%SOURCE_DIR%\ui"        "%PKG%\ui\"
xcopy /e /i /q "%SOURCE_DIR%\workers"   "%PKG%\workers\"
xcopy /e /i /q "%SOURCE_DIR%\benchmark" "%PKG%\benchmark\"
xcopy /e /i /q "%SOURCE_DIR%\config"    "%PKG%\config\"

copy "%SOURCE_DIR%\app.py"           "%PKG%\"
copy "%SOURCE_DIR%\requirements.txt" "%PKG%\"

mkdir "%PKG%\logs"       2>nul
mkdir "%PKG%\error_logs" 2>nul
mkdir "%PKG%\output"     2>nul

echo.
echo ============================================================
echo  Build complete!
echo  Package : dist\AISTTStudio_Package\
echo  Launcher: dist\AISTTStudio_Package\AISTTStudio.exe
echo.
echo  To create an installer (.exe):
echo    ISCC.exe installer.iss
echo ============================================================
echo.

deactivate
pause
