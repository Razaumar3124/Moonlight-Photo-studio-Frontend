import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Pattern to mask sensitive connection URIs like mongodb://user:pass@host
_URI_CREDENTIAL_PATTERN = re.compile(r"://([^:]+):([^@]+)@")


def sanitize_sensitive_data(text: str) -> str:
    """Mask credentials in strings (such as database URLs or tokens)."""
    return _URI_CREDENTIAL_PATTERN.sub(r"://***:***@", text)


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_sensitive_data(record.getMessage()),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if attached
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Colorized human-readable log formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        sanitized_msg = sanitize_sensitive_data(record.getMessage())
        base = f"[{timestamp}] [{record.levelname:<8}] [{record.name}] {sanitized_msg}"
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def setup_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """Configure the root logger with the designated formatter and level."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to prevent duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Set external libraries to warning to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
