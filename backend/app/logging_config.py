import logging.config
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "app.log"

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
    "root": {"level": "INFO", "handlers": ["stdout", "file"]},
    "loggers": {
        "uvicorn": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.error": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "app": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
    },
}


def configure_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
