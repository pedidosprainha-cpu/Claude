"""Logging estruturado (JSON em arquivo rotativo + console legível)."""
from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone

from .config import LOG_DIR, ensure_dirs


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
             "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        for k in ("event", "analysis_id", "symbol"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        return json.dumps(d, ensure_ascii=False)


_done = False


def setup_logging(level: int = logging.INFO) -> None:
    global _done
    if _done:
        return
    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(level)
    fh = logging.handlers.RotatingFileHandler(LOG_DIR / "fxintel.jsonl", maxBytes=5_000_000, backupCount=5,
                                              encoding="utf-8")
    fh.setFormatter(JsonFormatter())
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)
    root.addHandler(ch)
    for noisy in ("httpx", "httpcore", "urllib3", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _done = True
