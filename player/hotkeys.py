"""Global hotkeys (F8 start/stop, F9 pause, Esc abort, Shift+F9 speed up, Shift+F8 speed down)."""
from __future__ import annotations

from typing import Callable


class Hotkeys:
    """Thin wrapper around pynput GlobalHotKeys.

    Callbacks run on the listener thread. They must not touch tkinter
    directly; the GUI reads a queue instead.
    """

    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_pause: Callable[[], None],
        on_abort: Callable[[], None],
        on_speed_up: Callable[[], None] | None = None,
        on_speed_down: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_toggle = on_toggle
        self._on_pause = on_pause
        self._on_abort = on_abort
        self._on_speed_up = on_speed_up
        self._on_speed_down = on_speed_down
        self._on_error = on_error
        self._listener = None

    def start(self) -> None:
        from pynput import keyboard

        def guard(callback):
            def wrapped():
                try:
                    callback()
                except Exception as exc:  # keep the listener alive
                    if self._on_error:
                        self._on_error(str(exc))

            return wrapped

        bindings = {
            "<f8>": guard(self._on_toggle),
            "<f9>": guard(self._on_pause),
            "<esc>": guard(self._on_abort),
        }
        if self._on_speed_up:
            bindings["<shift>+<f9>"] = guard(self._on_speed_up)
        if self._on_speed_down:
            bindings["<shift>+<f8>"] = guard(self._on_speed_down)

        self._listener = keyboard.GlobalHotKeys(bindings)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
