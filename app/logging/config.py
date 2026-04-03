import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.logging.formatter import JsonLinesFormatter

_HANDLER_LOCK = threading.Lock()


class StructuredJsonlHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            category = self._category_for_record(record)
            self._append_line(category, line)
            if record.levelno >= logging.ERROR and category != "errors":
                self._append_line("errors", line)
        except Exception:
            self.handleError(record)

    @staticmethod
    def _category_for_record(record: logging.LogRecord) -> str:
        if record.name.startswith("app."):
            return record.name.split(".", maxsplit=1)[1].replace(".", "-")
        return "app"

    @staticmethod
    def _append_line(category: str, line: str) -> None:
        root = Path(settings.log_dir)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_path = root / category / f"{day}.jsonl"
        with _HANDLER_LOCK:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")


def configure_logging(*, force: bool = False) -> None:
    app_logger = logging.getLogger("app")
    if getattr(app_logger, "_structured_logging_configured", False) and not force:
        return

    app_logger.handlers.clear()
    app_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    app_logger.propagate = False

    handler = StructuredJsonlHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonLinesFormatter())
    app_logger.addHandler(handler)

    app_logger._structured_logging_configured = True  # type: ignore[attr-defined]
