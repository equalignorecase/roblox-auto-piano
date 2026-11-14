#!/usr/bin/env python3
"""Entry point: python main.py [song.mid]"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roblox MIDI auto piano")
    parser.add_argument("file", nargs="?", help="ไฟล์ .mid ที่จะเปิดใน GUI")
    args = parser.parse_args(argv)

    from player.gui import run

    run(args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
