from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from player.keymap import KeySpec, MappedNote
from player.sheet import export_sheet_file, key_to_sheet_char, notes_to_sheet


class SheetExportTests(unittest.TestCase):
    def test_key_to_sheet_char(self):
        # White keys
        self.assertEqual(key_to_sheet_char(KeySpec("1")), "1")
        self.assertEqual(key_to_sheet_char(KeySpec("t")), "t")

        # Shifted letters -> uppercase
        self.assertEqual(key_to_sheet_char(KeySpec("t", shift=True)), "T")
        self.assertEqual(key_to_sheet_char(KeySpec("q", shift=True)), "Q")

        # Shifted numbers -> symbols
        self.assertEqual(key_to_sheet_char(KeySpec("1", shift=True)), "!")
        self.assertEqual(key_to_sheet_char(KeySpec("2", shift=True)), "@")
        self.assertEqual(key_to_sheet_char(KeySpec("4", shift=True)), "$")

    def test_single_notes_sequence(self):
        notes = [
            MappedNote(start=0.0, duration=0.2, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.3, duration=0.2, source_pitch=64, key_pitch=64, key=KeySpec("u")),
            MappedNote(start=0.6, duration=0.2, source_pitch=67, key_pitch=67, key=KeySpec("o")),
        ]
        sheet = notes_to_sheet(notes)
        self.assertEqual(sheet, "t u o")

    def test_chord_grouped_in_brackets(self):
        # Simultaneous notes (C major chord: t, u, o)
        notes = [
            MappedNote(start=0.0, duration=0.5, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.01, duration=0.5, source_pitch=64, key_pitch=64, key=KeySpec("u")),
            MappedNote(start=0.02, duration=0.5, source_pitch=67, key_pitch=67, key=KeySpec("o")),
        ]
        sheet = notes_to_sheet(notes)
        self.assertEqual(sheet, "[tuo]")

    def test_chords_and_single_notes(self):
        notes = [
            # Chord at 0.0
            MappedNote(start=0.0, duration=0.2, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.0, duration=0.2, source_pitch=67, key_pitch=67, key=KeySpec("o")),
            # Single note at 0.3
            MappedNote(start=0.3, duration=0.2, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        sheet = notes_to_sheet(notes)
        self.assertEqual(sheet, "[to] u")

    def test_pause_produces_line_break(self):
        notes = [
            MappedNote(start=0.0, duration=0.2, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            # Large pause (1.5s gap >= pause_threshold 0.8)
            MappedNote(start=1.5, duration=0.2, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        sheet = notes_to_sheet(notes, pause_threshold=0.8)
        self.assertEqual(sheet, "t\nu")

    def test_export_sheet_file(self):
        notes = [
            MappedNote(start=0.0, duration=0.2, source_pitch=60, key_pitch=60, key=KeySpec("t")),
            MappedNote(start=0.2, duration=0.2, source_pitch=64, key_pitch=64, key=KeySpec("u")),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_sheet.txt"
            res_path = export_sheet_file(notes, out_file)
            self.assertTrue(res_path.is_file())
            self.assertEqual(res_path.read_text(encoding="utf-8"), "t u")


if __name__ == "__main__":
    unittest.main()
