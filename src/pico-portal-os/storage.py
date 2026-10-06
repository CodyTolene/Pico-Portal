# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import json
import os
import time

DEFAULT_CONFIG = {
    "clock": {
        "daylight_saving": True,
        "timezone_name": "Central",
        "utc_offset_hours": -6,
    },
    "display": {
        "brightness": 0.9,
        "font_px": 8,
        "scanlines": True,
        "theme": "green",
        "type": "auto",
    },
    "led": {"brightness": 0.05, "status": "heartbeat"},
    "portal": {
        "password": "",
        "ssid": "WiFi Setup",
        "success_template": "success.html",
        "template": "",
    },
    "regional": {
        "hour_format": 24,
        "temperature_unit": "C",
        "unit_system": "imperial",
    },
    "screensaver": {"name": "MATRIX", "timeout": 60},
    "weather": {
        "latitude": None,
        "location": "",
        "longitude": None,
        "zip_code": "",
    },
    "wifi": {"password": "", "ssid": ""},
}


def _weekday(year, month, day):
    offsets = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    return (
        year + year // 4 - year // 100 + year // 400 + offsets[month - 1] + day
    ) % 7


def _us_dst(date_tuple):
    year, month, day = date_tuple[0], date_tuple[1], date_tuple[2]
    if month < 3 or month > 11:
        return False
    if 3 < month < 11:
        return True
    first_sunday = 1 + (7 - _weekday(year, month, 1)) % 7
    return day >= first_sunday + 7 if month == 3 else day < first_sunday


def local_time(config):
    """Return configured wall time without loading the clock-settings UI."""
    utc = time.localtime()
    offset = int(config.get("utc_offset_hours", -6))
    if config.get("daylight_saving", True) and _us_dst(utc):
        offset += 1
    return time.localtime(time.time() + offset * 3600), offset


def _read(path):
    try:
        with open(path, "r") as settings_file:
            data = json.load(settings_file)
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        return data
    except (OSError, TypeError, ValueError):
        return None


def _level(value, default):
    """Return a safe 0..1 brightness value from user configuration."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(1.0, value))


def load_config(path="/config.json"):
    """Load current grouped settings and fill missing values with defaults."""
    loaded = _read(path) or {}
    data = {}
    for key, default in DEFAULT_CONFIG.items():
        merged = dict(default)
        section = loaded.get(key)
        if isinstance(section, dict):
            merged.update(section)
        data[key] = merged
    display = data["display"]
    led = data["led"]
    regional = data["regional"]
    screensaver = data["screensaver"]
    display["brightness"] = _level(display["brightness"], 0.9)
    led["brightness"] = _level(led["brightness"], 0.05)
    if 0 < led["brightness"] < 0.05:
        led["brightness"] = 0.05
    if display["theme"] not in (
        "green",
        "amber",
        "cyan",
        "blue",
        "purple",
        "red",
        "white",
    ):
        display["theme"] = "green"
    display["scanlines"] = bool(display["scanlines"])
    if led["status"] not in ("heartbeat", "on", "off"):
        led["status"] = "heartbeat"
    try:
        screensaver["timeout"] = max(0, int(screensaver["timeout"]))
    except (TypeError, ValueError):
        screensaver["timeout"] = 60
    try:
        display["font_px"] = max(8, min(16, int(display["font_px"])))
    except (TypeError, ValueError):
        display["font_px"] = 8
    try:
        regional["hour_format"] = int(regional["hour_format"])
    except (TypeError, ValueError):
        regional["hour_format"] = 24
    if regional["hour_format"] not in (12, 24):
        regional["hour_format"] = 24
    regional["temperature_unit"] = str(regional["temperature_unit"]).upper()
    if regional["temperature_unit"] not in ("C", "F"):
        regional["temperature_unit"] = "C"
    regional["unit_system"] = str(regional["unit_system"]).lower()
    if regional["unit_system"] not in ("imperial", "metric"):
        regional["unit_system"] = "imperial"
    return data


def _write_json(value, output, depth=0):
    """Write readable JSON with sorted keys using MicroPython's JSON API."""
    if not isinstance(value, (dict, list)):
        json.dump(value, output)
        return
    is_object = isinstance(value, dict)
    output.write("{" if is_object else "[")
    if value:
        output.write("\n")
        keys = sorted(value) if is_object else range(len(value))
        for index, key in enumerate(keys):
            output.write("    " * (depth + 1))
            if is_object:
                json.dump(key, output)
                output.write(": ")
            _write_json(value[key], output, depth + 1)
            output.write(",\n" if index + 1 < len(value) else "\n")
        output.write("    " * depth)
    output.write("}" if is_object else "]")


def save_config(data, path="/config.json"):
    """Persist all settings with each object's properties sorted A-Z."""
    with open(path, "w") as settings_file:
        _write_json(data, settings_file)
        settings_file.write("\n")
    sync = getattr(os, "sync", None)
    if sync is not None:
        sync()
