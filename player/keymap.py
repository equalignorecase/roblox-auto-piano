"""Map MIDI pitches to keyboard keys used by Roblox piano games."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

WHITE_PCS = {0, 2, 4, 5, 7, 9, 11}
BLACK_PCS = {1, 3, 6, 8, 10}

# Standard 61-key virtual piano layout. Each row lists the white keys of that
# row (left to right) and the MIDI pitch of the row's first white key.
# Numbers row: C2-E3, QWERTY row: F3-A4, home row: B4-C6, bottom row: D6-C7.
VIRTUAL_PIANO_ROWS = (
    ("1234567890", 36),  # C2
    ("qwertyuiop", 53),  # F3
    ("asdfghjkl", 71),   # B4
    ("zxcvbnm", 86),     # D6
)

SHIFTED_SYMBOLS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "{": "[", "}": "]", ":": ";",
    '"': "'", "<": ",", ">": ".", "?": "/", "|": "\\", "~": "`",
}


@dataclass(frozen=True)
class KeySpec:
    """One physical key press, with optional modifiers."""

    char: str
    shift: bool = False
    ctrl: bool = False
    alt: bool = False

    def label(self) -> str:
        parts = []
        if self.ctrl:
            parts.append("Ctrl")
        if self.alt:
            parts.append("Alt")
        if self.shift:
            parts.append("Shift")
        parts.append(self.char)
        return "+".join(parts)


def parse_key_spec(text: str) -> KeySpec:
    """Parse "t", "T", "shift+t", "ctrl+1", "!" into a KeySpec."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ค่าคีย์ว่าง")
    text = text.strip()
    parts = [p for p in text.split("+") if p != ""]
    if not parts:
        raise ValueError(f"ค่าคีย์ไม่ถูกต้อง: {text!r}")

    modifiers = {p.lower() for p in parts[:-1]}
    unknown = modifiers - {"shift", "ctrl", "alt"}
    if unknown:
        raise ValueError(f"ตัวปรับไม่รู้จัก: {', '.join(sorted(unknown))}")

    char = parts[-1]
    shift = "shift" in modifiers
    ctrl = "ctrl" in modifiers
    alt = "alt" in modifiers

    if len(char) != 1:
        raise ValueError(f"ต้องเป็นคีย์เดี่ยว: {text!r}")
    if char.isupper():
        shift = True
        char = char.lower()
    if char in SHIFTED_SYMBOLS:
        shift = True
        char = SHIFTED_SYMBOLS[char]

    return KeySpec(char=char, shift=shift, ctrl=ctrl, alt=alt)


@dataclass
class KeyMap:
    name: str
    keys: dict[int, KeySpec]
    min_pitch: int
    max_pitch: int

    def get(self, pitch: int) -> KeySpec | None:
        return self.keys.get(pitch)

    def nearest(self, pitch: int) -> int | None:
        """Nearest mapped pitch; for out-of-range notes first fold by octaves."""
        lo, hi = self.min_pitch, self.max_pitch
        p = pitch
        while p < lo:
            p += 12
        while p > hi:
            p -= 12
        if p in self.keys:
            return p
        for distance in range(1, 13):
            for candidate in (p - distance, p + distance):
                if candidate in self.keys:
                    return candidate
        return None


def _row_whites(start_pitch: int, count: int) -> list[int]:
    out: list[int] = []
    pitch = start_pitch
    while len(out) < count:
        if pitch % 12 in WHITE_PCS:
            out.append(pitch)
        pitch += 1
    return out


def virtualpiano61() -> KeyMap:
    """Standard virtualpiano.net layout, C2-C7 (61 keys)."""
    keys: dict[int, KeySpec] = {}
    for chars, start_pitch in VIRTUAL_PIANO_ROWS:
        whites = _row_whites(start_pitch, len(chars))
        for char, pitch in zip(chars, whites):
            keys[pitch] = KeySpec(char)
            if (pitch + 1) % 12 in BLACK_PCS:
                keys[pitch + 1] = KeySpec(char, shift=True)
    return KeyMap("virtualpiano61", keys, 36, 96)


def virtualpiano88() -> KeyMap:
    """61-key layout plus Ctrl+key for A0-B1 and C#7-C8 (88 keys).

    The Ctrl layer is our own deterministic extension: Ctrl+the first 27 keys
    in reading order (numbers, QWERTY, home row) cover the 15 low extras and
    12 high extras. Edit mapping.json if your game uses another scheme.
    """
    base = virtualpiano61()
    keys = dict(base.keys)
    order = [char for chars, _ in VIRTUAL_PIANO_ROWS for char in chars]
    extras = list(range(21, 36)) + list(range(97, 109))
    for char, pitch in zip(order, extras):
        if pitch not in keys:
            keys[pitch] = KeySpec(char, ctrl=True)
    return KeyMap("virtualpiano88", keys, 21, 108)


def load_mapping(path: str | Path) -> KeyMap:
    """Load a custom mapping JSON.

    Format:
        {"name": "my game", "min_pitch": 21, "max_pitch": 108,
         "keys": {"60": "t", "61": "shift+t", "36": "ctrl+1"}}
    A flat {"60": "t"} object is also accepted.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError(f"ไม่พบไฟล์ผังคีย์: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON ไม่ถูกต้องที่บรรทัด {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("ไฟล์ผังคีย์ต้องเป็น JSON object")

    raw_keys = data.get("keys", data.get("mapping", data))
    if not isinstance(raw_keys, dict) or not raw_keys:
        raise ValueError("ไม่มีรายการ keys ในไฟล์ผังคีย์")

    keys: dict[int, KeySpec] = {}
    for raw_pitch, raw_key in raw_keys.items():
        if isinstance(raw_key, dict):  # tolerate {"60": {"key": "t"}}
            raw_key = raw_key.get("key", raw_key.get("char"))
        try:
            pitch = int(raw_pitch)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"หมายเลขโน้ตไม่ถูกต้อง: {raw_pitch!r}") from exc
        if not 0 <= pitch <= 127:
            raise ValueError(f"โน้ต MIDI ต้องอยู่ 0-127: {pitch}")
        try:
            keys[pitch] = parse_key_spec(raw_key)
        except ValueError as exc:
            raise ValueError(f"คีย์ของโน้ต {pitch}: {exc}") from exc

    name = str(data.get("name") or path.stem)
    min_pitch = int(data.get("min_pitch", min(keys)))
    max_pitch = int(data.get("max_pitch", max(keys)))
    return KeyMap(name, keys, min_pitch, max_pitch)


PRESETS = {
    "virtualpiano61": virtualpiano61,
    "virtualpiano88": virtualpiano88,
}


@dataclass
class MappedNote:
    start: float
    duration: float
    source_pitch: int
    key_pitch: int
    key: KeySpec


@dataclass
class TransformResult:
    notes: list[MappedNote]
    folded: int
    skipped: int

    @property
    def duration(self) -> float:
        return max((n.start + n.duration for n in self.notes), default=0.0)


def transform_notes(
    notes,
    keymap: KeyMap,
    *,
    tempo: float = 1.0,
    transpose: int = 0,
    octave: int = 0,
    fold: bool = True,
) -> TransformResult:
    """Apply tempo/transpose/octave and resolve each note to a key."""
    if tempo <= 0:
        raise ValueError("tempo ต้องมากกว่า 0")
    mapped: list[MappedNote] = []
    folded = 0
    skipped = 0
    for note in notes:
        pitch = note.pitch + transpose + 12 * octave
        if pitch in keymap.keys:
            key_pitch = pitch
        elif not fold:
            skipped += 1
            continue
        else:
            key_pitch = keymap.nearest(pitch)
            if key_pitch is None or key_pitch not in keymap.keys:
                skipped += 1
                continue
            folded += 1
        mapped.append(
            MappedNote(
                start=note.start / tempo,
                duration=note.duration / tempo,
                source_pitch=note.pitch,
                key_pitch=key_pitch,
                key=keymap.keys[key_pitch],
            )
        )
    return TransformResult(mapped, folded, skipped)
