"""File-system utility helpers."""

from __future__ import annotations

from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create a directory (and parents) if it doesn't already exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, extension: str = ".pdf") -> str:
    """Sanitise a string for use as a filename.

    Replaces unsafe characters with underscores and appends *extension*.
    """
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    if not safe.endswith(extension):
        safe += extension
    return safe
