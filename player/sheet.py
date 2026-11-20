"""Convert mapped MIDI notes to Roblox Virtual Piano sheet music text."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .keymap import KeySpec, MappedNote

UNSHIFTED_TO_SHIFTED = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    "-": "_", "=": "+", "[": "{", "]": "}", ";": ":",
    "'": '"', ",": "<", ".": ">", "/": "?", "\\": "|", "`": "~",
}


def key_to_sheet_char(key: KeySpec) -> str:
    """Return the sheet music character for a KeySpec."""
    if key.shift:
        if key.char.isalpha():
            return key.char.upper()
        if key.char in UNSHIFTED_TO_SHIFTED:
            return UNSHIFTED_TO_SHIFTED[key.char]
    return key.char


def notes_to_sheet(
    notes: Sequence[MappedNote],
    *,
    chord_tolerance: float = 0.035,
    pause_threshold: float = 0.8,
    max_line_length: int = 60,
) -> str:
    """Convert a sequence of MappedNote into Virtual Piano sheet text.

    Notes occurring within chord_tolerance are grouped into chords, e.g. [tuo].
    Pauses larger than pause_threshold or lines longer than max_line_length
    produce line breaks.
    """
    if not notes:
        return ""

    # Sort primarily by start time, secondarily by pitch
    sorted_notes = sorted(notes, key=lambda n: (n.start, n.key_pitch))

    # Group notes into simultaneous clusters (chords)
    clusters: list[tuple[float, list[MappedNote]]] = []
    for note in sorted_notes:
        if not clusters or (note.start - clusters[-1][0]) > chord_tolerance:
            clusters.append((note.start, [note]))
        else:
            clusters[-1][1].append(note)

    tokens: list[tuple[float, str]] = []
    for start_time, cluster_notes in clusters:
        # Deduplicate chars while preserving pitch order
        seen_chars: set[str] = set()
        chars: list[str] = []
        for n in sorted(cluster_notes, key=lambda x: x.key_pitch):
            ch = key_to_sheet_char(n.key)
            if ch not in seen_chars:
                seen_chars.add(ch)
                chars.append(ch)

        if not chars:
            continue
        if len(chars) == 1:
            tokens.append((start_time, chars[0]))
        else:
            tokens.append((start_time, f"[{''.join(chars)}]"))

    if not tokens:
        return ""

    lines: list[str] = []
    current_line: list[str] = [tokens[0][1]]
    current_length = len(tokens[0][1])
    last_time = tokens[0][0]

    for start_time, tok in tokens[1:]:
        gap = start_time - last_time
        last_time = start_time
        tok_len = len(tok)

        # If a significant musical pause occurs, break line
        if gap >= pause_threshold:
            lines.append(" ".join(current_line))
            current_line = [tok]
            current_length = tok_len
        elif current_length + 1 + tok_len > max_line_length:
            lines.append(" ".join(current_line))
            current_line = [tok]
            current_length = tok_len
        else:
            current_line.append(tok)
            current_length += 1 + tok_len

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


def export_sheet_file(notes: Sequence[MappedNote], path: str | Path, **kwargs) -> Path:
    """Generate sheet text and save to a file."""
    text = notes_to_sheet(notes, **kwargs)
    out_path = Path(path).expanduser().resolve()
    out_path.write_text(text, encoding="utf-8")
    return out_path
