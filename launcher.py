"""
AI STT Studio — Windows launcher.

역할:
  1. 첫 실행: tkinter GUI로 진행상황을 표시하며 venv 생성 + pip install
  2. 이후 실행: 즉시 app.py 실행

이 파일은 PyInstaller로 단독 exe로 빌드되며,
Python / PySide6 설치 여부와 무관하게 동작한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# ── 경로 설정 ──────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller 빌드 환경: exe가 있는 폴더가 작업 디렉토리
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.resolve()

VENV_DIR = APP_DIR / ".venv"
PYTHON_BIN = VENV_DIR / "Scripts" / "python.exe"
PIP_BIN = VENV_DIR / "Scripts" / "pip.exe"
APP_SCRIPT = APP_DIR / "app.py"
REQ_FILE = APP_DIR / "requirements.txt"

WINDOW_W, WINDOW_H = 560, 380


# ──────────────────────────────────────────────────────────────────────────
# Setup GUI (tkinter — 표준 라이브러리이므로 추가 설치 불필요)
# ──────────────────────────────────────────────────────────────────────────

class SetupWindow:
    """첫 실행 환경 구성 진행창."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AI STT Studio — 환경 초기화")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e1e")
        self._center()
        self._build()
        self._success = False

    def _center(self) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - WINDOW_W) // 2
        y = (sh - WINDOW_H) // 2
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")

    def _build(self) -> None:
        # 로고 / 제목
        tk.Label(
            self.root,
            text="AI STT Studio",
            font=("Segoe UI", 18, "bold"),
            fg="#4fc3f7",
            bg="#1e1e1e",
        ).pack(pady=(28, 2))

        tk.Label(
            self.root,
            text="日本語 音声転写ツール",
            font=("Segoe UI", 10),
            fg="#aaaaaa",
            bg="#1e1e1e",
        ).pack()

        # 상태 메시지
        self._status_var = tk.StringVar(value="환경 확인 중...")
        tk.Label(
            self.root,
            textvariable=self._status_var,
            font=("Segoe UI", 10),
            fg="#dddddd",
            bg="#1e1e1e",
            wraplength=480,
        ).pack(pady=(24, 6))

        # 진행바
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor="#2d2d2d",
            background="#4fc3f7",
            bordercolor="#1e1e1e",
            lightcolor="#4fc3f7",
            darkcolor="#4fc3f7",
        )
        self._progress = ttk.Progressbar(
            self.root,
            style="Custom.Horizontal.TProgressbar",
            orient="horizontal",
            length=480,
            mode="indeterminate",
        )
        self._progress.pack(pady=4)

        # 세부 로그
        log_frame = tk.Frame(self.root, bg="#2d2d2d", padx=2, pady=2)
        log_frame.pack(fill="both", expand=True, padx=36, pady=(14, 14))
        self._log = tk.Text(
            log_frame,
            height=8,
            bg="#2d2d2d",
            fg="#cccccc",
            font=("Consolas", 8),
            relief="flat",
            state="disabled",
            wrap="word",
        )
        sb = tk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def log(self, msg: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")
        self.root.update_idletasks()

    def set_status(self, msg: str) -> None:
        self._status_var.set(msg)
        self.root.update_idletasks()

    def set_progress_determinate(self, value: int) -> None:
        self._progress.stop()
        self._progress.configure(mode="determinate", maximum=100, value=value)
        self.root.update_idletasks()

    def start_indeterminate(self) -> None:
        self._progress.configure(mode="indeterminate")
        self._progress.start(12)

    def run_setup_thread(self) -> None:
        self.start_indeterminate()
        t = threading.Thread(target=self._setup_worker, daemon=True)
        t.start()
        self.root.mainloop()
        return self._success

    # ── 실제 설치 로직 (별도 스레드) ──────────────────────────────────────

    def _setup_worker(self) -> None:
        try:
            self._do_setup()
            self._success = True
            self.root.after(800, self.root.destroy)
        except Exception as exc:
            self.set_status(f"❌ 설치 실패: {exc}")
            self.log(f"\n오류: {exc}")
            self.log("\n수동으로 다음 명령을 실행하세요:")
            self.log(f"  python -m venv {VENV_DIR}")
            self.log(f"  {PIP_BIN} install -r {REQ_FILE}")
            # 오류 시 창을 닫지 않고 대기 (사용자가 읽을 수 있도록)

    def _do_setup(self) -> None:
        # Step 1: Python 버전 확인
        self.set_status("Python 버전 확인 중...")
        self.log(f"Python: {sys.version}")
        major, minor = sys.version_info[:2]
        if major < 3 or minor < 11:
            raise RuntimeError(f"Python 3.11 이상이 필요합니다. (현재: {major}.{minor})")

        # Step 2: venv 생성
        if not PYTHON_BIN.exists():
            self.set_status("가상환경(venv) 생성 중...")
            self.log(f"venv 생성: {VENV_DIR}")
            self._run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                "venv 생성 실패",
            )
            self.log("✅ venv 생성 완료")
        else:
            self.log(f"✅ 기존 venv 사용: {VENV_DIR}")

        # Step 3: pip 업그레이드
        self.set_status("pip 업그레이드 중...")
        self._run(
            [str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            "pip 업그레이드 실패",
        )

        # Step 4: 의존성 설치
        self.set_status("패키지 설치 중... (최초 1회, 수 분 소요)")
        self.log(f"requirements: {REQ_FILE}")
        self._run(
            [
                str(PYTHON_BIN), "-m", "pip", "install",
                "-r", str(REQ_FILE),
                "--quiet",
                "--no-warn-script-location",
            ],
            "패키지 설치 실패",
            stream=True,
        )
        self.log("✅ 모든 패키지 설치 완료")
        self.set_status("✅ 설치 완료! 앱을 시작합니다...")
        self.set_progress_determinate(100)

    def _run(self, cmd: list[str], error_msg: str, stream: bool = False) -> None:
        if stream:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.log(line)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"{error_msg} (code {proc.returncode})")
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.stdout.strip():
                self.log(result.stdout.strip())
            if result.returncode != 0:
                self.log(result.stderr.strip())
                raise RuntimeError(f"{error_msg} (code {result.returncode})")


# ──────────────────────────────────────────────────────────────────────────
# 런처 진입점
# ──────────────────────────────────────────────────────────────────────────

def is_env_ready() -> bool:
    """venv가 존재하고 PySide6이 설치되어 있으면 준비된 것으로 판단."""
    if not PYTHON_BIN.exists():
        return False
    result = subprocess.run(
        [str(PYTHON_BIN), "-c", "import PySide6"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return result.returncode == 0


def launch_app() -> None:
    """venv Python으로 app.py를 실행한다."""
    os.chdir(APP_DIR)
    subprocess.Popen(
        [str(PYTHON_BIN), str(APP_SCRIPT)],
        cwd=str(APP_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def main() -> None:
    os.chdir(APP_DIR)

    if not is_env_ready():
        win = SetupWindow()
        ok = win.run_setup_thread()
        if not ok:
            # 오류 발생 시 창은 열려 있으므로 종료하지 않음
            return

    launch_app()


if __name__ == "__main__":
    main()
