#!/usr/bin/env python3
"""Entry point: python main.py [song.mid]"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roblox MIDI auto piano")
    parser.add_argument("file", nargs="?", help="ไฟล์ .mid ที่จะเปิดใน GUI")
    parser.add_argument(
        "--sheet",
        metavar="OUT.txt",
        nargs="?",
        const="-",
        help="แปลงโน้ตเป็น Sheet Music แล้วพิมพ์ออก stdout หรือบันทึกลงไฟล์",
    )
    args = parser.parse_args(argv)

    if args.sheet is not None:
        if not args.file:
            parser.error("ต้องระบุไฟล์ MIDI เมื่อใช้ --sheet")
        from player.keymap import transform_notes, virtualpiano61
        from player.midi_loader import load_midi
        from player.sheet import notes_to_sheet

        midi = load_midi(args.file)
        transformed = transform_notes(midi.notes, virtualpiano61())
        sheet = notes_to_sheet(transformed.notes)
        if args.sheet == "-":
            print(sheet)
        else:
            Path(args.sheet).write_text(sheet, encoding="utf-8")
            print(f"บันทึก Sheet Music ที่: {args.sheet}")
        return 0

    from player.gui import run

    run(args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
