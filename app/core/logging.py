from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_SECRET_RE = re.compile(
    r"(token|secret|password|authorization|api[_-]?key|bearer)",
    re.IGNORECASE,
)


def _redact(_: Any, __: Any, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if _SECRET_RE.search(str(key)) or isinstance(value, str) and _SECRET_RE.search(value) and len(value) > 12:
            event_dict[key] = "[redacted]"
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
