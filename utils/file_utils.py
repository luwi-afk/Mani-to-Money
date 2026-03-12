import os
from datetime import datetime


def base_dir() -> str:
    """
    Returns the project root directory (Money-Mani/).
    This works if this file is in Money-Mani/utils/file_utils.py
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_path(*parts) -> str:
    """Build an absolute path from the project root."""
    return os.path.join(base_dir(), *parts)


def ensure_dir(path: str) -> None:
    """Create directory if missing."""
    os.makedirs(path, exist_ok=True)


def resource_path(relative: str):
    """
    Returns absolute path if the resource exists, else None.
    Example: resource_path("assets/logo.png")
    """
    p = project_path(relative)
    return p if os.path.exists(p) else None

def pretty_scan_name(filename: str) -> str:
    """
    Convert scan_YYYYMMDD_HHMMSS.pdf
    -> YYYY-MM-DD  HH:MM:SS

    Falls back to filename if format is unexpected.
    """
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)

    parts = name.split("_")
    if len(parts) >= 3 and parts[0] == "scan":
        ymd = parts[1]
        hms = parts[2]
        try:
            dt = datetime.strptime(ymd + hms, "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d  %H:%M:%S")
        except Exception:
            pass

    return filename