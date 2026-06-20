"""
AI STT Studio - Windows launcher.

First run:  shows a tkinter setup window, creates venv, runs pip install.
Later runs: launches app.py immediately with no setup window.

This file is bundled into a standalone exe via PyInstaller and
works without any pre-installed packages (uses stdlib tkinter only).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# ── Paths ──────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.resolve()

VENV_DIR   = APP_DIR / ".venv"
PYTHON_BIN = VENV_DIR / "Scripts" / "python.exe"
APP_SCRIPT = APP_DIR / "app.py"
REQ_FILE   = APP_DIR / "requirements.txt"

WINDOW_W, WINDOW_H = 560, 380


# ──────────────────────────────────────────────────────────────────────────
# Setup GUI
# ──────────────────────────────────────────────────────────────────────────

class SetupWindow:
    """First-run environment setup progress window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AI STT Studio - Setup")
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
        tk.Label(
            self.root,
            text="AI STT Studio",
            font=("Segoe UI", 18, "bold"),
            fg="#4fc3f7",
            bg="#1e1e1e",
        ).pack(pady=(28, 2))

        tk.Label(
            self.root,
            text="Japanese Speech Transcription Tool",
            font=("Segoe UI", 10),
            fg="#aaaaaa",
            bg="#1e1e1e",
        ).pack()

        self._status_var = tk.StringVar(value="Checking environment...")
        tk.Label(
            self.root,
            textvariable=self._status_var,
            font=("Segoe UI", 10),
            fg="#dddddd",
            bg="#1e1e1e",
            wraplength=480,
        ).pack(pady=(24, 6))

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

    def set_progress_done(self) -> None:
        self._progress.stop()
        self._progress.configure(mode="determinate", maximum=100, value=100)
        self.root.update_idletasks()

    def start_indeterminate(self) -> None:
        self._progress.configure(mode="indeterminate")
        self._progress.start(12)

    def run_setup_thread(self) -> bool:
        self.start_indeterminate()
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        self.root.mainloop()
        return self._success

    # ── Worker (runs in background thread) ────────────────────────────────

    def _worker(self) -> None:
        try:
            self._do_setup()
            self._success = True
            self.root.after(800, self.root.destroy)
        except Exception as exc:
            self.set_status(f"Setup failed: {exc}")
            self.log(f"\nError: {exc}")
            self.log("\nManual steps to fix:")
            self.log(f"  python -m venv {VENV_DIR}")
            self.log(f"  {VENV_DIR}\\Scripts\\pip install -r {REQ_FILE}")

    def _do_setup(self) -> None:
        self.set_status("Checking Python version...")
        self.log(f"Python: {sys.version}")
        major, minor = sys.version_info[:2]
        if major < 3 or minor < 11:
            raise RuntimeError(f"Python 3.11+ required. Found: {major}.{minor}")

        if not PYTHON_BIN.exists():
            self.set_status("Creating virtual environment...")
            self.log(f"Creating venv: {VENV_DIR}")
            self._run([sys.executable, "-m", "venv", str(VENV_DIR)], "venv creation failed")
            self.log("venv created.")
        else:
            self.log(f"Existing venv: {VENV_DIR}")

        self.set_status("Upgrading pip...")
        self._run(
            [str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            "pip upgrade failed",
        )

        self.set_status("Installing packages... (first run only, may take several minutes)")
        self.log(f"Requirements: {REQ_FILE}")
        self._run(
            [
                str(PYTHON_BIN), "-m", "pip", "install",
                "-r", str(REQ_FILE),
                "--quiet",
                "--no-warn-script-location",
            ],
            "Package installation failed",
            stream=True,
        )
        self.log("All packages installed.")
        self.set_status("Setup complete! Launching app...")
        self.set_progress_done()

    def _run(self, cmd: list[str], error_msg: str, stream: bool = False) -> None:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        if stream:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.log(line)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"{error_msg} (exit code {proc.returncode})")
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
            )
            if result.stdout.strip():
                self.log(result.stdout.strip())
            if result.returncode != 0:
                self.log(result.stderr.strip())
                raise RuntimeError(f"{error_msg} (exit code {result.returncode})")


# ──────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────

def is_env_ready() -> bool:
    if not PYTHON_BIN.exists():
        return False
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        [str(PYTHON_BIN), "-c", "import PySide6"],
        capture_output=True,
        creationflags=flags,
    )
    return result.returncode == 0


def launch_app() -> None:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(
        [str(PYTHON_BIN), str(APP_SCRIPT)],
        cwd=str(APP_DIR),
        creationflags=flags,
    )


def main() -> None:
    os.chdir(APP_DIR)

    if not is_env_ready():
        win = SetupWindow()
        ok = win.run_setup_thread()
        if not ok:
            return

    launch_app()


if __name__ == "__main__":
    main()
