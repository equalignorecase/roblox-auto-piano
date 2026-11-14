from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mido

from player.midi_loader import load_midi
from player.musescore import download_musescore_midi


SCORE_URL = "https://musescore.com/user/12/scores/345"
SCRIPT_URL = "https://musescore.com/static/public/build/test/1/2.test.js"
MEDIA_URL = "https://cdn.example/song.mid"
PAGE = f'''<meta property="og:title" content="Test / Song">
<meta property="og:url" content="{SCORE_URL}">
<script src="{SCRIPT_URL}"></script>'''
SCRIPT = '1732584193 -271733879 -1732584194 271733878 a+b+c+"secret").substr(0,4)'


def midi_bytes(*, notes=True):
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    if notes:
        track.append(mido.Message("note_on", note=60, velocity=64))
        track.append(mido.Message("note_off", note=60, time=480))
    data = io.BytesIO()
    mid.save(file=data)
    return data.getvalue()


class Response:
    status_code = 200
    ok = True

    def __init__(self, *, text="", content=b"", data=None):
        self.text = text
        self.content = content
        self.data = data
        self.headers = {"Content-Type": "application/octet-stream"}

    def json(self):
        return self.data

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ScoreHttp:
    cookie_header = ""

    def __init__(self, body):
        self.body = body
        self.closed = False

    def get(self, url, **kwargs):
        if url == SCORE_URL:
            return Response(text=PAGE)
        if url == "https://musescore.com/api/jmuse":
            assert kwargs["params"] == {"id": "345", "index": 0, "type": "midi"}
            token = hashlib.md5(b"345midi0secret").hexdigest()[:4]
            assert kwargs["headers"]["Authorization"] == token
            return Response(data={"status": 200, "info": {"url": MEDIA_URL}})
        if url == MEDIA_URL:
            if isinstance(self.body, Exception):
                raise self.body
            return Response(content=self.body)
        raise AssertionError(f"Unexpected URL: {url}")

    def fetch_text(self, url, **kwargs):
        assert url == SCRIPT_URL
        return SCRIPT

    def close(self):
        self.closed = True


class MuseScoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cwd = Path.cwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, self.cwd)

    def download(self, body, **kwargs):
        http = ScoreHttp(body)
        self.addCleanup(lambda: self.assertTrue(http.closed))
        with patch("player._vendor.musescore_downloader.http_client.HttpClient", return_value=http), \
             patch("player._vendor.musescore_downloader.token.default_cache_dir", return_value=Path.cwd() / "cache"):
            return download_musescore_midi(SCORE_URL, use_browser=False, **kwargs)

    def test_saves_playable_mid_in_current_directory(self):
        statuses = []
        path = self.download(midi_bytes(), on_status=statuses.append)
        self.assertEqual(path.parent, Path.cwd())
        self.assertEqual(path.suffix, ".mid")
        self.assertEqual(path.name, "Test Song.mid")
        self.assertEqual(load_midi(path).notes[0].pitch, 60)
        self.assertTrue(statuses)

    def test_duplicate_download_preserves_existing_song(self):
        first = self.download(midi_bytes())
        first.write_bytes(b"keep my file")
        second = self.download(midi_bytes())
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"keep my file")
        self.assertEqual(load_midi(second).notes[0].pitch, 60)

    def test_invalid_midi_is_not_saved(self):
        with self.assertRaisesRegex(RuntimeError, "MIDI"):
            self.download(b"<html>Login required</html>")
        self.assertEqual(list(Path.cwd().glob("*.mid")), [])
        self.assertEqual(list(Path.cwd().glob(".musescore-*")), [])

    def test_empty_midi_is_not_saved(self):
        with self.assertRaisesRegex(RuntimeError, "โน้ต"):
            self.download(midi_bytes(notes=False))
        self.assertEqual(list(Path.cwd().glob("*.mid")), [])

    def test_network_failure_removes_staging_files(self):
        with self.assertRaisesRegex(RuntimeError, "offline"):
            self.download(RuntimeError("offline"))
        self.assertEqual(list(Path.cwd().glob(".musescore-*")), [])
        self.assertEqual(list(Path.cwd().glob("*.mid")), [])

    def test_rejects_foreign_hosts_and_non_score_urls_before_network(self):
        for url in ("", "https://evil-musescore.com/user/1/scores/2",
                    "https://musescore.com.evil.test/score/2",
                    "file:///tmp/song.mid", "https://musescore.com/",
                    "https://user:password@musescore.com/score/2"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                download_musescore_midi(url, use_browser=False)

    def test_browser_mode_downloads_headlessly(self):
        http = ScoreHttp(midi_bytes())
        http.fetch_page_html = lambda url: PAGE
        with patch("player._vendor.musescore_downloader.browser.BrowserHttpClient", return_value=http) as browser_factory, \
             patch("player._vendor.musescore_downloader.token.default_cache_dir", return_value=Path.cwd() / "cache"):
            path = download_musescore_midi(SCORE_URL)
        self.assertIs(browser_factory.call_args.kwargs["headless"], True)
        self.assertTrue(http.closed)
        self.assertEqual(load_midi(path).notes[0].pitch, 60)

    def test_http_browser_fallback_stays_headless(self):
        from player._vendor.musescore_downloader.browser import BrowserCapture

        http = ScoreHttp(midi_bytes())
        http.fetch_text = lambda *args, **kwargs: "script without a token secret"
        browser = ScoreHttp(b"")
        browser.capture_tokens = lambda *args, **kwargs: BrowserCapture(
            media_urls={"345_midi_0": MEDIA_URL},
        )
        with patch("player._vendor.musescore_downloader.http_client.HttpClient", return_value=http), \
             patch("player._vendor.musescore_downloader.browser.BrowserHttpClient", return_value=browser) as browser_factory, \
             patch("player._vendor.musescore_downloader.token.default_cache_dir", return_value=Path.cwd() / "cache"):
            path = download_musescore_midi(SCORE_URL, use_browser=False)
        self.assertIs(browser_factory.call_args.kwargs["headless"], True)
        self.assertTrue(browser.closed)
        self.assertTrue(http.closed)
        self.assertEqual(load_midi(path).notes[0].pitch, 60)

    def test_browser_capture_fallback_when_script_has_no_secret(self):
        from player._vendor.musescore_downloader.browser import BrowserCapture

        http = ScoreHttp(midi_bytes())
        http.fetch_text = lambda *args, **kwargs: "script without a token secret"
        http.capture_tokens = lambda *args, **kwargs: BrowserCapture(
            media_urls={"345_midi_0": MEDIA_URL},
        )
        with patch("player._vendor.musescore_downloader.http_client.HttpClient", return_value=http), \
             patch("player._vendor.musescore_downloader.token.default_cache_dir", return_value=Path.cwd() / "cache"):
            path = download_musescore_midi(SCORE_URL, use_browser=False)
        self.assertTrue(http.closed)
        self.assertEqual(load_midi(path).notes[0].pitch, 60)


if __name__ == "__main__":
    unittest.main()
