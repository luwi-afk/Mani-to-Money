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

def pretty_scan_name(filename):
    """
    Convert filename to a human-readable name.
    New format: Scan_mm-dd-yyyy-0000.pdf -> "Scan mm-dd-yyyy-0000"
    Old format: scan_20250328_123456.pdf -> "Scan 03-28-2025 12:34:56"
    Otherwise, return filename without extension.
    """
    name, _ = os.path.splitext(filename)

    if name.startswith("Scan_"):
        # New ID-based name
        return name.replace('_', ' ')
    elif name.startswith("scan_"):
        # Old timestamp-based name: scan_YYYYMMDD_HHMMSS
        try:
            parts = name.split('_')
            if len(parts) >= 3:
                date_part = parts[1]  # YYYYMMDD
                time_part = parts[2]  # HHMMSS
                dt = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
                return f"Scan {dt.strftime('%m-%d-%Y %H:%M:%S')}"
        except:
            pass
        return name
    else:
        return name