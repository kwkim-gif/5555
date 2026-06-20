"""AI STT Studio - entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from loguru import logger


def _configure_logging(log_dir: str = "logs", error_dir: str = "error_logs") -> None:
    Path(log_dir).mkdir(exist_ok=True)
    Path(error_dir).mkdir(exist_ok=True)

    from datetime import date

    log_file = Path(log_dir) / f"{date.today()}.log"

    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True, format="{time:HH:mm:ss} | {level} | {message}")
    logger.add(
        str(log_file),
        level="DEBUG",
        rotation="50 MB",
        retention="7 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{line} | {message}",
    )
    logger.add(
        str(Path(error_dir) / "error_{time:YYYYMMDD_HHmmss}.log"),
        level="ERROR",
        rotation="1 MB",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )


def _load_config(config_path: str = "config/config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config not found at {config_path}, using defaults")
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    _configure_logging()
    logger.info("=" * 60)
    logger.info("AI STT Studio starting")

    config = _load_config()

    import os
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("AI STT Studio")
    app.setOrganizationName("STTStudio")

    try:
        import torch

        if torch.cuda.is_available():
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
            props = torch.cuda.get_device_properties(0)
            logger.info(f"VRAM: {props.total_memory / 1024**3:.1f} GB")
        else:
            logger.info("CUDA not available - running on CPU")
    except ImportError:
        logger.warning("PyTorch not installed")

    from ui.main_window import MainWindow

    window = MainWindow(app_config=config)
    window.show()

    logger.info("UI launched")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
