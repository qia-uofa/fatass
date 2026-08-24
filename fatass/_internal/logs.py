import logging

from .paths import LOG_PATH as _LOG_PATH

_LOGGER_NAME = "fatass"

_handler: logging.Handler | None = None
"""Tracks specifically the FileHandler *this module* attached, rather than
asking `logger.handlers` "is anything attached at all" — a test runner (or
any other code sharing this process) can attach its own foreign handler to
the same named logger, and a bare "if not logger.handlers" would mistake
that for "already configured" and skip creating our FileHandler entirely,
silently dropping every write to ./log."""


def get_logger() -> logging.Logger:
    """The shared logger every CLI command dispatch and every
    fatass.free() call writes through — a FileHandler appending to ./log
    at the repo root. Configured once per process (idempotent: repeat
    calls, including across commands in one `shell` REPL session, reuse
    the same handler rather than reopening the file)."""
    global _handler
    logger = logging.getLogger(_LOGGER_NAME)
    if _handler is None or _handler not in logger.handlers:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        _handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
