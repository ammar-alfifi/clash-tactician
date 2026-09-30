"""Logging setup and secret redaction."""

from __future__ import annotations

import logging
import re

_SECRET_PATTERN = re.compile(
    r"(?i)((?:token|key|secret|password|authorization)\s*[=:]\s*)([^\s,;'\"]+)"
)


class _RedactingFilter(logging.Filter):
    """Never write API tokens or keys to the logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        if _SECRET_PATTERN.search(message):
            record.msg = _SECRET_PATTERN.sub(r"\1<redacted>", message)
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(_RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
    # aiogram can be chatty at INFO for every update; keep it at WARNING.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
