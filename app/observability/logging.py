"""结构化日志 — JSON formatter + trace_id 注入"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from observability.middleware import get_trace_id


class TraceIdFilter(logging.Filter):
    """自动将 ContextVar 中的 trace_id 注入日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """JSON 格式日志输出"""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_format: str = "text") -> logging.Logger:
    """初始化根日志配置

    Args:
        log_format: "text"（默认多行格式）或 "json"（生产用）

    Returns:
        根 logger
    """
    root = logging.getLogger()

    # 清空已有 handler（避免 basicConfig 叠加）
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(trace_id)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.addFilter(TraceIdFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # 降低噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return root
