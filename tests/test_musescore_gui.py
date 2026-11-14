from __future__ import annotations

import queue
import threading
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from player.gui import App


class Button:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def focus_set(self):
        pass


class Panel:
    def __init__(self):
        self.visible = False

    def winfo_manager(self):
        return "grid" if self.visible else ""

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class CompactUiTests(unittest.TestCase):
    def setUp(self):
        self.tcl = tk.Tcl()
        self.app = App.__new__(App)
        self.app.path_var = tk.StringVar(self.tcl)
        self.app.song_var = tk.StringVar(self.tcl)
        self.app.tempo_var = tk.StringVar(self.tcl, value="1.25")
        self.download = Panel()
        self.settings = Panel()
        self.app._panels = {
            "download": (self.download, Button(), "MuseScore"),
            "settings": (self.settings, Button(), "ตั้งค่าการเล่น"),
        }
        self.sizes = []
        self.app.root = SimpleNamespace(
            update_idletasks=lambda: None,
            winfo_width=lambda: 560,
            winfo_reqheight=lambda: 280 + 180 * sum(
                panel.visible for panel in (self.download, self.settings)
            ),
            geometry=self.sizes.append,
        )

    def test_opening_section_expands_window(self):
        self.app._toggle_panel("download")
        self.assertTrue(self.download.visible)
        self.assertFalse(self.settings.visible)
        self.assertEqual(self.sizes[-1], "560x460")

    def test_opening_other_section_closes_previous_section(self):
        self.app._toggle_panel("download")
        self.app._toggle_panel("settings")
        self.assertFalse(self.download.visible)
        self.assertTrue(self.settings.visible)

    def test_closing_section_restores_compact_height(self):
        self.app._toggle_panel("settings")
        self.app._toggle_panel("settings")
        self.assertFalse(self.settings.visible)
        self.assertEqual(self.sizes[-1], "560x280")

    def test_hiding_section_keeps_entered_values(self):
        self.app.path_var.set("/tmp/เพลง.mid")
        self.app._toggle_panel("settings")
        self.app._toggle_panel("settings")
        self.app._toggle_panel("settings")
        self.assertEqual(self.app.path_var.get(), "/tmp/เพลง.mid")
        self.assertEqual(self.app.tempo_var.get(), "1.25")

    def test_song_name_tracks_selected_file(self):
        self.app.path_var.trace_add("write", self.app._update_song)
        self.app.path_var.set("/tmp/เพลงใหม่.mid")
        self.assertEqual(self.app.song_var.get(), "เพลงใหม่.mid")
        self.app.path_var.set("")
        self.assertEqual(self.app.song_var.get(), "ยังไม่ได้เลือกเพลง")

    def test_fit_window_keeps_user_width(self):
        self.app._fit_window()
        self.assertEqual(self.sizes[-1], "560x280")


class MuseScoreGuiTests(unittest.TestCase):
    def setUp(self):
        self.tcl = tk.Tcl()
        self.app = App.__new__(App)
        self.app.root = SimpleNamespace(after=lambda *args: None)
        self.app.player = None
        self.app.backend = None
        self.app._downloading = False
        self.app._midi_cache = None
        self.app.ui_queue = queue.Queue()
        self.app.path_var = tk.StringVar(self.tcl, value="previous.mid")
        self.app.musescore_url_var = tk.StringVar(self.tcl, value="https://musescore.com/score/345")
        self.app.browser_var = tk.BooleanVar(self.tcl, value=True)
        self.app.musescore_status_var = tk.StringVar(self.tcl)
        self.app.status_var = tk.StringVar(self.tcl)
        self.app.info_var = tk.StringVar(self.tcl, value="รายละเอียดเพลงเดิม")
        self.app.start_button = Button()
        self.app.pause_button = Button()
        self.app.download_button = Button()

    def test_download_success_selects_file_and_enables_playback(self):
        path = Path("/tmp/new.mid")
        self.app._downloading = True
        with patch("player.gui.download_musescore_midi", return_value=path):
            self.app._download_worker("345", True)
        self.assertEqual(self.app.path_var.get(), "previous.mid")
        self.app._poll()
        self.assertEqual(self.app.path_var.get(), str(path))
        self.assertFalse(self.app._downloading)
        self.assertEqual(self.app.start_button.options["state"], "normal")
        self.assertIn(str(path), self.app.musescore_status_var.get())
        self.assertIn("พร้อมเล่น", self.app.status_var.get())
        self.assertEqual(self.app.info_var.get(), "")

    def test_failed_download_keeps_previous_file_and_allows_retry(self):
        self.app._downloading = True
        with patch("player.gui.download_musescore_midi", side_effect=RuntimeError("offline")):
            self.app._download_worker("345", False)
        with patch("player.gui.messagebox.showerror"):
            self.app._poll()
        self.assertEqual(self.app.path_var.get(), "previous.mid")
        self.assertFalse(self.app._downloading)
        self.assertIn("offline", self.app.musescore_status_var.get())
        self.assertIn("ดาวน์โหลดไม่สำเร็จ", self.app.status_var.get())
        self.assertEqual(self.app.download_button.options["state"], "normal")

    def test_download_does_not_block_ui_and_f8_cannot_start_playback(self):
        entered = threading.Event()
        release = threading.Event()

        def download(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("worker did not get released")
            return Path("/tmp/new.mid")

        with patch("player.gui.download_musescore_midi", side_effect=download):
            try:
                self.app._download()
                self.assertTrue(entered.wait(2))
                self.assertTrue(self.app._downloading)
                self.assertIn("กำลังดาวน์โหลด", self.app.status_var.get())
                self.assertEqual(self.app.start_button.options["state"], "disabled")
                self.assertEqual(self.app.download_button.options["state"], "disabled")
                self.app._start()
                self.assertIsNone(self.app.player)
            finally:
                release.set()
                self.app.ui_queue.get(timeout=3)

    def test_download_is_disabled_during_playback(self):
        self.app.player = SimpleNamespace(state="playing")
        self.app._refresh_buttons()
        self.assertEqual(self.app.download_button.options["state"], "disabled")
        self.app._download()
        self.assertFalse(self.app._downloading)

    def test_empty_url_does_not_start_worker(self):
        self.app.musescore_url_var.set(" ")
        with patch("player.gui.messagebox.showwarning"):
            self.app._download()
        self.assertFalse(self.app._downloading)

    def test_close_waits_for_download_to_finish(self):
        self.app._downloading = True
        destroyed = []
        self.app.root.destroy = lambda: destroyed.append(True)
        with patch("player.gui.messagebox.showwarning"):
            self.app._on_close()
        self.assertEqual(destroyed, [])


if __name__ == "__main__":
    unittest.main()
