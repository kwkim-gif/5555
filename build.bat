@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  AI STT Studio - Windows Build Script
echo ============================================================
echo.

:: ============================================================
:: CONFIG
:: ============================================================
set REPO_URL=https://github.com/kwkim-gif/5555.git
set REPO_BRANCH=claude/wonderful-dijkstra-ht66iw
set BUILD_ROOT=%~dp0
set SOURCE_DIR=%BUILD_ROOT%src
set PKG_DIR=%BUILD_ROOT%dist\AISTTStudio_Package
set ICON_PATH=%SOURCE_DIR%\assets\icon.ico
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
    echo [*] Repo exists - pulling latest...
    git -C "%SOURCE_DIR%" fetch origin %REPO_BRANCH%
    git -C "%SOURCE_DIR%" checkout %REPO_BRANCH%
    git -C "%SOURCE_DIR%" pull origin %REPO_BRANCH%
) else (
    git clone --branch %REPO_BRANCH% --depth 1 %REPO_URL% "%SOURCE_DIR%"
)
if %errorlevel% neq 0 (
    echo [ERROR] git failed.
    pause
    exit /b 1
)
echo [OK] Source ready.
goto :BUILD

:USE_CURL
echo [*] git not found - downloading zip via curl...
set ZIP_URL=https://github.com/kwkim-gif/5555/archive/refs/heads/claude/wonderful-dijkstra-ht66iw.zip
set ZIP_FILE=%BUILD_ROOT%_source.zip

curl -L -o "%ZIP_FILE%" "%ZIP_URL%"
if %errorlevel% neq 0 (
    echo [ERROR] curl download failed. Install git from https://git-scm.com
    pause
    exit /b 1
)
echo [*] Extracting...
if exist "%BUILD_ROOT%_extracted" rmdir /s /q "%BUILD_ROOT%_extracted"
if exist "%SOURCE_DIR%"           rmdir /s /q "%SOURCE_DIR%"
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%BUILD_ROOT%_extracted' -Force"
for /d %%D in ("%BUILD_ROOT%_extracted\*") do (
    move "%%D" "%SOURCE_DIR%"
    goto :curl_done
)
:curl_done
del "%ZIP_FILE%" 2>nul
rmdir /s /q "%BUILD_ROOT%_extracted" 2>nul
echo [OK] Source ready.

:BUILD
:: Verify source exists
if not exist "%SOURCE_DIR%\launcher.py" (
    echo [ERROR] launcher.py not found in %SOURCE_DIR%
    echo         Download may have failed. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Source verified: %SOURCE_DIR%\launcher.py

:: --- Step 3: Build venv ---
echo.
echo [*] Setting up build environment...
if not exist "%BUILD_ROOT%.build_venv\Scripts\activate.bat" (
    python -m venv "%BUILD_ROOT%.build_venv"
)
call "%BUILD_ROOT%.build_venv\Scripts\activate.bat"

:: --- Step 4: Install build tools ---
echo [*] Installing PyInstaller and Pillow...
pip install pyinstaller pillow --quiet --upgrade
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install build tools.
    pause
    exit /b 1
)

:: --- Step 5: Generate icon (explicit absolute path) ---
echo [*] Generating icon: %ICON_PATH%
mkdir "%SOURCE_DIR%\assets" 2>nul

python -c "
import sys, os
sys.path.insert(0, r'%SOURCE_DIR%')
output = r'%ICON_PATH%'
os.makedirs(os.path.dirname(output), exist_ok=True)
try:
    from PIL import Image, ImageDraw, ImageFont
    SIZE = 256
    img = Image.new('RGBA', (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    d.ellipse([4,4,SIZE-4,SIZE-4], fill=(25,118,210,255))
    d.ellipse([80,60,176,156], fill=(255,255,255,255))
    d.line([(128,156),(128,200)], fill=(255,255,255,255), width=10)
    d.line([(100,200),(156,200)], fill=(255,255,255,255), width=10)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype('arial.ttf', 36)
    except:
        font = ImageFont.load_default()
    d.text((100,210), 'AI', font=font, fill=(255,255,255,220))
    sizes = [16,24,32,48,64,128,256]
    icons = [img.resize((s,s), Image.LANCZOS) for s in sizes]
    icons[0].save(output, format='ICO', sizes=[(s,s) for s in sizes], append_images=icons[1:])
    print('[OK] Icon saved:', output)
except Exception as e:
    print('[WARN] Icon generation failed:', e)
    # Create a minimal 32x32 ICO as fallback
    try:
        img = Image.new('RGB', (32,32), (25,118,210))
        img.save(output, format='ICO')
        print('[OK] Fallback icon saved:', output)
    except Exception as e2:
        print('[ERROR] Could not create any icon:', e2)
        sys.exit(1)
"

if not exist "%ICON_PATH%" (
    echo [ERROR] Icon file was not created: %ICON_PATH%
    pause
    exit /b 1
)
echo [OK] Icon ready.

:: --- Step 6: PyInstaller build ---
echo.
echo [*] Building AISTTStudio.exe...
echo.

if exist "%BUILD_ROOT%build_tmp" rmdir /s /q "%BUILD_ROOT%build_tmp"

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "AISTTStudio" ^
    --icon "%ICON_PATH%" ^
    --add-data "%SOURCE_DIR%\assets;assets" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --version-file "%SOURCE_DIR%\version_info.txt" ^
    --distpath "%BUILD_ROOT%dist" ^
    --workpath "%BUILD_ROOT%build_tmp" ^
    --specpath "%BUILD_ROOT%build_tmp" ^
    "%SOURCE_DIR%\launcher.py"

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)
echo [OK] AISTTStudio.exe created.

:: --- Step 7: Assemble package ---
echo.
echo [*] Assembling distribution package...

if exist "%PKG_DIR%" rmdir /s /q "%PKG_DIR%"
mkdir "%PKG_DIR%"

copy "%BUILD_ROOT%dist\AISTTStudio.exe" "%PKG_DIR%\"

xcopy /e /i /q "%SOURCE_DIR%\engines"   "%PKG_DIR%\engines\"
xcopy /e /i /q "%SOURCE_DIR%\audio"     "%PKG_DIR%\audio\"
xcopy /e /i /q "%SOURCE_DIR%\subtitle"  "%PKG_DIR%\subtitle\"
xcopy /e /i /q "%SOURCE_DIR%\ui"        "%PKG_DIR%\ui\"
xcopy /e /i /q "%SOURCE_DIR%\workers"   "%PKG_DIR%\workers\"
xcopy /e /i /q "%SOURCE_DIR%\benchmark" "%PKG_DIR%\benchmark\"
xcopy /e /i /q "%SOURCE_DIR%\config"    "%PKG_DIR%\config\"

copy "%SOURCE_DIR%\app.py"           "%PKG_DIR%\"
copy "%SOURCE_DIR%\requirements.txt" "%PKG_DIR%\"

mkdir "%PKG_DIR%\logs"       2>nul
mkdir "%PKG_DIR%\error_logs" 2>nul
mkdir "%PKG_DIR%\output"     2>nul

echo.
echo ============================================================
echo  Build complete!
echo  Folder : %PKG_DIR%
echo  Exe    : %PKG_DIR%\AISTTStudio.exe
echo ============================================================
echo.

deactivate
pause
