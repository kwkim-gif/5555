# AI STT Studio — 배포 빌드 가이드

## 배포 방식 개요

```
더블클릭
   │
   ▼
AISTTStudio.exe  ← PyInstaller 빌드 (tkinter만 포함, ~6 MB)
   │
   ├─ .venv 존재?
   │     NO → 설치 진행창 표시 → pip install → 완료
   │     YES → 즉시 실행
   │
   └─▶  app.py 실행 (PySide6 GUI 표시)
```

---

## 빌드 순서 (Windows)

### 사전 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.11 이상 (`python --version`으로 확인) |
| Inno Setup *(설치 파일 생성 시만 필요)* | 6.x |

### Step 1 — 빌드 실행

```bat
build.bat
```

- 자동으로 `.build_venv` 생성
- PyInstaller로 `dist/AISTTStudio.exe` 빌드
- `dist/AISTTStudio_Package/` 에 배포 파일 구성

### Step 2 — 설치 파일 생성 (선택)

Inno Setup 설치 후:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

→ `dist/installer/AISTTStudio_Setup_v1.0.0.exe` 생성

---

## 배포 파일 구조

```
AISTTStudio_Package/
├── AISTTStudio.exe     ← 사용자가 실행하는 파일
├── app.py
├── requirements.txt
├── config/
├── engines/
├── audio/
├── subtitle/
├── ui/
├── workers/
├── benchmark/
├── logs/               (자동 생성)
├── error_logs/         (자동 생성)
└── output/             (기본 출력 폴더)
```

---

## 사용자 첫 실행 흐름

1. `AISTTStudio.exe` 더블클릭
2. 설치 진행창 자동 표시:
   - Python 버전 확인
   - `.venv` 가상환경 생성
   - `pip install -r requirements.txt` (최초 1회, ~5~15분)
   - 완료 후 자동으로 메인 GUI 실행
3. 두 번째 실행부터는 설치 과정 없이 즉시 GUI 실행

---

## CUDA 패키지 설치 (GPU 가속)

`requirements.txt`의 torch는 CPU 버전이 기본 설치됩니다.
GPU 가속을 위해서는 사용자가 CUDA 버전에 맞는 PyTorch를 재설치해야 합니다.

앱의 `.venv\Scripts\pip.exe`를 사용:

```bat
.venv\Scripts\pip.exe install torch torchvision torchaudio ^
    --index-url https://download.pytorch.org/whl/cu124
```

또는 `settings_dialog` > CUDA 탭에서 디바이스를 `cuda`로 변경하면
VRAM 상태가 자동 감지됩니다.

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| `.venv` 설치 실패 | 로그창 확인 후 `error_logs/` 폴더 참조 |
| 앱이 열리지 않음 | `.venv\Scripts\python.exe app.py` 직접 실행하여 오류 확인 |
| 모델 다운로드 실패 | 네트워크 확인, `.model_cache/` 폴더 삭제 후 재시도 |
| CUDA 미인식 | CUDA 버전에 맞는 PyTorch 재설치 (위 참고) |
