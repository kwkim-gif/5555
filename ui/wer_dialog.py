"""WER / CER measurement dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class WERDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("WER / CER Measurement")
        self.resize(700, 500)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        ref_grp = QGroupBox("Reference Text")
        rg = QVBoxLayout(ref_grp)
        self._ref_edit = QTextEdit()
        rg.addWidget(self._ref_edit)
        row_r = QHBoxLayout()
        btn_load_ref = QPushButton("Load TXT")
        btn_load_ref.clicked.connect(lambda: self._load_text(self._ref_edit))
        row_r.addStretch()
        row_r.addWidget(btn_load_ref)
        rg.addLayout(row_r)
        root.addWidget(ref_grp)

        hyp_grp = QGroupBox("Hypothesis (Transcription Result)")
        hg = QVBoxLayout(hyp_grp)
        self._hyp_edit = QTextEdit()
        hg.addWidget(self._hyp_edit)
        row_h = QHBoxLayout()
        btn_load_hyp = QPushButton("Load TXT / SRT")
        btn_load_hyp.clicked.connect(self._load_hyp)
        row_h.addStretch()
        row_h.addWidget(btn_load_hyp)
        hg.addLayout(row_h)
        root.addWidget(hyp_grp)

        btn_calc = QPushButton("Calculate")
        btn_calc.clicked.connect(self._calculate)
        root.addWidget(btn_calc)

        result_grp = QGroupBox("Results")
        res = QHBoxLayout(result_grp)
        self._wer_label = QLabel("WER: -")
        self._cer_label = QLabel("CER: -")
        self._wer_label.setStyleSheet("font-size:16px; font-weight:bold;")
        self._cer_label.setStyleSheet("font-size:16px; font-weight:bold;")
        res.addWidget(self._wer_label)
        res.addWidget(self._cer_label)
        root.addWidget(result_grp)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        root.addWidget(close_btn)

    def _load_text(self, editor: QTextEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Text (*.txt *.srt)")
        if path:
            editor.setPlainText(Path(path).read_text(encoding="utf-8"))

    def _load_hyp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Hypothesis File", "", "Text/SRT (*.txt *.srt)")
        if not path:
            return
        content = Path(path).read_text(encoding="utf-8")
        if path.endswith(".srt"):
            content = self._strip_srt(content)
        self._hyp_edit.setPlainText(content)

    def _strip_srt(self, srt_text: str) -> str:
        lines = []
        for line in srt_text.splitlines():
            line = line.strip()
            if not line or line.isdigit() or "-->" in line:
                continue
            lines.append(line)
        return "\n".join(lines)

    def _calculate(self) -> None:
        ref = self._ref_edit.toPlainText().strip()
        hyp = self._hyp_edit.toPlainText().strip()
        if not ref or not hyp:
            return
        try:
            import jiwer
            wer = jiwer.wer(ref, hyp)
            cer = jiwer.cer(ref, hyp)
            self._wer_label.setText(f"WER: {wer*100:.2f}%")
            self._cer_label.setText(f"CER: {cer*100:.2f}%")
        except ImportError:
            self._wer_label.setText("jiwer package not installed")
