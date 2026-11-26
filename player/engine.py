"""Playback engine: turn mapped notes into timed key press/release events."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .keymap import KeySpec

MIN_HOLD = 0.030  # Roblox piano needs a short key-down duration
CHORD_WINDOW = 0.005  # notes within this window are pressed as one chord

RELEASE = 0  # released before presses at the same timestamp
PRESS = 1


@dataclass(frozen=True)
class TimedNote:
    start: float
    duration: float
    key: KeySpec


@dataclass(frozen=True)
class Event:
    time: float
    kind: int
    key: KeySpec


def build_events(notes) -> list[Event]:
    """Merge overlapping intervals per key, then sort into press/release events."""
    spans: dict[KeySpec, list[tuple[float, float]]] = {}
    for note in notes:
        end = max(note.start + note.duration, note.start + MIN_HOLD)
        spans.setdefault(note.key, []).append((note.start, end))

    events: list[Event] = []
    for key, intervals in spans.items():
        intervals.sort()
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                events.append(Event(start, PRESS, key))
                events.append(Event(end, RELEASE, key))
                start, end = next_start, next_end
        events.append(Event(start, PRESS, key))
        events.append(Event(end, RELEASE, key))

    events.sort(key=lambda event: (event.time, event.kind))
    return events


class Backend:
    """Minimal keyboard backend interface (swappable for tests)."""

    def press(self, key: KeySpec) -> None:
        raise NotImplementedError

    def release(self, key: KeySpec) -> None:
        raise NotImplementedError

    def release_all(self) -> None:
        raise NotImplementedError


class PynputBackend(Backend):
    """Cross-platform backend: Quartz on macOS, SendInput on Windows."""

    def __init__(self) -> None:
        try:
            from pynput.keyboard import Controller, Key
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "ไม่พบไลบรารี pynput. ติดตั้งก่อน: pip install -r requirements.txt"
            ) from exc
        self._controller = Controller()
        self._modifiers = {"ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt}
        self._held: set[KeySpec] = set()

    def press(self, key: KeySpec) -> None:
        modifiers = [self._modifiers[name] for name in ("ctrl", "shift", "alt") if getattr(key, name)]
        for modifier in modifiers:
            self._controller.press(modifier)
        self._controller.press(key.char)
        for modifier in reversed(modifiers):
            self._controller.release(modifier)
        self._held.add(key)

    def release(self, key: KeySpec) -> None:
        if key not in self._held:
            return
        self._controller.release(key.char)
        self._held.discard(key)

    def release_all(self) -> None:
        for key in list(self._held):
            try:
                self._controller.release(key.char)
            except Exception:  # never leave a stuck key because one release failed
                pass
            self._held.discard(key)


class LogBackend(Backend):
    """Records events instead of touching the keyboard. Used by tests."""

    def __init__(self) -> None:
        self.events: list[tuple[float, str, str]] = []
        self._origin = time.perf_counter()
        self._held: set[KeySpec] = set()

    def press(self, key: KeySpec) -> None:
        self.events.append((time.perf_counter() - self._origin, "press", key.label()))
        self._held.add(key)

    def release(self, key: KeySpec) -> None:
        if key in self._held:
            self.events.append((time.perf_counter() - self._origin, "release", key.label()))
            self._held.discard(key)

    def release_all(self) -> None:
        for key in list(self._held):
            self.events.append((time.perf_counter() - self._origin, "release_all", key.label()))
            self._held.discard(key)


class Player:
    """Plays a list of mapped notes on a background thread with real-time tempo scaling.

    A new Player is created for each playback so an old thread can never
    interfere with a new run.
    """

    def __init__(
        self,
        backend: Backend,
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self.backend = backend
        self.on_state = on_state
        self._progress = 0.0
        self.duration = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._tempo_changed = threading.Event()
        self._lock = threading.Lock()
        self._state = "idle"
        self._tempo = 1.0
        self._t0 = 0.0
        self._s0 = 0.0
        self._events: list[Event] = []

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    @property
    def tempo(self) -> float:
        with self._lock:
            return self._tempo

    def set_tempo(self, tempo: float) -> None:
        """Update playback speed dynamically without stopping or restarting."""
        with self._lock:
            val = max(0.1, min(10.0, float(tempo)))
            if abs(val - self._tempo) < 1e-4:
                return
            now = time.perf_counter()
            if self._state == "playing":
                current_song_pos = self._s0 + self._tempo * (now - self._t0)
                self._s0 = max(0.0, min(current_song_pos, self.duration))
                self._t0 = now
            self._tempo = val
            self._tempo_changed.set()

    @property
    def progress(self) -> float:
        with self._lock:
            if self._state == "playing":
                now = time.perf_counter()
                elapsed_song = self._s0 + self._tempo * (now - self._t0)
                return max(0.0, min(elapsed_song, self.duration))
            return self._progress

    @progress.setter
    def progress(self, val: float) -> None:
        with self._lock:
            self._progress = val

    def play(self, notes, countdown: float = 3.0, tempo: float = 1.0) -> None:
        self._events = build_events(notes)
        self.duration = max((event.time for event in self._events), default=0.0)
        with self._lock:
            self._progress = 0.0
            self._tempo = max(0.1, float(tempo))
            self._s0 = 0.0
            self._t0 = 0.0
        self._thread = threading.Thread(
            target=self._run, args=(countdown,), daemon=True, name="midi-player"
        )
        self._thread.start()

    def stop(self, wait: bool = False) -> None:
        self._stop.set()
        self._pause.clear()
        self._tempo_changed.set()
        if wait and self._thread is not None:
            self._thread.join(timeout=2.0)

    def pause(self) -> None:
        with self._lock:
            if self._state == "playing":
                self._pause.set()

    def resume(self) -> None:
        self._pause.clear()

    def toggle_pause(self) -> None:
        if self._pause.is_set() or self.state == "paused":
            self.resume()
        else:
            self.pause()

    def _target_time(self, event_time: float) -> float:
        with self._lock:
            return self._t0 + (event_time - self._s0) / self._tempo

    def _wait_until(self, event_time: float) -> bool:
        """Sleep until event_time in musical seconds. False when stopped."""
        while True:
            if self._stop.is_set():
                return False
            if self._pause.is_set():
                self._set_state("paused")
                self.backend.release_all()
                while self._pause.is_set() and not self._stop.is_set():
                    time.sleep(0.02)
                if self._stop.is_set():
                    return False
                with self._lock:
                    self._t0 = time.perf_counter()
                self._set_state("playing")

            if self._tempo_changed.is_set():
                self._tempo_changed.clear()

            target = self._target_time(event_time)
            remaining = target - time.perf_counter()
            if remaining <= 0:
                return True
            if remaining > 0.003:
                time.sleep(min(remaining - 0.002, 0.02))

    def _run(self, countdown: float) -> None:
        events = self._events
        try:
            if countdown > 0:
                self._set_state("countdown")
                end = time.perf_counter() + countdown
                while time.perf_counter() < end:
                    if self._stop.is_set():
                        return
                    time.sleep(0.02)

            self._set_state("playing")
            with self._lock:
                self._t0 = time.perf_counter()
                self._s0 = 0.0
            index = 0
            total = len(events)
            while index < total:
                if self._stop.is_set():
                    return
                event_time = events[index].time
                with self._lock:
                    self._progress = event_time
                if not self._wait_until(event_time):
                    return

                # Collect everything due now so chord notes go down together.
                group_end = index
                while group_end < total and events[group_end].time <= event_time + CHORD_WINDOW:
                    group_end += 1
                group = events[index:group_end]
                index = group_end
                for event in sorted(group, key=lambda item: (item.time, item.kind)):
                    if event.kind == PRESS:
                        self.backend.press(event.key)
                    else:
                        self.backend.release(event.key)

            with self._lock:
                self._progress = self.duration
            self._set_state("finished")
        except Exception as exc:  # surface backend failures through the state callback
            self._set_state(f"error: {exc}")
        finally:
            self.backend.release_all()
            if self.state not in {"finished", "error"} and str(self.state).startswith("error") is False:
                if self._stop.is_set():
                    self._set_state("stopped")
