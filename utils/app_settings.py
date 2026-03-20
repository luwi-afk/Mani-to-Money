import json
import os
from utils.file_utils import project_path

SETTINGS_PATH = project_path("settings.json")

DEFAULTS = {
    "max_price_per_kg": 250.0,
    "history_auto_purge": True,
    "history_keep_days": 30,
    "settings_passcode": "0000",
    "camera": {
        "fps": 30,                 # 15, 30, 60
        "hflip": False,            # Horizontal flip
        "vflip": False             # Vertical flip
    }
}


def load_settings() -> dict:
    """Load settings from JSON file, return defaults if not exists"""
    if not os.path.exists(SETTINGS_PATH):
        return DEFAULTS.copy()

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = DEFAULTS.copy()
        out.update(data if isinstance(data, dict) else {})
        return out
    except Exception:
        return DEFAULTS.copy()


def save_settings(data: dict) -> None:
    """Save settings to JSON file"""
    out = DEFAULTS.copy()
    out.update(data if isinstance(data, dict) else {})

    # Ensure directory exists
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


# ===== PRICE SETTINGS =====
def get_max_price_per_kg() -> float:
    """Get maximum price per kg setting"""
    s = load_settings()
    try:
        return float(s.get("max_price_per_kg", DEFAULTS["max_price_per_kg"]))
    except Exception:
        return float(DEFAULTS["max_price_per_kg"])


def set_max_price_per_kg(value: float) -> None:
    """Set maximum price per kg"""
    s = load_settings()
    s["max_price_per_kg"] = float(value)
    save_settings(s)


# ===== HISTORY SETTINGS =====
def get_history_auto_purge() -> bool:
    """Get auto-purge setting"""
    s = load_settings()
    return bool(s.get("history_auto_purge", DEFAULTS["history_auto_purge"]))


def set_history_auto_purge(value: bool) -> None:
    """Set auto-purge setting"""
    s = load_settings()
    s["history_auto_purge"] = bool(value)
    save_settings(s)


def get_history_keep_days() -> int:
    """Get number of days to keep history"""
    s = load_settings()
    try:
        v = int(s.get("history_keep_days", DEFAULTS["history_keep_days"]))
        return max(1, v)
    except Exception:
        return int(DEFAULTS["history_keep_days"])


def set_history_keep_days(days: int) -> None:
    """Set number of days to keep history"""
    s = load_settings()
    s["history_keep_days"] = max(1, int(days))
    save_settings(s)


# ===== PASSCODE SETTINGS =====
def get_settings_passcode() -> str:
    """Get settings passcode as string (preserves leading zeros)"""
    s = load_settings()
    value = s.get("settings_passcode", DEFAULTS["settings_passcode"])

    if isinstance(value, (int, float)):
        return f"{int(value):04d}"
    return str(value).strip()


def set_settings_passcode(passcode: str) -> None:
    """Set settings passcode (stored as string)"""
    s = load_settings()
    clean = str(passcode).strip()
    if clean.isdigit():
        s["settings_passcode"] = clean
    else:
        s["settings_passcode"] = DEFAULTS["settings_passcode"]
    save_settings(s)


def validate_passcode(entered: str) -> bool:
    """Validate entered passcode against stored one"""
    stored = get_settings_passcode()
    return str(entered).strip() == stored


# ===== CAMERA SETTINGS =====
def get_camera_settings() -> dict:
    """Get all camera settings"""
    s = load_settings()
    if "camera" not in s:
        s["camera"] = DEFAULTS["camera"].copy()
        save_settings(s)
    return s["camera"]


def update_camera_settings(settings: dict) -> None:
    """Update camera settings"""
    s = load_settings()
    s["camera"] = settings
    save_settings(s)

def get_camera_fps() -> int:
    """Get camera FPS"""
    return get_camera_settings().get("fps", 30)


def get_camera_hflip() -> bool:
    """Get horizontal flip setting"""
    return get_camera_settings().get("hflip", False)


def get_camera_vflip() -> bool:
    """Get vertical flip setting"""
    return get_camera_settings().get("vflip", False)


# ===== RESET FUNCTION =====
def reset_to_defaults() -> None:
    """Reset all settings to default values"""
    save_settings(DEFAULTS.copy())


def get_all_settings() -> dict:
    """Get all settings as a dictionary"""
    return load_settings()


def update_settings(updates: dict) -> None:
    """Update multiple settings at once"""
    s = load_settings()
    s.update(updates)
    save_settings(s)