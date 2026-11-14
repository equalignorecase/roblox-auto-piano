"""Download and validate MuseScore MIDI files for the piano player."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .midi_loader import load_midi


def download_musescore_midi(
    url: str,
    *,
    use_browser: bool = True,
    on_status: Callable[[str], None] | None = None,
) -> Path:
    """Save a playable .mid in cwd without replacing any existing file."""
    value = url.strip()
    if value.isascii() and value.isdigit():
        value = f"https://musescore.com/score/{value}"
    elif value.startswith(("musescore.com/", "www.musescore.com/")):
        value = "https://" + value
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"musescore.com", "www.musescore.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 80, 443}
        or not re.fullmatch(r"/(?:score/[0-9]+|(?:user/[0-9]+|[\w-]+)/scores/[0-9]+)/?", parsed.path)
    ):
        raise ValueError("ใส่ URL หน้าเพลง MuseScore หรือเลข score ID")
    url = "https://musescore.com" + parsed.path
    directory = Path.cwd()

    try:
        from ._vendor.musescore_downloader.browser import BrowserHttpClient
        from ._vendor.musescore_downloader.downloader import MuseScoreDownloader
        from ._vendor.musescore_downloader.http_client import HttpClient
        from ._vendor.musescore_downloader.utils import Logger, sanitize_filename
    except ImportError as exc:
        raise RuntimeError(
            "ขาดไลบรารีดาวน์โหลด: python -m pip install -r requirements.txt"
        ) from exc

    class StatusLogger(Logger):
        def status(self, message: str) -> None:
            if on_status is not None:
                on_status(message)

    logger = StatusLogger()
    logger.status("กำลังโหลด MuseScore เบื้องหลัง..." if use_browser else "กำลังเชื่อมต่อ MuseScore...")
    http = BrowserHttpClient(headless=True, logger=logger) if use_browser else HttpClient()
    try:
        downloader = MuseScoreDownloader(url, http=http, logger=logger, use_browser=use_browser, headless=True)
        score = downloader.load()
        if not score.is_valid:
            raise RuntimeError("ไม่พบ score ID จากหน้า MuseScore")
        with tempfile.TemporaryDirectory(prefix=".musescore-", dir=directory) as staging:
            temporary = downloader.download_midi(str(Path(staging) / "download.mid"))
            logger.status("กำลังตรวจไฟล์ MIDI...")
            midi = load_midi(temporary)
            if not midi.notes:
                raise RuntimeError("ไฟล์ MIDI ไม่มีโน้ตให้เล่น")
            name = sanitize_filename(score.base_filename, fallback=f"musescore-{score.score_id}")
            destination = directory / f"{name}.mid"
            index = 1
            while True:
                try:
                    # Both paths share a filesystem; linking publishes atomically without overwriting.
                    os.link(temporary, destination)
                    return destination
                except FileExistsError:
                    destination = directory / f"{name} ({index}).mid"
                    index += 1
    finally:
        http.close()
