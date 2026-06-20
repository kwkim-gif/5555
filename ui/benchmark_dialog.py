"""Benchmark dialog — run all models against a reference audio and show results."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from benchmark.benchmark_runner import BenchmarkResult, BenchmarkRunner
from engines import ENGINE_REGISTRY


class _BenchmarkThread(QThread):
    result_ready = Signal(object)  # BenchmarkResult
    log = Signal(str)
    finished_all = Signal()

    def __init__(self, audio_path: str, reference_text: str, engine_config, preprocess_config, models: list[str]):
        super().__init__()
        self.audio_path = audio_path
        self.reference_text = reference_text
        self.engine_config = engine_config
        self.preprocess_config = preprocess_config
        self.models = models

    def run(self) -> None:
        runner = BenchmarkRunner(self.engine_config, self.preprocess_config)
        for model in self.models:
            self.log.emit(f"▶ {model} 벤치마크 시작...")
            try:
                res = runner.run(
                    model_name=model,
                    audio_path=self.audio_path,
                    reference_text=self.reference_text or None,
                    progress_callback=None,
                )
                self.result_ready.emit(res)
                self.log.emit(f"✅ {model} RTF={res.rtf:.3f}")
            except Exception as exc:
                self.log.emit(f"❌ {model} 실패: {exc}")
        self.finished_all.emit()


class BenchmarkDialog(QDialog):
    def __init__(self, engine_config, preprocess_config, parent=None) -> None:
        super().__init__(parent)
        self.engine_config = engine_config
        self.preprocess_config = preprocess_config
        self.setWindowTitle("모델 벤치마크")
        self.resize(800, 600)
        self._thread: _BenchmarkThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # File selection
        file_grp = QGroupBox("벤치마크 설정")
        fl = QVBoxLayout(file_grp)

        row1 = QHBoxLayout()
        self._audio_edit = QLineEdit()
        self._audio_edit.setPlaceholderText("테스트 음성 파일 경로...")
        btn_audio = QPushButton("선택")
        btn_audio.clicked.connect(self._pick_audio)
        row1.addWidget(QLabel("음성:"))
        row1.addWidget(self._audio_edit)
        row1.addWidget(btn_audio)

        row2 = QHBoxLayout()
        self._ref_edit = QLineEdit()
        self._ref_edit.setPlaceholderText("참조 텍스트 (WER/CER 측정용, 선택사항)...")
        btn_ref = QPushButton("파일")
        btn_ref.clicked.connect(self._pick_ref)
        row2.addWidget(QLabel("참조:"))
        row2.addWidget(self._ref_edit)
        row2.addWidget(btn_ref)

        fl.addLayout(row1)
        fl.addLayout(row2)
        root.addWidget(file_grp)

        # Controls
        ctrl = QHBoxLayout()
        self._run_btn = QPushButton("▶ 벤치마크 실행")
        self._run_btn.clicked.connect(self._run)
        ctrl.addWidget(self._run_btn)
        self._progress = QProgressBar()
        self._progress.setRange(0, len(ENGINE_REGISTRY))
        ctrl.addWidget(self._progress)
        root.addLayout(ctrl)

        # Results table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["모델", "음성길이(s)", "처리시간(s)", "RTF", "WER", "CER", "VRAM(MB)"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._table)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        root.addWidget(self._log)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        root.addWidget(close_btn)

    def _pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "음성 파일 선택", "",
            "Audio/Video (*.wav *.mp3 *.m4a *.flac *.ogg *.mp4 *.mkv *.avi *.mov *.ts)"
        )
        if path:
            self._audio_edit.setText(path)

    def _pick_ref(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "참조 텍스트 선택", "", "Text (*.txt)")
        if path:
            self._ref_edit.setText(Path(path).read_text(encoding="utf-8"))

    def _run(self) -> None:
        audio = self._audio_edit.text().strip()
        if not audio or not Path(audio).exists():
            QMessageBox.warning(self, "오류", "유효한 음성 파일을 선택하세요.")
            return

        self._table.setRowCount(0)
        self._progress.setValue(0)
        self._run_btn.setEnabled(False)
        ref = self._ref_edit.text().strip()

        self._thread = _BenchmarkThread(
            audio_path=audio,
            reference_text=ref,
            engine_config=self.engine_config,
            preprocess_config=self.preprocess_config,
            models=list(ENGINE_REGISTRY.keys()),
        )
        self._thread.result_ready.connect(self._add_result)
        self._thread.log.connect(lambda m: self._log.append(m))
        self._thread.finished_all.connect(self._on_done)
        self._thread.start()

    def _add_result(self, res: BenchmarkResult) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._table.setItem(r, 0, QTableWidgetItem(res.model_name))
        self._table.setItem(r, 1, QTableWidgetItem(f"{res.audio_duration:.1f}"))
        self._table.setItem(r, 2, QTableWidgetItem(f"{res.processing_time:.1f}"))
        self._table.setItem(r, 3, QTableWidgetItem(f"{res.rtf:.3f}"))
        self._table.setItem(r, 4, QTableWidgetItem(f"{res.wer*100:.1f}%" if res.wer is not None else "N/A"))
        self._table.setItem(r, 5, QTableWidgetItem(f"{res.cer*100:.1f}%" if res.cer is not None else "N/A"))
        self._table.setItem(r, 6, QTableWidgetItem(f"{res.vram_peak_mb:.0f}"))
        self._progress.setValue(r + 1)

    def _on_done(self) -> None:
        self._run_btn.setEnabled(True)
        self._log.append("🏁 벤치마크 완료")
