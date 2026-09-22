import json
import logging
import re
from datetime import datetime, timezone


_SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(password|passwd|secret|token|api[_ -]?key|authorization)\b"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@[^\s]+"),
]


def redact_log_text(value):
    text = str(value or "")
    text = _SECRET_PATTERNS[0].sub(r"\1\2[REDACTED]", text)
    text = _SECRET_PATTERNS[1].sub(r"\1[REDACTED]", text)
    return text


class SafeJsonFormatter(logging.Formatter):
    """Structured log formatter with a deliberately small, bounded field set."""

    safe_fields = (
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "error_type",
        "task",
        "component",
        "outcome",
    )

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_text(record.getMessage()),
        }
        for field in self.safe_fields:
            value = getattr(record, field, None)
            if value not in (None, ""):
                payload[field] = redact_log_text(value)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
