"""Main application window."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import torch
from loguru import logger
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audio.preprocess import PreprocessConfig
from engines import ENGINE_REGISTRY
from engines.base_engine import EngineConfig
from ui.settings_dialog import SettingsDialog
from workers.transcription_worker import TranscriptionWorker


class VRAMBar(QWidget):
    """Compact VRAM usage indicator."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("VRAM: N/A")
        from PySide6.QtWidgets import QProgressBar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setMaximumWidth(150)
        self._bar.setMaximumHeight(14)
        layout.addWidget(self._label)
        layout.addWidget(self._bar)

        self._total_mb = 0.0
        if torch.cuda.is_available():
            self._total_mb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 2

    def update_usage(self, used_mb: float) -> None:
        if self._total_mb > 0:
            pct = int(used_mb / self._total_mb * 100)
            self._bar.setValue(pct)
            self._label.setText(f"VRAM: {used_mb:.0f}/{self._total_mb:.0f} MB ({pct}%)")
        else:
            self._label.setText(f"VRAM: {used_mb:.0f} MB")


class MainWindow(QMainWindow):
    """AI STT Studio main window."""

    SUPPORTED_EXTS = "*.mp4 *.mkv *.avi *.mov *.ts *.wav *.mp3 *.m4a *.flac *.ogg"

    def __init__(self, app_config: dict) -> None:
        super().__init__()
        self._cfg = app_config
        self._worker: Optional[TranscriptionWorker] = None
        self._settings: dict = self._build_default_settings()

        self.setWindowTitle("AI STT Studio")
        self.resize(1280, 800)

        self._build_menu()
        self._build_central()
        self._build_status_bar()
        self._apply_dark_palette()

        self._vram_timer = QTimer(self)
        self._vram_timer.timeout.connect(self._poll_vram)
        self._vram_timer.start(2000)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        open_act = QAction("Open File", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._pick_file)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("Exit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        tool_menu = menubar.addMenu("Tools")
        bench_act = QAction("Model Benchmark", self)
        bench_act.triggered.connect(self._open_benchmark)
        tool_menu.addAction(bench_act)
        wer_act = QAction("WER / CER Measure", self)
        wer_act.triggered.connect(self._open_wer_dialog)
        tool_menu.addAction(wer_act)

        help_menu = menubar.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setAlignment(Qt.AlignTop)
        left_layout.addWidget(self._grp_file())
        left_layout.addWidget(self._grp_model())
        left_layout.addWidget(self._grp_output())
        left_layout.addWidget(self._grp_preprocess())
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)

        log_grp = QGroupBox("Live Log")
        lg = QVBoxLayout(log_grp)
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 9))
        lg.addWidget(self._log_view)
        right_layout.addWidget(log_grp, 3)

        result_grp = QGroupBox("Transcription Result")
        rg = QVBoxLayout(result_grp)
        self._result_view = QTextEdit()
        self._result_view.setReadOnly(True)
        self._result_view.setFont(QFont("Yu Gothic", 11))
        rg.addWidget(self._result_view)
        right_layout.addWidget(result_grp, 2)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([380, 860])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(splitter)

        bottom = QHBoxLayout()
        self._start_btn = QPushButton("Start Transcription")
        self._start_btn.setMinimumHeight(40)
        self._start_btn.clicked.connect(self._start_transcription)
        self._start_btn.setStyleSheet("font-size:14px; font-weight:bold;")

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_transcription)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setMinimumHeight(40)
        self._settings_btn.clicked.connect(self._open_settings)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

        bottom.addWidget(self._start_btn)
        bottom.addWidget(self._stop_btn)
        bottom.addWidget(self._settings_btn)
        bottom.addWidget(self._progress_bar, 1)
        root_layout.addLayout(bottom)
        self.setCentralWidget(root)

    # ------------------------------------------------------------------
    # Left panel groups
    # ------------------------------------------------------------------

    def _grp_file(self) -> QGroupBox:
        grp = QGroupBox("Input File")
        layout = QVBoxLayout(grp)
        row = QHBoxLayout()
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Select a video or audio file...")
        self._file_edit.setReadOnly(True)
        btn = QPushButton("Browse")
        btn.clicked.connect(self._pick_file)
        row.addWidget(self._file_edit)
        row.addWidget(btn)
        layout.addLayout(row)
        self._file_info_label = QLabel("")
        self._file_info_label.setWordWrap(True)
        layout.addWidget(self._file_info_label)
        return grp

    def _grp_model(self) -> QGroupBox:
        grp = QGroupBox("Model")
        layout = QVBoxLayout(grp)
        self._model_combo = QComboBox()
        self._model_combo.addItems(list(ENGINE_REGISTRY.keys()))
        last = self._cfg.get("model", {}).get("last_used", "kotoba-whisper-v2")
        idx = self._model_combo.findText(last)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        layout.addWidget(self._model_combo)

        device_str = "CUDA available" if torch.cuda.is_available() else "CPU only"
        if torch.cuda.is_available():
            device_str = f"CUDA | {torch.cuda.get_device_name(0)}"
        self._device_label = QLabel(device_str)
        layout.addWidget(self._device_label)
        return grp

    def _grp_output(self) -> QGroupBox:
        grp = QGroupBox("Output")
        layout = QVBoxLayout(grp)
        row = QHBoxLayout()
        self._out_edit = QLineEdit()
        self._out_edit.setText(str(Path("output").resolve()))
        btn = QPushButton("Browse")
        btn.clicked.connect(self._pick_output_dir)
        row.addWidget(self._out_edit)
        row.addWidget(btn)
        layout.addLayout(row)

        fmt_row = QHBoxLayout()
        self._chk_srt = QCheckBox("SRT")
        self._chk_srt.setChecked(True)
        self._chk_txt = QCheckBox("TXT")
        self._chk_txt.setChecked(True)
        self._chk_json = QCheckBox("JSON")
        fmt_row.addWidget(self._chk_srt)
        fmt_row.addWidget(self._chk_txt)
        fmt_row.addWidget(self._chk_json)
        layout.addLayout(fmt_row)
        return grp

    def _grp_preprocess(self) -> QGroupBox:
        grp = QGroupBox("Preprocessing")
        layout = QVBoxLayout(grp)
        self._chk_noise = QCheckBox("Noise Reduction")
        self._chk_norm = QCheckBox("Volume Normalization")
        self._chk_norm.setChecked(True)
        self._chk_silence = QCheckBox("Silence Removal")
        self._chk_vad = QCheckBox("VAD")
        self._chk_vad.setChecked(True)
        self._chk_resample = QCheckBox("Resample to 16kHz")
        self._chk_resample.setChecked(True)
        for w in [self._chk_noise, self._chk_norm, self._chk_silence, self._chk_vad, self._chk_resample]:
            layout.addWidget(w)
        return grp

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("Ready")
        self._vram_bar = VRAMBar()
        sb.addWidget(self._status_label, 1)
        sb.addPermanentWidget(self._vram_bar)

    # ------------------------------------------------------------------
    # Dark palette
    # ------------------------------------------------------------------

    def _apply_dark_palette(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        self.setPalette(palette)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "",
            f"Media Files ({self.SUPPORTED_EXTS});;All Files (*)"
        )
        if path:
            self._file_edit.setText(path)
            size_mb = Path(path).stat().st_size / 1024 ** 2
            self._file_info_label.setText(f"{Path(path).name}  ({size_mb:.1f} MB)")

    def _pick_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d:
            self._out_edit.setText(d)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, parent=self)
        if dlg.exec():
            self._settings = dlg.get_config()

    def _open_benchmark(self) -> None:
        from ui.benchmark_dialog import BenchmarkDialog
        dlg = BenchmarkDialog(
            engine_config=self._build_engine_config(),
            preprocess_config=self._build_preprocess_config(),
            parent=self,
        )
        dlg.exec()

    def _open_wer_dialog(self) -> None:
        from ui.wer_dialog import WERDialog
        dlg = WERDialog(parent=self)
        dlg.exec()

    def _show_about(self) -> None:
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only"
        QMessageBox.information(
            self, "AI STT Studio",
            f"AI STT Studio v1.0\n\n"
            f"Japanese Speech Transcription Tool\n"
            f"Models: ReazonSpeech K2-v2, Parakeet-TDT, Kotoba-Whisper-v2\n\n"
            f"GPU: {gpu}",
        )

    # ------------------------------------------------------------------
    # Transcription control
    # ------------------------------------------------------------------

    def _start_transcription(self) -> None:
        path = self._file_edit.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Error", "Please select a valid input file.")
            return

        formats = []
        if self._chk_srt.isChecked():  formats.append("srt")
        if self._chk_txt.isChecked():  formats.append("txt")
        if self._chk_json.isChecked(): formats.append("json")
        if not formats:
            QMessageBox.warning(self, "Error", "Select at least one output format.")
            return

        self._log_view.clear()
        self._result_view.clear()
        self._progress_bar.setValue(0)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("Transcribing...")

        self._worker = TranscriptionWorker(
            input_path=path,
            model_name=self._model_combo.currentText(),
            output_dir=self._out_edit.text(),
            engine_config=self._build_engine_config(),
            preprocess_config=self._build_preprocess_config(),
            output_formats=formats,
        )
        self._worker.progress.connect(self._progress_bar.setValue)
        self._worker.segment_ready.connect(self._on_segment)
        self._worker.log_message.connect(self._log_view.append)
        self._worker.vram_usage.connect(self._vram_bar.update_usage)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_transcription(self) -> None:
        if self._worker:
            self._worker.request_stop()
        self._stop_btn.setEnabled(False)

    def _on_segment(self, text: str, start: float, end: float) -> None:
        self._result_view.append(text)

    def _on_finished(self, out_dir: str) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText(f"Done -> {out_dir}")
        QMessageBox.information(self, "Done", f"Transcription complete.\n\nOutput: {out_dir}")

    def _on_error(self, msg: str) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Error")
        QMessageBox.critical(self, "Error", f"Transcription failed:\n\n{msg}")

    def _poll_vram(self) -> None:
        if torch.cuda.is_available():
            used = torch.cuda.memory_allocated() / 1024 ** 2
            self._vram_bar.update_usage(used)

    # ------------------------------------------------------------------
    # Config builders
    # ------------------------------------------------------------------

    def _build_engine_config(self) -> EngineConfig:
        s = self._settings
        return EngineConfig(
            device=s.get("device", "auto"),
            fp16=s.get("fp16", True),
            bf16=s.get("bf16", False),
            batch_size=s.get("batch_size", 8),
            beam_size=s.get("beam_size", 5),
            temperature=s.get("temperature", 0.0),
            best_of=s.get("best_of", 5),
            patience=s.get("patience", 1.0),
            no_speech_threshold=s.get("no_speech_threshold", 0.6),
            logprob_threshold=s.get("logprob_threshold", -1.0),
            compression_ratio_threshold=s.get("compression_ratio_threshold", 2.4),
            condition_on_previous_text=s.get("condition_on_previous_text", False),
            word_timestamps=s.get("word_timestamps", True),
            min_segment_duration=s.get("min_segment_duration", 0.5),
            max_segment_duration=s.get("max_segment_duration", 15.0),
            hallucination_silence_threshold=s.get("hallucination_silence_threshold", 2.0),
            chunk_duration_seconds=s.get("chunk_duration_seconds", 600),
            vad_enabled=s.get("vad_enabled", True),
        )

    def _build_preprocess_config(self) -> PreprocessConfig:
        return PreprocessConfig(
            noise_reduction=self._chk_noise.isChecked(),
            volume_normalization=self._chk_norm.isChecked(),
            silence_removal=self._chk_silence.isChecked(),
            vad_enabled=self._chk_vad.isChecked(),
            resample_16k=self._chk_resample.isChecked(),
        )

    def _build_default_settings(self) -> dict:
        dec  = self._cfg.get("decoding", {})
        ts   = self._cfg.get("timestamp", {})
        vad  = self._cfg.get("vad", {})
        cuda = self._cfg.get("cuda", {})
        pre  = self._cfg.get("preprocessing", {})
        return {
            "device":                        "auto" if cuda.get("auto_detect", True) else cuda.get("device", "auto"),
            "fp16":                          cuda.get("fp16", True),
            "bf16":                          cuda.get("bf16", False),
            "batch_size":                    cuda.get("batch_size", 8),
            "beam_size":                     dec.get("beam_size", 5),
            "temperature":                   dec.get("temperature", 0.0),
            "best_of":                       dec.get("best_of", 5),
            "patience":                      dec.get("patience", 1.0),
            "condition_on_previous_text":    dec.get("condition_on_previous_text", False),
            "no_speech_threshold":           dec.get("no_speech_threshold", 0.6),
            "logprob_threshold":             dec.get("logprob_threshold", -1.0),
            "compression_ratio_threshold":   dec.get("compression_ratio_threshold", 2.4),
            "hallucination_silence_threshold": dec.get("hallucination_silence_threshold", 2.0),
            "word_timestamps":               ts.get("word_timestamps", True),
            "min_segment_duration":          ts.get("min_segment_duration", 0.5),
            "max_segment_duration":          ts.get("max_segment_duration", 15.0),
            "merge_gap":                     ts.get("merge_threshold", 0.3),
            "vad_enabled":                   vad.get("threshold", 0.5) > 0,
            "vad_threshold":                 vad.get("threshold", 0.5),
            "vad_min_speech_ms":             vad.get("min_speech_duration", 250),
            "vad_min_silence_ms":            vad.get("min_silence_duration", 500),
            "chunk_duration_seconds":        pre.get("chunk_duration_seconds", 600),
        }

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(3000)
        self._save_config()
        event.accept()

    def _save_config(self) -> None:
        import yaml
        self._cfg.setdefault("model", {})["last_used"] = self._model_combo.currentText()
        self._cfg.setdefault("output", {})["directory"] = self._out_edit.text()
        try:
            with open("config/config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self._cfg, f, allow_unicode=True)
        except Exception as exc:
            logger.warning(f"Config save failed: {exc}")
