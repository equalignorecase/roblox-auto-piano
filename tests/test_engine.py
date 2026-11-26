from __future__ import annotations

import time
import tkinter as tk
from types import SimpleNamespace
import unittest

from player.engine import LogBackend, Player, build_events
from player.gui import App
from player.keymap import KeySpec, MappedNote


class EngineTempoTests(unittest.TestCase):
    def test_build_events_sorting(self):
        notes = [
            MappedNote(start=0.0, duration=0.2, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.5, duration=0.2, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        events = build_events(notes)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].time, 0.0)
        self.assertEqual(events[0].kind, 1)  # press
        self.assertEqual(events[1].time, 0.2)
        self.assertEqual(events[1].kind, 0)  # release

    def test_set_tempo_dynamically_scales_playback(self):
        backend = LogBackend()
        player = Player(backend)
        notes = [
            MappedNote(start=0.0, duration=0.05, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.20, duration=0.05, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        start_time = time.perf_counter()
        player.play(notes, countdown=0.0, tempo=1.0)
        # Immediately double the speed to 2.0x
        player.set_tempo(2.0)
        self.assertEqual(player.tempo, 2.0)
        # Wait for player to finish
        player._thread.join(timeout=1.0)
        elapsed = time.perf_counter() - start_time

        self.assertEqual(player.state, "finished")
        # At 2.0x speed, 0.25s of events should finish in roughly ~0.10s - 0.20s (much faster than 0.25s)
        self.assertLess(elapsed, 0.23)

    def test_pause_and_resume_preserves_tempo(self):
        backend = LogBackend()
        player = Player(backend)
        notes = [
            MappedNote(start=0.0, duration=0.05, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.30, duration=0.05, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        player.play(notes, countdown=0.0, tempo=1.5)
        time.sleep(0.05)
        player.pause()
        self.assertEqual(player.tempo, 1.5)
        time.sleep(0.05)
        player.resume()
        player.stop(wait=True)
        self.assertEqual(player.state, "stopped")


class GuiTempoTests(unittest.TestCase):
    def test_adjust_speed_limits(self):
        tcl = tk.Tcl()
        app = App.__new__(App)
        app.tempo_var = tk.StringVar(tcl, value="1.00")
        app._adjust_speed(0.10)
        self.assertEqual(app.tempo_var.get(), "1.10")

        app._adjust_speed(-0.20)
        self.assertEqual(app.tempo_var.get(), "0.90")

        # Test max limit 4.0
        app.tempo_var.set("3.95")
        app._adjust_speed(0.10)
        self.assertEqual(app.tempo_var.get(), "4.00")

        # Test min limit 0.25
        app.tempo_var.set("0.30")
        app._adjust_speed(-0.10)
        self.assertEqual(app.tempo_var.get(), "0.25")

    def test_on_tempo_change_updates_running_player(self):
        tcl = tk.Tcl()
        app = App.__new__(App)
        app.tempo_var = tk.StringVar(tcl, value="1.00")
        app.status_var = tk.StringVar(tcl, value="กำลังเล่น")
        notes = [
            MappedNote(start=0.0, duration=0.5, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=1.0, duration=0.5, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        app.player = Player(LogBackend())
        app.player.play(notes, countdown=0.0, tempo=1.0)
        app.lang = "th"

        time.sleep(0.05)  # wait for thread to enter playing state
        app.tempo_var.set("1.50")
        app._on_tempo_change()
        self.assertEqual(app.player.tempo, 1.50)
        self.assertIn("1.50x", app.status_var.get())
        app.player.stop(wait=True)

    def test_toggle_play_pause_resume_behavior(self):
        app = App.__new__(App)
        app.player = Player(LogBackend())
        started = []
        app._start = lambda: started.append(True)
        app._is_active = lambda: app.player is not None and app.player.state in {"countdown", "playing", "paused"}

        # When player idle -> calls _start()
        app.player._state = "idle"
        app._toggle()
        self.assertEqual(len(started), 1)

        # When playing -> calls pause()
        app.player._state = "playing"
        app._toggle()
        self.assertTrue(app.player._pause.is_set())

        # When paused -> calls resume()
        app.player._state = "paused"
        app._toggle()
        self.assertFalse(app.player._pause.is_set())

    def test_refresh_buttons_two_button_labels(self):
        app = App.__new__(App)
        app.lang = "th"
        app._downloading = False
        app._is_active = lambda: app.player is not None and app.player.state in {"countdown", "playing", "paused"}

        class DummyButton:
            def __init__(self):
                self.options = {}

            def configure(self, **kwargs):
                self.options.update(kwargs)

        app.start_button = DummyButton()
        app.stop_button = DummyButton()
        app.download_button = DummyButton()
        app.pause_button = None

        # Idle
        app.player = None
        app._refresh_buttons()
        self.assertEqual(app.start_button.options["text"], "เริ่มเล่น (F8)")
        self.assertEqual(app.stop_button.options["state"], "disabled")

        # Playing
        app.player = SimpleNamespace(state="playing")
        app._refresh_buttons()
        self.assertEqual(app.start_button.options["text"], "พัก (F8)")
        self.assertEqual(app.stop_button.options["state"], "normal")
        self.assertEqual(app.stop_button.options["text"], "รีเซ็ต (Esc)")

        # Paused
        app.player = SimpleNamespace(state="paused")
        app._refresh_buttons()
        self.assertEqual(app.start_button.options["text"], "เล่นต่อ (F8)")
        self.assertEqual(app.stop_button.options["state"], "normal")


if __name__ == "__main__":
    unittest.main()
