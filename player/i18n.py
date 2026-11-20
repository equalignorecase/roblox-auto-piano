"""Localization (i18n) for Roblox MIDI auto player."""
from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "th"

LANGUAGE_OPTIONS = (
    ("ไทย", "th"),
    ("English", "en"),
)

PRESETS_BY_LANG = {
    "th": (
        ("Virtual Piano 61 คีย์ (C2-C7)", "virtualpiano61"),
        ("Virtual Piano 88 คีย์ (+Ctrl)", "virtualpiano88"),
        ("กำหนดเอง (mapping.json)", "custom"),
    ),
    "en": (
        ("Virtual Piano 61 keys (C2-C7)", "virtualpiano61"),
        ("Virtual Piano 88 keys (+Ctrl)", "virtualpiano88"),
        ("Custom (mapping.json)", "custom"),
    ),
}

MESSAGES: dict[str, dict[str, str]] = {
    "th": {
        "title": "Roblox Piano",
        "topmost": "อยู่เหนือหน้าต่างอื่น",
        "selected_song": "เพลงที่เลือก",
        "no_song": "ยังไม่ได้เลือกเพลง",
        "browse": "เลือกไฟล์...",
        "browse_title": "เลือกไฟล์ MIDI",
        "filetypes_all": "ทุกไฟล์",
        "play_f8": "เริ่มเล่น (F8)",
        "stop_f8": "หยุด (F8)",
        "pause_f9": "พัก (F9)",
        "resume_f9": "เล่นต่อ (F9)",
        "stop_esc": "หยุด (Esc)",
        "musescore_panel": "MuseScore",
        "settings_panel": "ตั้งค่าการเล่น",
        "musescore_url_label": "URL MuseScore / score ID",
        "download_midi": "ดาวน์โหลด MIDI",
        "use_browser": "ใช้ Chromium เบื้องหลัง",
        "saved_to": "บันทึก .mid ที่: {path}",
        "midi_file_label": "ไฟล์ MIDI (พาธเต็ม)",
        "language_label": "ภาษา / Language",
        "keymap_label": "ผังคีย์",
        "tempo_label": "ความเร็ว",
        "countdown_label": "นับถอยหลัง (วินาที)",
        "transpose_label": "ทรานสโพส (semitone)",
        "octave_label": "อ็อกเทฟ",
        "fold_label": "พับโน้ตนอกช่วงเข้าโน้ตที่ใกล้สุด",
        "roblox_active_hint": "Roblox ต้องเป็นหน้าต่างที่ active ขณะเล่น",
        "state_idle": "พร้อม",
        "state_countdown": "นับถอยหลัง... สลับไปที่ Roblox",
        "state_playing": "กำลังเล่น",
        "state_paused": "พักอยู่ (F9 เพื่อเล่นต่อ)",
        "state_stopped": "หยุดแล้ว",
        "state_finished": "จบเพลง",
        "downloading": "กำลังดาวน์โหลด MIDI...",
        "download_done_status": "พร้อมเล่น · กด F8 แล้วสลับไป Roblox",
        "download_saved": "บันทึกแล้ว: {path} · กด F8 เพื่อเล่น",
        "download_failed": "ดาวน์โหลดไม่สำเร็จ",
        "download_failed_short": "ดาวน์โหลดไม่สำเร็จ",
        "download_failed_detail": "ดาวน์โหลดไม่สำเร็จ: {error}",
        "download_failed_title": "ดาวน์โหลด MuseScore ไม่สำเร็จ",
        "no_url_title": "ยังไม่มี URL",
        "no_url_msg": "ใส่ URL หน้าเพลง MuseScore หรือเลข score ID ก่อน",
        "no_file_title": "ยังไม่มีไฟล์",
        "no_file_msg": "เลือกไฟล์ MIDI ก่อน",
        "invalid_settings_title": "ตั้งค่าไม่ถูกต้อง",
        "tempo_invalid_msg": "ความเร็วต้องมากกว่า 0",
        "cannot_play_title": "เล่นไม่ได้",
        "no_mapped_notes_msg": "ไม่มีโน้ตที่ map เข้าคีย์ได้ — ตรวจผังคีย์หรือเปิดการพับโน้ต",
        "missing_library_title": "ขาดไลบรารี",
        "closing_download_warning_title": "กำลังดาวน์โหลด",
        "closing_download_warning_msg": "รอให้ดาวน์โหลดเสร็จก่อนปิดโปรแกรม",
        "info_stats": "{name}: โน้ต {total} · เล่นได้ {playable} · พับ {folded} · ข้าม {skipped} · ยาว {duration:.1f} วินาที · ผัง {keymap}",
        "macos_access_hint": "macOS ยังไม่ได้ให้สิทธิ์ Accessibility — ไปที่ System Settings > Privacy & Security > Accessibility แล้วเพิ่ม Terminal/Python",
        "hotkey_failed": "global hotkey ไม่ทำงาน: {error}",
        "hotkey_error": "hotkey ผิดพลาด: {error}",
        "error_prefix": "ผิดพลาด: {error}",
        "btn_export_sheet": "ส่งออก Sheet",
        "sheet_window_title": "Roblox Piano Sheet Music",
        "sheet_copied_hint": "คัดลอกลงคลิปบอร์ดแล้ว สามารถบันทึกเป็น .txt หรือก๊อปไปวางได้ทันที",
        "sheet_copy_again": "คัดลอกทั้งหมด",
        "sheet_copied_alert": "คัดลอกลงคลิปบอร์ดเรียบร้อยแล้ว",
        "sheet_save_file": "บันทึกเป็น .txt...",
        "sheet_save_title": "บันทึกไฟล์ Sheet Music",
        "sheet_close": "ปิด",
        "sheet_file_saved": "บันทึกไฟล์เรียบร้อยแล้วที่:\n{path}",
    },
    "en": {
        "title": "Roblox Piano",
        "topmost": "Always on top",
        "selected_song": "Selected Song",
        "no_song": "No song selected",
        "browse": "Browse...",
        "browse_title": "Select MIDI file",
        "filetypes_all": "All files",
        "play_f8": "Play (F8)",
        "stop_f8": "Stop (F8)",
        "pause_f9": "Pause (F9)",
        "resume_f9": "Resume (F9)",
        "stop_esc": "Stop (Esc)",
        "musescore_panel": "MuseScore",
        "settings_panel": "Playback Settings",
        "musescore_url_label": "MuseScore URL / score ID",
        "download_midi": "Download MIDI",
        "use_browser": "Headless Chromium",
        "saved_to": "Save .mid to: {path}",
        "midi_file_label": "MIDI file (full path)",
        "language_label": "Language / ภาษา",
        "keymap_label": "Keymap",
        "tempo_label": "Speed / Tempo",
        "countdown_label": "Countdown (sec)",
        "transpose_label": "Transpose (semitones)",
        "octave_label": "Octave",
        "fold_label": "Fold out-of-range notes to nearest key",
        "roblox_active_hint": "Roblox must be the active window while playing",
        "state_idle": "Ready",
        "state_countdown": "Counting down... Switch to Roblox",
        "state_playing": "Playing",
        "state_paused": "Paused (F9 to resume)",
        "state_stopped": "Stopped",
        "state_finished": "Finished",
        "downloading": "Downloading MIDI...",
        "download_done_status": "Ready to play · Press F8 then switch to Roblox",
        "download_saved": "Saved: {path} · Press F8 to play",
        "download_failed": "Download failed",
        "download_failed_short": "Download failed",
        "download_failed_detail": "Download failed: {error}",
        "download_failed_title": "MuseScore download failed",
        "no_url_title": "No URL",
        "no_url_msg": "Enter a MuseScore URL or score ID first",
        "no_file_title": "No file",
        "no_file_msg": "Please select a MIDI file first",
        "invalid_settings_title": "Invalid settings",
        "tempo_invalid_msg": "Speed must be greater than 0",
        "cannot_play_title": "Cannot play",
        "no_mapped_notes_msg": "No notes could be mapped — check keymap or enable note folding",
        "missing_library_title": "Missing library",
        "closing_download_warning_title": "Downloading",
        "closing_download_warning_msg": "Please wait for download to finish before closing",
        "info_stats": "{name}: notes {total} · playable {playable} · folded {folded} · skipped {skipped} · length {duration:.1f}s · layout {keymap}",
        "macos_access_hint": "macOS Accessibility permission not granted — go to System Settings > Privacy & Security > Accessibility and add Terminal/Python",
        "hotkey_failed": "global hotkey failed: {error}",
        "hotkey_error": "hotkey error: {error}",
        "error_prefix": "Error: {error}",
        "btn_export_sheet": "Export Sheet",
        "sheet_window_title": "Roblox Piano Sheet Music",
        "sheet_copied_hint": "Copied to clipboard! You can save as .txt or paste directly.",
        "sheet_copy_again": "Copy All",
        "sheet_copied_alert": "Copied to clipboard successfully",
        "sheet_save_file": "Save as .txt...",
        "sheet_save_title": "Save Sheet Music File",
        "sheet_close": "Close",
        "sheet_file_saved": "File successfully saved to:\n{path}",
    },
}


def tr(key: str, lang: str = "th", **kwargs: Any) -> str:
    """Translate key for lang with formatting fallback."""
    table = MESSAGES.get(lang, MESSAGES[DEFAULT_LANGUAGE])
    msg = table.get(key)
    if msg is None:
        msg = MESSAGES[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        return msg.format(**kwargs)
    return msg


def get_preset_label(key: str, lang: str = "th") -> str:
    presets = PRESETS_BY_LANG.get(lang, PRESETS_BY_LANG[DEFAULT_LANGUAGE])
    for label, k in presets:
        if k == key:
            return label
    return presets[0][0]


def get_preset_key(label: str) -> str:
    for lang in ("th", "en"):
        for lbl, key in PRESETS_BY_LANG[lang]:
            if lbl == label:
                return key
    return "virtualpiano61"
