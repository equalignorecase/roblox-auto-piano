# MuseScore MIDI integration

**Goal:** Download a MuseScore score from the Roblox piano GUI, save a playable `.mid` in the process's current directory, and select it for existing F8 playback.

**Constraints:** All changes stay in `roblox-midi-player`. Never change `musescore-downloader-py`. Keep existing local MIDI playback usable without downloader dependencies. Never overwrite an existing song or publish an invalid download.

**Approach:** Vendor the reference library with its MIT license inside `player/_vendor`, preserving its HTTP, token, browser, and error handling. A small adapter validates input, stages downloads, validates MIDI with the existing loader, and publishes a unique filename. Tkinter runs network work on a worker thread and receives results through the existing queue. Requiring the sibling project at runtime would violate standalone operation; rewriting its network stack adds unnecessary risk.

**Files:** `player/_vendor/musescore_downloader/` contains the reference library; `player/musescore.py` owns download and file validation; `player/gui.py` owns URL input and worker feedback; requirements and README cover installation; `tests/test_musescore.py` and `tests/test_musescore_gui.py` cover observable behavior.

- [x] Write failing tests for current-directory saves, playable notes, URL boundaries, collisions, corrupt/empty MIDI, failed download cleanup, and HTTP cleanup.
- [x] Vendor the library and implement `download_musescore_midi(url, *, use_browser=True, on_status=None) -> Path` with no runtime sibling dependency.
- [x] Test and wire URL input, Chromium selection, background download, success/error feedback, and playback guards.
- [x] Document setup and current-directory semantics; run the complete Roblox test suite, reference tests against the vendored code, and attempt a GUI smoke check.
- [x] Verify the original downloader's file hashes are unchanged.

**Review focus:** Reject foreign hosts before networking; preserve previous MIDI selection on error; never write Tk variables from workers; keep F8 from starting playback while Chromium is active; close HTTP/browser resources on all completed requests. No automatic playback after download, because the user must first focus Roblox.

**Verification:** 14 Roblox tests and 20 reference tests passed. The reference tests used the vendored modules with bytecode writing disabled. All 78 original downloader files remained byte-for-byte unchanged. Python compilation and `pip check` passed. PyPI DNS access failed, so the existing system packages were packaged locally and installed into the project venv without network access. Playwright CLI works and Chromium is already cached. Creating a real Tk window exited with status 134 in this execution environment; GUI logic was tested with Tcl variables and the real queue handlers. Live MuseScore downloads and Roblox key delivery were not verified.
