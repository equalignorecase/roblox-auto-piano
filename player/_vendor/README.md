# Bundled MuseScore downloader

`musescore_downloader/` is an unchanged copy of the library modules from
`musescore-downloader-py/musescore_downloader/` in this workspace, bundled on
2026-11-14. Its MIT license is included in that directory. CLI entry points
are omitted. The reference directory is never imported or modified at runtime.

The Roblox integration uses only MIDI downloads. PDF helpers remain because
the reference downloader imports them; optional PDF dependencies are not installed.

When updating this copy, run the Roblox tests and the reference library tests
against this directory. Website or token changes may require an update.
