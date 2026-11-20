from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from player import fonts


class FontTests(unittest.TestCase):
    def test_get_fonts_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            f_dir = base / "assets" / "fonts"
            f_dir.mkdir(parents=True)
            dirs = fonts._get_fonts_dirs(base, base)
            self.assertIn(f_dir.resolve(), dirs)

    def test_get_preferred_font_fallback(self):
        tcl = tk.Tcl()
        # Non-Tk root or mocked should fallback to TkDefaultFont or safe system font
        preferred = fonts.get_preferred_font(None)
        self.assertIn(preferred, ("Kanit", "Inter", "Segoe UI", "Leelawadee UI", "SF Pro Text", "Helvetica Neue", "Arial", "TkDefaultFont"))

    def test_load_bundled_fonts(self):
        # Uses existing assets/fonts directory in repo
        app_dir = Path(__file__).resolve().parent.parent
        loaded = fonts.load_bundled_fonts(app_dir, app_dir)
        # On Windows it loads the TTF files
        import sys
        if sys.platform == "win32":
            self.assertTrue(any("Kanit" in name for name in loaded))


if __name__ == "__main__":
    unittest.main()
