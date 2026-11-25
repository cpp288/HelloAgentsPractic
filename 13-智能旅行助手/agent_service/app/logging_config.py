import logging
import sys
from contextvars import ContextVar
from pathlib import Path

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    """把 contextvar 里的 traceId 注入每条日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def setup_logging() -> None:
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(trace_id)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    trace_filter = TraceIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_dir / "agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    for handler in (console, file_handler):
        handler.addFilter(trace_filter)
        root.addHandler(handler)
