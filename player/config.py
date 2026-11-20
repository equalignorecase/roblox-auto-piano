"""Tiny JSON settings store (last file, preset, tempo...)."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".roblox-midi-player.json"

DEFAULTS = {
    "midi_path": "",
    "preset": "virtualpiano61",
    "tempo": "1.0",
    "transpose": "0",
    "octave": "0",
    "fold": True,
    "countdown": "3",
    "language": "th",
}


def load_settings() -> dict:
    settings = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            settings.update({key: data[key] for key in DEFAULTS if key in data})
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return settings


def save_settings(settings: dict) -> None:
    data = {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}
    try:
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
