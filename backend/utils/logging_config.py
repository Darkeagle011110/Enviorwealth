"""
logging_config.py — Centralised logging configuration for EnviroWealth backend.

Sets up:
  - Coloured console output (INFO and above visible at a glance)
  - Rotating file logs (backend/logs/ directory)
  - Separate files for errors and LLM/agent activity
  - Structured JSON log lines for machine-readable output (can be shipped to Datadog, etc.)

Usage:
    from utils.logging_config import setup_logging
    setup_logging()   # call once at startup in main.py

Every module should use:
    import logging
    logger = logging.getLogger(__name__)
"""

import logging
import logging.handlers
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path


# ─── Log directory ────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ─── Colour codes for console ─────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
BLUE   = "\033[34m"
GREY   = "\033[90m"

LEVEL_COLOURS = {
    "DEBUG":    GREY,
    "INFO":     GREEN,
    "WARNING":  YELLOW,
    "ERROR":    RED,
    "CRITICAL": BOLD + RED,
}

# Module-name colour coding by area
MODULE_COLOURS = {
    "orchestrator": CYAN,
    "eligibility":  BLUE,
    "rag":          GREEN,
    "web_search":   YELLOW,
    "api":          GREEN,
    "engine":       CYAN,
    "llm":          BLUE,
    "session":      GREY,
    "utils":        GREY,
}


# ─── Custom formatters ────────────────────────────────────────────────────────

class ColouredConsoleFormatter(logging.Formatter):
    """
    Human-readable coloured log formatter for the console.

    Format:
        HH:MM:SS | LEVEL    | module.name | message
    """

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        level_colour = LEVEL_COLOURS.get(level, "")

        # Module colour
        module = record.name
        mod_colour = RESET
        for prefix, colour in MODULE_COLOURS.items():
            if prefix in module:
                mod_colour = colour
                break

        # Timestamp
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")

        # Format the message
        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        return (
            f"{GREY}{ts}{RESET} "
            f"{level_colour}{level:<8}{RESET} "
            f"{mod_colour}{module:<40}{RESET} "
            f"{msg}"
        )


class JSONFileFormatter(logging.Formatter):
    """
    Machine-readable JSON formatter for log files.
    Each line is a valid JSON object — easy to ingest into Datadog, ELK, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts":       datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":    record.levelname,
            "logger":   record.name,
            "msg":      record.getMessage(),
            "func":     f"{record.filename}:{record.lineno}",
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        return json.dumps(log_obj, ensure_ascii=False)


# ─── Timing helper ────────────────────────────────────────────────────────────

class TimedOperation:
    """
    Context manager for timing operations and logging them.

    Usage:
        with TimedOperation(logger, "RAG retrieval", {"query": user_query[:50]}):
            chunks = await retriever.search(query)
    """
    def __init__(self, logger: logging.Logger, name: str, extra: dict = None):
        self.logger = logger
        self.name = name
        self.extra = extra or {}
        self._start = None

    def __enter__(self):
        self._start = time.perf_counter()
        self.logger.debug(f"⏱  START  {self.name}", extra={"extra": self.extra})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = int((time.perf_counter() - self._start) * 1000)
        if exc_type:
            self.logger.error(
                f"⏱  FAIL   {self.name} ({elapsed_ms}ms) — {exc_val}",
                extra={"extra": {**self.extra, "elapsed_ms": elapsed_ms}},
                exc_info=True,
            )
        else:
            self.logger.info(
                f"⏱  DONE   {self.name} ({elapsed_ms}ms)",
                extra={"extra": {**self.extra, "elapsed_ms": elapsed_ms}},
            )
        return False  # do not suppress exceptions


# ─── Setup function ───────────────────────────────────────────────────────────

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure the root logger with:
      - Console handler: coloured, human-readable
      - Rolling file handler: all.log (JSON, 10 MB, 5 backups)
      - Rolling file handler: error.log (JSON, errors only, 5 MB, 3 backups)
      - Rolling file handler: agents.log (JSON, agent activity only, 10 MB, 5 backups)

    Call once in main.py startup.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)   # capture everything; handlers filter by level

    # Remove any existing handlers (prevents duplicate logs on hot reload)
    if root.handlers:
        root.handlers.clear()

    # ── 1. Console handler ─────────────────────────────────────────────────────
    # Windows cp1252 charmap crashes on emojis. Force sys.stdout to UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(ColouredConsoleFormatter())
    root.addHandler(console_handler)

    # ── 2. All-events log (JSON, rotating) ────────────────────────────────────
    all_log_path = LOG_DIR / "all.log"
    all_handler = logging.handlers.RotatingFileHandler(
        all_log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(JSONFileFormatter())
    root.addHandler(all_handler)

    # ── 3. Errors-only log (JSON, rotating) ───────────────────────────────────
    error_log_path = LOG_DIR / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFileFormatter())
    root.addHandler(error_handler)

    # ── 4. Agents-only log (JSON, rotating) ───────────────────────────────────
    # Captures only the orchestrator, agents, engine, and rag loggers
    agents_log_path = LOG_DIR / "agents.log"
    agents_handler = logging.handlers.RotatingFileHandler(
        agents_log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    agents_handler.setLevel(logging.DEBUG)
    agents_handler.setFormatter(JSONFileFormatter())
    agents_handler.addFilter(_AgentsFilter())
    root.addHandler(agents_handler)

    # ── Silence noisy third-party loggers ─────────────────────────────────────
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured — level={log_level} | "
        f"console=ON | "
        f"all.log={all_log_path} | "
        f"error.log={error_log_path} | "
        f"agents.log={agents_log_path}"
    )


class _AgentsFilter(logging.Filter):
    """Only passes records from agent-related modules."""
    _PREFIXES = (
        "orchestrator", "rag", "engine", "eligibility",
        "web_search", "session", "llm", "api.chat",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        return any(record.name.startswith(p) for p in self._PREFIXES)
