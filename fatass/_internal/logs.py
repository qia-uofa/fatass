import logging

from .paths import LOG_PATH as _LOG_PATH

_LOGGER_NAME = "fatass"


def get_logger() -> logging.Logger:
    """The shared logger every CLI command dispatch and every
    fatass.free() call writes through — a FileHandler appending to ./log
    at the repo root. Configured once per process (idempotent: repeat
    calls, including across commands in one `shell` REPL session, reuse
    the same handler rather than reopening the file)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
