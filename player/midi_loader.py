"""Read Standard MIDI Files into absolute-time notes."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path


class MidiError(RuntimeError):
    """Raised when a MIDI file can not be read."""


@dataclass(frozen=True)
class Note:
    start: float
    duration: float
    pitch: int
    velocity: int = 64


@dataclass
class MidiInfo:
    path: Path
    notes: list[Note]
    duration: float
    track_count: int
    ticks_per_beat: int


def _tick2second(ticks: int, ticks_per_beat: int, tempo_us: int) -> float:
    return ticks * tempo_us / (1_000_000.0 * ticks_per_beat)


def load_midi(path: str | Path) -> MidiInfo:
    """Parse a .mid file. Tempo changes are honoured; sustain pedal is ignored."""
    try:
        import mido
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MidiError("ไม่พบไลบรารี mido. ติดตั้งก่อน: pip install -r requirements.txt") from exc

    path = Path(path).expanduser()
    if not path.is_file():
        raise MidiError(f"ไม่พบไฟล์: {path}")

    try:
        mid = mido.MidiFile(str(path))
    except Exception as exc:  # mido raises several unrelated types
        raise MidiError(f"อ่าน MIDI ไม่ได้: {exc}") from exc

    if mid.type == 2:
        raise MidiError("ไม่รองรับ MIDI type 2 (แยก track คนละ tempo)")

    ticks_per_beat = mid.ticks_per_beat or 480
    tempo = 500_000  # microseconds per quarter note, 120 BPM
    now = 0.0
    open_notes: dict[tuple[int, int], deque[tuple[float, int]]] = {}
    notes: list[Note] = []

    for msg in mido.merge_tracks(mid.tracks):
        now += _tick2second(msg.time, ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            open_notes.setdefault((msg.channel, msg.note), deque()).append((now, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            stack = open_notes.get((msg.channel, msg.note))
            if stack:
                start, velocity = stack.popleft()
                notes.append(Note(start, max(now - start, 0.001), msg.note, velocity))

    # Notes without a matching note_off: close them at the end of the file.
    for (_, pitch), stack in open_notes.items():
        while stack:
            start, velocity = stack.popleft()
            notes.append(Note(start, max(now - start, 0.001), pitch, velocity))

    notes.sort(key=lambda n: (n.start, n.pitch))
    duration = max((n.start + n.duration for n in notes), default=0.0)
    return MidiInfo(
        path=path,
        notes=notes,
        duration=duration,
        track_count=len(mid.tracks),
        ticks_per_beat=ticks_per_beat,
    )
