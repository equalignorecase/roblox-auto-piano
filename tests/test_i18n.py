from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
import unittest

from player import config, i18n
from player.gui import App


class I18nTests(unittest.TestCase):
    def test_translation_fallback(self):
        self.assertEqual(i18n.tr("title", "th"), "Roblox Piano")
        self.assertEqual(i18n.tr("title", "en"), "Roblox Piano")
        self.assertEqual(i18n.tr("topmost", "en"), "Always on top")
        self.assertEqual(i18n.tr("topmost", "th"), "อยู่เหนือหน้าต่างอื่น")
        # Nonexistent key returns key name
        self.assertEqual(i18n.tr("nonexistent_xyz", "en"), "nonexistent_xyz")

    def test_preset_label_and_key_mapping(self):
        vp61_th = i18n.get_preset_label("virtualpiano61", "th")
        vp61_en = i18n.get_preset_label("virtualpiano61", "en")
        self.assertEqual(vp61_th, "Virtual Piano 61 คีย์ (C2-C7)")
        self.assertEqual(vp61_en, "Virtual Piano 61 keys (C2-C7)")

        self.assertEqual(i18n.get_preset_key(vp61_th), "virtualpiano61")
        self.assertEqual(i18n.get_preset_key(vp61_en), "virtualpiano61")

        custom_th = i18n.get_preset_label("custom", "th")
        custom_en = i18n.get_preset_label("custom", "en")
        self.assertEqual(i18n.get_preset_key(custom_th), "custom")
        self.assertEqual(i18n.get_preset_key(custom_en), "custom")

    def test_config_save_and_load_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / ".roblox-midi-player.json"
            orig_path = config.CONFIG_PATH
            config.CONFIG_PATH = cfg_file
            try:
                # Default is "th"
                loaded = config.load_settings()
                self.assertEqual(loaded["language"], "th")

                # Save "en"
                loaded["language"] = "en"
                config.save_settings(loaded)

                # Re-load
                reloaded = config.load_settings()
                self.assertEqual(reloaded["language"], "en")
            finally:
                config.CONFIG_PATH = orig_path

    def test_gui_language_switching(self):
        tcl = tk.Tcl()
        app = App.__new__(App)
        app.lang = "th"
        app.lang_var = tk.StringVar(tcl, value="ไทย")
        app.path_var = tk.StringVar(tcl, value="")
        app.song_var = tk.StringVar(tcl, value="ยังไม่ได้เลือกเพลง")
        app.status_var = tk.StringVar(tcl, value="พร้อม")
        app.musescore_status_var = tk.StringVar(tcl, value="")
        app.preset_var = tk.StringVar(tcl, value="Virtual Piano 61 คีย์ (C2-C7)")
        app.player = None
        app._downloading = False

        # Mock widgets
        class DummyWidget:
            def __init__(self):
                self.config = {}

            def configure(self, **kwargs):
                self.config.update(kwargs)

            def winfo_manager(self):
                return ""

        app.header_topmost_label = DummyWidget()
        app.song_label = DummyWidget()
        app.browse_button = DummyWidget()
        app.sheet_button = DummyWidget()
        app.stop_button = DummyWidget()
        app.start_button = DummyWidget()
        app.download_button = DummyWidget()
        app.pause_button = DummyWidget()
        app.preset_box = DummyWidget()
        app.musescore_url_label = DummyWidget()
        app.browser_check = DummyWidget()
        app.lang_label = DummyWidget()
        app.midi_path_label = DummyWidget()
        app.preset_label = DummyWidget()
        app.tempo_label = DummyWidget()
        app.countdown_label = DummyWidget()
        app.transpose_label = DummyWidget()
        app.octave_label = DummyWidget()
        app.fold_check = DummyWidget()
        app.active_hint_label = DummyWidget()

        download_panel = DummyWidget()
        download_btn = DummyWidget()
        settings_panel = DummyWidget()
        settings_btn = DummyWidget()
        app._panels = {
            "download": (download_panel, download_btn, "MuseScore"),
            "settings": (settings_panel, settings_btn, "ตั้งค่าการเล่น"),
        }
        app._fit_window = lambda: None

        # Switch to English
        app.lang_var.set("English")
        app._on_language_change()

        self.assertEqual(app.lang, "en")
        self.assertEqual(app.song_var.get(), "No song selected")
        self.assertEqual(app.status_var.get(), "Ready")
        self.assertEqual(app.preset_var.get(), "Virtual Piano 61 keys (C2-C7)")
        self.assertEqual(app.header_topmost_label.config["text"], "Always on top")
        self.assertEqual(app.song_label.config["text"], "Selected Song")
        self.assertEqual(app.browse_button.config["text"], "Browse...")
        self.assertEqual(app.sheet_button.config["text"], "Export Sheet")
        self.assertEqual(app.start_button.config["text"], "Play (F8)")
        self.assertEqual(app.stop_button.config["text"], "Stop (Esc)")
        self.assertEqual(app.lang_label.config["text"], "Language / ภาษา")

        # Switch back to Thai
        app.lang_var.set("ไทย")
        app._on_language_change()

        self.assertEqual(app.lang, "th")
        self.assertEqual(app.song_var.get(), "ยังไม่ได้เลือกเพลง")
        self.assertEqual(app.status_var.get(), "พร้อม")
        self.assertEqual(app.preset_var.get(), "Virtual Piano 61 คีย์ (C2-C7)")
        self.assertEqual(app.header_topmost_label.config["text"], "อยู่เหนือหน้าต่างอื่น")
        self.assertEqual(app.sheet_button.config["text"], "ส่งออก Sheet")
        self.assertEqual(app.lang_label.config["text"], "ภาษา / Language")


if __name__ == "__main__":
    unittest.main()
