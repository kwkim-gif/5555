"""Advanced settings dialog - decoding, VAD, CUDA, timestamp parameters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QTabWidget,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setMinimumWidth(500)
        self._config = dict(config)
        self._widgets: dict[str, QWidget] = {}
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_decoding(),     "Decoding")
        tabs.addTab(self._tab_hallucination(), "Hallucination")
        tabs.addTab(self._tab_timestamp(),    "Timestamp")
        tabs.addTab(self._tab_vad(),          "VAD")
        tabs.addTab(self._tab_cuda(),         "CUDA / Batch")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _tab_decoding(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._add_spin (form, "beam_size",  "Beam Size",  1, 20,  1)
        self._add_dspin(form, "temperature","Temperature",0.0, 1.0, 0.1)
        self._add_spin (form, "best_of",    "Best Of",    1, 20,  1)
        self._add_dspin(form, "patience",   "Patience",   0.0, 5.0, 0.1)
        self._add_check(form, "condition_on_previous_text", "Use Previous Context")
        return w

    def _tab_hallucination(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._add_dspin(form, "no_speech_threshold",          "No-speech Threshold",          0.0,  1.0, 0.05)
        self._add_dspin(form, "logprob_threshold",            "Log-prob Threshold",           -5.0, 0.0, 0.1)
        self._add_dspin(form, "compression_ratio_threshold",  "Compression Ratio Threshold",  1.0,  5.0, 0.1)
        self._add_dspin(form, "hallucination_silence_threshold", "Silence Hallucination (s)", 0.0, 10.0, 0.5)
        return w

    def _tab_timestamp(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._add_check(form, "word_timestamps",      "Word-level Timestamps")
        self._add_dspin(form, "min_segment_duration", "Min Segment Duration (s)", 0.1,  5.0, 0.1)
        self._add_dspin(form, "max_segment_duration", "Max Segment Duration (s)", 1.0, 60.0, 1.0)
        self._add_dspin(form, "merge_gap",            "Merge Gap (s)",            0.0,  3.0, 0.1)
        return w

    def _tab_vad(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._add_check(form, "vad_enabled",       "Enable VAD")
        self._add_dspin(form, "vad_threshold",     "VAD Threshold",          0.0, 1.0,  0.05)
        self._add_spin (form, "vad_min_speech_ms", "Min Speech Duration (ms)", 0, 2000, 50)
        self._add_spin (form, "vad_min_silence_ms","Min Silence Duration (ms)",0, 5000, 100)
        return w

    def _tab_cuda(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        device_combo = QComboBox()
        device_combo.addItems(["auto", "cuda", "cpu"])
        self._widgets["device"] = device_combo
        form.addRow("Device", device_combo)
        self._add_check(form, "fp16",       "FP16 (Half Precision)")
        self._add_check(form, "bf16",       "BF16 (BFloat16)")
        self._add_spin (form, "batch_size", "Batch Size",       1,   64,  1)
        self._add_spin (form, "chunk_duration_seconds", "Chunk Duration (s)", 30, 3600, 30)
        return w

    # ------------------------------------------------------------------

    def _add_spin(self, form, key, label, mn, mx, step) -> None:
        w = QSpinBox(); w.setRange(mn, mx); w.setSingleStep(step)
        self._widgets[key] = w; form.addRow(label, w)

    def _add_dspin(self, form, key, label, mn, mx, step) -> None:
        w = QDoubleSpinBox(); w.setRange(mn, mx); w.setSingleStep(step); w.setDecimals(3)
        self._widgets[key] = w; form.addRow(label, w)

    def _add_check(self, form, key, label) -> None:
        w = QCheckBox()
        self._widgets[key] = w; form.addRow(label, w)

    _DEFAULTS = {
        "beam_size": 5, "temperature": 0.0, "best_of": 5, "patience": 1.0,
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.6, "logprob_threshold": -1.0,
        "compression_ratio_threshold": 2.4, "hallucination_silence_threshold": 2.0,
        "word_timestamps": True, "min_segment_duration": 0.5,
        "max_segment_duration": 15.0, "merge_gap": 0.3,
        "vad_enabled": True, "vad_threshold": 0.5,
        "vad_min_speech_ms": 250, "vad_min_silence_ms": 500,
        "device": "auto", "fp16": True, "bf16": False,
        "batch_size": 8, "chunk_duration_seconds": 600,
    }

    def _load_values(self) -> None:
        for key, widget in self._widgets.items():
            val = self._config.get(key, self._DEFAULTS.get(key))
            if val is None:
                continue
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(val))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(val)
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)

    def _on_accept(self) -> None:
        for key, widget in self._widgets.items():
            if isinstance(widget, QCheckBox):
                self._config[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                self._config[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                self._config[key] = widget.value()
            elif isinstance(widget, QComboBox):
                self._config[key] = widget.currentText()
        self.accept()

    def get_config(self) -> dict:
        return self._config
