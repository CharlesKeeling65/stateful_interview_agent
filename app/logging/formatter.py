import json
import logging

from app.core.config import settings


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "event_payload", None)
        if payload is None:
            payload = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "event": "log.message",
                "message": record.getMessage(),
            }

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=settings.log_pretty_json,
            separators=(",", ":") if not settings.log_pretty_json else None,
        )
