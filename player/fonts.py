"""Font helper to load and apply bundled Google Fonts (Kanit)."""
from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont

FR_PRIVATE = 0x10


def _get_fonts_dirs(bundle_dir: Path, app_dir: Path) -> list[Path]:
    candidates = [
        app_dir / "assets" / "fonts",
        bundle_dir / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    seen = set()
    valid = []
    for d in candidates:
        res = d.resolve()
        if res.is_dir() and res not in seen:
            seen.add(res)
            valid.append(res)
    return valid


def load_bundled_fonts(bundle_dir: Path, app_dir: Path) -> list[str]:
    """Load bundled .ttf files into process memory on Windows."""
    loaded_files: list[str] = []
    if sys.platform != "win32":
        return loaded_files

    for font_dir in _get_fonts_dirs(bundle_dir, app_dir):
        for ttf in font_dir.glob("*.ttf"):
            try:
                res = ctypes.windll.gdi32.AddFontResourceExW(str(ttf.resolve()), FR_PRIVATE, 0)
                if res > 0:
                    loaded_files.append(ttf.name)
            except Exception:
                pass
    return loaded_files


def get_preferred_font(root: tk.Tk | None = None) -> str:
    """Detect if Kanit is available, otherwise return clean system fallback."""
    try:
        available = tkfont.families(root) if root else ()
    except Exception:
        available = ()

    for candidate in ("Kanit", "Inter", "Segoe UI", "Leelawadee UI", "SF Pro Text", "Helvetica Neue", "Arial"):
        if candidate in available:
            return candidate

    return "TkDefaultFont"
