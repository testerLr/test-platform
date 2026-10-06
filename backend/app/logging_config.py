import logging.config
from pathlib import Path

from app.config import settings

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "app.log"

_LOG_LEVEL = settings.log_level.upper()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stdout"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(LOG_FILE),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    "root": {"level": _LOG_LEVEL, "handlers": ["stdout", "file"]},
    "loggers": {
        "uvicorn": {"level": _LOG_LEVEL, "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.error": {"level": _LOG_LEVEL, "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.access": {"level": _LOG_LEVEL, "handlers": ["stdout", "file"], "propagate": False},
        "app": {"level": _LOG_LEVEL, "handlers": ["stdout", "file"], "propagate": False},
    },
}


def configure_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)