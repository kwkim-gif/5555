@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ============================================================
echo  AI STT Studio — Windows 빌드 스크립트
echo ============================================================
echo.

:: ── 1. Python 확인 ────────────────────────────────────────────
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python이 PATH에 없습니다.
    echo         https://www.python.org 에서 Python 3.11+ 설치 후 재실행하세요.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER%

:: ── 2. 빌드용 가상환경 ────────────────────────────────────────
if not exist ".build_venv\Scripts\activate.bat" (
    echo [*] 빌드용 venv 생성 중...
    python -m venv .build_venv
)
call .build_venv\Scripts\activate.bat

:: ── 3. PyInstaller 설치 ────────────────────────────────────────
echo [*] PyInstaller 설치 중...
pip install pyinstaller pillow --quiet --upgrade

:: ── 4. 아이콘 생성 (아이콘 파일이 없을 경우 기본 아이콘 생성) ──
if not exist "assets\icon.ico" (
    echo [*] 기본 아이콘 생성 중...
    mkdir assets 2>nul
    python -c "
from PIL import Image, ImageDraw, ImageFont
import os

img = Image.new('RGBA', (256, 256), (30, 30, 30, 255))
d = ImageDraw.Draw(img)
d.ellipse([20, 20, 236, 236], fill=(79, 195, 247, 255))
d.text((80, 90), 'STT', fill=(255,255,255,255))

sizes = [16, 32, 48, 64, 128, 256]
icons = []
for s in sizes:
    icons.append(img.resize((s, s), Image.LANCZOS))

icons[0].save('assets/icon.ico', format='ICO', sizes=[(s, s) for s in sizes],
              append_images=icons[1:])
print('icon saved')
"
)

:: ── 5. PyInstaller 빌드 ────────────────────────────────────────
echo.
echo [*] PyInstaller로 launcher.exe 빌드 중...
echo     (tkinter만 의존하므로 빠르게 완료됩니다)
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
    echo [ERROR] PyInstaller 빌드 실패
    pause
    exit /b 1
)

:: ── 6. 배포 폴더 구성 ─────────────────────────────────────────
echo.
echo [*] 배포 패키지 구성 중...

if exist "dist\AISTTStudio_Package" rmdir /s /q "dist\AISTTStudio_Package"
mkdir "dist\AISTTStudio_Package"

:: exe 복사
copy "dist\AISTTStudio.exe" "dist\AISTTStudio_Package\"

:: 소스 파일 복사
xcopy /e /i /q "engines"   "dist\AISTTStudio_Package\engines\"
xcopy /e /i /q "audio"     "dist\AISTTStudio_Package\audio\"
xcopy /e /i /q "subtitle"  "dist\AISTTStudio_Package\subtitle\"
xcopy /e /i /q "ui"        "dist\AISTTStudio_Package\ui\"
xcopy /e /i /q "workers"   "dist\AISTTStudio_Package\workers\"
xcopy /e /i /q "benchmark" "dist\AISTTStudio_Package\benchmark\"
xcopy /e /i /q "config"    "dist\AISTTStudio_Package\config\"

copy "app.py"           "dist\AISTTStudio_Package\"
copy "requirements.txt" "dist\AISTTStudio_Package\"

:: 빈 폴더 생성
mkdir "dist\AISTTStudio_Package\logs"        2>nul
mkdir "dist\AISTTStudio_Package\error_logs"  2>nul
mkdir "dist\AISTTStudio_Package\output"      2>nul

echo.
echo ============================================================
echo  빌드 완료!
echo  배포 폴더: dist\AISTTStudio_Package\
echo  실행 파일: dist\AISTTStudio_Package\AISTTStudio.exe
echo.
echo  ※ Inno Setup이 설치되어 있다면 installer.iss를 컴파일하여
echo    단일 설치파일(.exe)을 생성할 수 있습니다.
echo ============================================================
echo.

deactivate
pause
