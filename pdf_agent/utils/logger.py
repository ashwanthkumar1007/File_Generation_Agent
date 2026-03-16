"""Central logging configuration for the PDF agent.

Log format:  ``LEVEL | TIMESTAMP | MODULE | MESSAGE``

Usage in any module::

    from pdf_agent.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Document spec created")
"""

from __future__ import annotations

import logging
import sys


_LOG_FORMAT = "%(levelname)s | %(asctime)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root ``pdf_agent`` logger once.

    Safe to call multiple times — only the first invocation has effect.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root_logger = logging.getLogger("pdf_agent")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    root_logger.propagate = False

    _CONFIGURED = True


def get_logger(module_name: str) -> logging.Logger:
    """Return a logger for *module_name*, ensuring logging is initialised."""
    setup_logging()
    return logging.getLogger(module_name)
