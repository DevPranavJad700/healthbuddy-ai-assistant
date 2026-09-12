"""
Centralized logging configuration for the application.
"""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Root logger config — force UTF-8 to avoid Windows cp1252 encoding errors
    handler = logging.StreamHandler(sys.stdout)
    handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

    import json

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                log_record["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    if settings.is_production:
        handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ"))
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

    logging.basicConfig(
        level=log_level,
        handlers=[handler],
    )

    # Suppress noisy third-party loggers
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger("healthbuddy")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
