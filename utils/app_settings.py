# utils/app_settings.py

import json
import os
from utils.file_utils import project_path

SETTINGS_PATH = project_path("settings.json")

DEFAULTS = {
    "max_price_per_kg": 250.0,
    "history_auto_purge": True,
    "history_keep_days": 30
}

def load_settings() -> dict:
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
    out = DEFAULTS.copy()
    out.update(data if isinstance(data, dict) else {})
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

def get_max_price_per_kg() -> float:
    s = load_settings()
    try:
        return float(s.get("max_price_per_kg", DEFAULTS["max_price_per_kg"]))
    except Exception:
        return float(DEFAULTS["max_price_per_kg"])

def set_max_price_per_kg(value: float) -> None:
    s = load_settings()
    s["max_price_per_kg"] = float(value)
    save_settings(s)

def get_history_auto_purge() -> bool:
    s = load_settings()
    return bool(s.get("history_auto_purge", DEFAULTS["history_auto_purge"]))

def set_history_auto_purge(value: bool) -> None:
    s = load_settings()
    s["history_auto_purge"] = bool(value)
    save_settings(s)

def get_history_keep_days() -> int:
    s = load_settings()
    try:
        v = int(s.get("history_keep_days", DEFAULTS["history_keep_days"]))
        return max(1, v)
    except Exception:
        return int(DEFAULTS["history_keep_days"])

def set_history_keep_days(days: int) -> None:
    s = load_settings()
    s["history_keep_days"] = max(1, int(days))
    save_settings(s)

