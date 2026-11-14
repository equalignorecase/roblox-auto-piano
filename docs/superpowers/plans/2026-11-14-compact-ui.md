# Compact piano UI implementation plan

**Goal:** Keep the piano visible over Roblox while using less screen space, with a dark interface and collapsible download/settings sections.

**Approved design:** The user accepted a compact main view containing song name, playback controls, and status; a dark gray palette with one accent; and collapsible access to existing download and playback settings. Keep Always on top and every current capability.

**Approach:** Reuse Tkinter/ttk and its built-in clam theme. Keep controls and event handlers in `player/gui.py`. Default to a 480-pixel-wide window with both sections closed. Open one section at a time and fit window height when switching sections or changing status text. Keep the complete MIDI path editable in settings while showing its filename on the main view. Preserve the system font and visible keyboard focus. No new dependencies or features.

**Alternatives:** Styling the existing full form would still cover the game. Replacing Tkinter would add packaging and platform work. The accepted compact layout solves the stated need using the existing toolkit.

**Files:** Modify `player/gui.py`, `tests/test_musescore_gui.py`, and `README.md`. Do not modify the playback engine, downloader, settings schema, or sibling project.

- [x] Add failing tests for section toggling, automatic window height, filename display, and retained values.
- [x] Apply the dark theme and rebuild the view with existing variables and handlers.
- [x] Wire song-name updates and section resizing; keep playback/download guards intact.
- [x] Update usage documentation and run the full test suite and compilation checks.

**Review focus:** Long Thai filenames and errors must wrap; hidden settings retain their values; playback controls remain outside the sections; downloaded songs update the main title; expanding controls must not force a permanently large window. Native rendering and stacking require a real desktop smoke test; the current execution environment previously aborted Tk window creation with exit 134.

**Verification:** All 20 project tests passed, including six new compact-view tests. Existing download tests now also check visible main-view feedback and removal of stale song details. Python compilation passed. Main text and accent-button contrast checks exceeded 4.5:1. Rendering, real window dimensions, and stacking over Roblox remain unverified because native Tk window creation is unavailable in this execution environment. No dependencies were added.
