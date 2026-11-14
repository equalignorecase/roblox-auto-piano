"""Tkinter GUI for the Roblox MIDI auto player."""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import config
from .engine import Player, PynputBackend
from .hotkeys import Hotkeys
from .keymap import PRESETS, KeyMap, load_mapping, transform_notes
from .midi_loader import MidiError, load_midi
from .musescore import download_musescore_midi

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = APP_DIR


def custom_mapping_path() -> Path:
    """Prefer a user-editable mapping.json next to the app, then the bundle."""
    for candidate in (Path.cwd() / "mapping.json", APP_DIR / "mapping.json", BUNDLE_DIR / "mapping.json"):
        if candidate.is_file():
            return candidate
    return APP_DIR / "mapping.json"

PRESETS_UI = (
    ("Virtual Piano 61 คีย์ (C2-C7)", "virtualpiano61"),
    ("Virtual Piano 88 คีย์ (+Ctrl)", "virtualpiano88"),
    ("กำหนดเอง (mapping.json)", "custom"),
)

STATE_LABELS = {
    "idle": "พร้อม",
    "countdown": "นับถอยหลัง... สลับไปที่ Roblox",
    "playing": "กำลังเล่น",
    "paused": "พักอยู่ (F9 เพื่อเล่นต่อ)",
    "stopped": "หยุดแล้ว",
    "finished": "จบเพลง",
}


def _accessibility_trusted() -> bool | None:
    """macOS only: is this process allowed to send synthetic key events?"""
    if sys.platform != "darwin":
        return None
    try:
        import ApplicationServices

        return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception:
        return None


class App:
    def __init__(self, root: tk.Tk, initial_file: str | None = None) -> None:
        self.root = root
        self.root.title("Roblox MIDI Auto Piano")
        self.root.attributes("-topmost", True)
        self.root.minsize(480, 250)
        self._apply_theme()

        settings = config.load_settings()
        self.path_var = tk.StringVar(value=initial_file or settings["midi_path"])
        self.song_var = tk.StringVar()
        self._update_song()
        self.path_var.trace_add("write", self._update_song)
        self.musescore_url_var = tk.StringVar()
        self.browser_var = tk.BooleanVar(value=True)
        self.musescore_status_var = tk.StringVar(value=f"บันทึก .mid ที่: {Path.cwd()}")
        self.preset_var = tk.StringVar(
            value=dict((key, label) for label, key in PRESETS_UI).get(
                settings["preset"], PRESETS_UI[0][0]
            )
        )
        self.tempo_var = tk.StringVar(value=settings["tempo"])
        self.transpose_var = tk.StringVar(value=settings["transpose"])
        self.octave_var = tk.StringVar(value=settings["octave"])
        self.countdown_var = tk.StringVar(value=settings["countdown"])
        self.fold_var = tk.BooleanVar(value=bool(settings["fold"]))
        self.status_var = tk.StringVar(value="พร้อม")
        self.info_var = tk.StringVar(value="")

        self.ui_queue: queue.Queue = queue.Queue()
        self.player: Player | None = None
        self.backend: PynputBackend | None = None
        self._midi_cache: tuple[str, float, object] | None = None
        self._hotkeys: Hotkeys | None = None
        self._downloading = False

        self._build_widgets()
        self._refresh_buttons()
        self._start_hotkeys()
        self._show_permission_hint()
        for variable in (self.song_var, self.status_var, self.info_var, self.musescore_status_var):
            # Let Tk update the label text before measuring its wrapped height.
            variable.trace_add("write", lambda *_args: self.root.after(0, self._fit_window))
        self._fit_window()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll)

    # ------------------------------------------------------------------ UI
    def _apply_theme(self) -> None:
        background = "#151c24"
        surface = "#202a36"
        field = "#101720"
        text = "#eef3f8"
        muted = "#afbdcc"
        border = "#617287"
        accent = "#77dfb5"
        self.root.configure(background=background)
        default_font = tkfont.nametofont("TkDefaultFont", root=self.root)
        default_font.configure(size=11)
        family = default_font.actual("family")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=background, foreground=text, font="TkDefaultFont")
        style.configure("TFrame", background=background)
        style.configure("Surface.TFrame", background=surface)
        style.configure("TLabel", background=background, foreground=text)
        style.configure("Title.TLabel", font=(family, 14, "bold"))
        style.configure("Song.TLabel", background=surface, font=(family, 12, "bold"))
        style.configure("Muted.TLabel", foreground=muted)
        style.configure("SurfaceMuted.TLabel", background=surface, foreground=muted)
        style.configure(
            "TButton", background=surface, foreground=text, bordercolor=border,
            padding=(12, 8), relief="flat", focuscolor=accent, focusthickness=2,
        )
        style.map(
            "TButton", background=[("pressed", "#40536a"), ("active", "#344457")],
            foreground=[("disabled", muted)], bordercolor=[("focus", accent)],
        )
        style.configure("Accent.TButton", background=accent, foreground=field, bordercolor=accent, focuscolor=field)
        style.map(
            "Accent.TButton",
            background=[("disabled", surface), ("pressed", "#54bc94"), ("active", "#9ceaca")],
            foreground=[("disabled", muted), ("!disabled", field)],
        )
        for widget in ("TEntry", "TSpinbox", "TCombobox"):
            style.configure(
                widget, fieldbackground=field, background=surface, foreground=text,
                insertcolor=text, arrowcolor=text, bordercolor=border,
                lightcolor=border, darkcolor=border, padding=6,
            )
            style.map(
                widget, bordercolor=[("focus", accent)],
                fieldbackground=[("readonly", field)], foreground=[("readonly", text)],
                selectbackground=[("!disabled", accent)], selectforeground=[("!disabled", field)],
            )
        style.configure("TCheckbutton", background=background, foreground=text, focuscolor=accent)
        style.map("TCheckbutton", background=[("active", background)], indicatorbackground=[("selected", accent)])
        style.configure("Horizontal.TProgressbar", background=accent, troughcolor=field, bordercolor=field, thickness=6)
        self.root.option_add("*TCombobox*Listbox.background", field)
        self.root.option_add("*TCombobox*Listbox.foreground", text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", field)

    def _build_widgets(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(header, text="Roblox Piano", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="อยู่เหนือหน้าต่างอื่น", style="Muted.TLabel").pack(side="right")

        song = ttk.Frame(main, style="Surface.TFrame", padding=12)
        song.grid(row=1, column=0, sticky="ew")
        song.columnconfigure(0, weight=1)
        ttk.Label(song, text="เพลงที่เลือก", style="SurfaceMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(song, textvariable=self.song_var, style="Song.TLabel", wraplength=300).grid(
            row=1, column=0, sticky="w", pady=(4, 0),
        )
        ttk.Button(song, text="เลือกไฟล์...", command=self._browse).grid(
            row=0, column=1, rowspan=2, padx=(12, 0),
        )

        controls = ttk.Frame(main)
        controls.grid(row=2, column=0, sticky="ew", pady=(12, 12))
        controls.columnconfigure(0, weight=2)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        self.start_button = ttk.Button(controls, text="เริ่มเล่น (F8)", style="Accent.TButton", command=self._toggle)
        self.start_button.grid(row=0, column=0, sticky="ew")
        self.pause_button = ttk.Button(controls, text="พัก (F9)", command=self._toggle_pause)
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(controls, text="หยุด (Esc)", command=self._abort).grid(row=0, column=2, sticky="ew")

        self.progress = ttk.Progressbar(main, mode="determinate", maximum=1.0)
        self.progress.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(main, textvariable=self.status_var, wraplength=440).grid(row=4, column=0, sticky="w")
        ttk.Label(main, textvariable=self.info_var, style="Muted.TLabel", wraplength=440).grid(
            row=5, column=0, sticky="w", pady=(4, 8),
        )

        sections = ttk.Frame(main)
        sections.grid(row=6, column=0, sticky="ew", pady=(4, 0))
        sections.columnconfigure(0, weight=1)
        sections.columnconfigure(1, weight=1)
        download_toggle = ttk.Button(sections, text="MuseScore +", command=lambda: self._toggle_panel("download"))
        download_toggle.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        settings_toggle = ttk.Button(sections, text="ตั้งค่าการเล่น +", command=lambda: self._toggle_panel("settings"))
        settings_toggle.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        download = ttk.Frame(main, padding=(0, 12, 0, 0))
        download.grid(row=7, column=0, sticky="ew")
        download.columnconfigure(0, weight=1)
        ttk.Label(download, text="URL MuseScore / score ID").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Entry(download, textvariable=self.musescore_url_var).grid(row=1, column=0, sticky="ew")
        self.download_button = ttk.Button(download, text="ดาวน์โหลด MIDI", command=self._download)
        self.download_button.grid(row=1, column=1, padx=(8, 0))
        ttk.Checkbutton(
            download, text="ใช้ Chromium เบื้องหลัง", variable=self.browser_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(download, textvariable=self.musescore_status_var, style="Muted.TLabel", wraplength=440).grid(
            row=3, column=0, columnspan=2, sticky="w",
        )

        options = ttk.Frame(main, padding=(0, 12, 0, 0))
        options.grid(row=8, column=0, sticky="ew")
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="ไฟล์ MIDI (พาธเต็ม)").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Entry(options, textvariable=self.path_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        ttk.Label(options, text="ผังคีย์").grid(row=2, column=0, columnspan=2, sticky="w")
        self.preset_box = ttk.Combobox(
            options,
            textvariable=self.preset_var,
            values=[label for label, _ in PRESETS_UI],
            state="readonly",
        )
        self.preset_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        ttk.Label(options, text="ความเร็ว").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(
            options, from_=0.25, to=4.0, increment=0.05, width=8,
            textvariable=self.tempo_var,
        ).grid(row=5, column=0, sticky="ew", padx=(0, 8), pady=(4, 12))

        ttk.Label(options, text="นับถอยหลัง (วินาที)").grid(row=4, column=1, sticky="w")
        ttk.Spinbox(
            options, from_=0, to=15, width=8, textvariable=self.countdown_var
        ).grid(row=5, column=1, sticky="ew", pady=(4, 12))

        ttk.Label(options, text="ทรานสโพส (semitone)").grid(row=6, column=0, sticky="w")
        ttk.Spinbox(
            options, from_=-24, to=24, width=8, textvariable=self.transpose_var
        ).grid(row=7, column=0, sticky="ew", padx=(0, 8), pady=(4, 12))

        ttk.Label(options, text="อ็อกเทฟ").grid(row=6, column=1, sticky="w")
        ttk.Spinbox(
            options, from_=-3, to=3, width=8, textvariable=self.octave_var
        ).grid(row=7, column=1, sticky="ew", pady=(4, 12))

        ttk.Checkbutton(
            options, text="พับโน้ตนอกช่วงเข้าโน้ตที่ใกล้สุด", variable=self.fold_var
        ).grid(row=8, column=0, columnspan=2, sticky="w")
        ttk.Label(
            main, text="Roblox ต้องเป็นหน้าต่างที่ active ขณะเล่น",
            style="Muted.TLabel", wraplength=440,
        ).grid(row=9, column=0, sticky="w", pady=(12, 0))
        self._panels = {
            "download": (download, download_toggle, "MuseScore"),
            "settings": (options, settings_toggle, "ตั้งค่าการเล่น"),
        }
        download.grid_remove()
        options.grid_remove()

    def _update_song(self, *_args) -> None:
        path = self.path_var.get().strip()
        self.song_var.set(Path(path).name if path else "ยังไม่ได้เลือกเพลง")

    def _fit_window(self, *_args) -> None:
        self.root.update_idletasks()
        self.root.geometry(f"{max(480, self.root.winfo_width())}x{self.root.winfo_reqheight()}")

    def _toggle_panel(self, name: str) -> None:
        selected = self._panels[name][0]
        opening = not selected.winfo_manager()
        for key, (panel, button, label) in self._panels.items():
            if key == name and opening:
                panel.grid()
                button.configure(text=f"{label} −")
            else:
                panel.grid_remove()
                button.configure(text=f"{label} +")
        self._panels[name][1].focus_set()
        self._fit_window()

    def _show_permission_hint(self) -> None:
        trusted = _accessibility_trusted()
        if trusted is False:
            self.info_var.set(
                "macOS ยังไม่ได้ให้สิทธิ์ Accessibility — ไปที่ System Settings > "
                "Privacy & Security > Accessibility แล้วเพิ่ม Terminal/Python"
            )

    # ------------------------------------------------------------ actions
    def _download(self) -> None:
        if self._downloading or self._is_active():
            return
        url = self.musescore_url_var.get().strip()
        if not url:
            messagebox.showwarning("ยังไม่มี URL", "ใส่ URL หน้าเพลง MuseScore หรือเลข score ID ก่อน")
            return
        self._downloading = True
        self.musescore_status_var.set("กำลังดาวน์โหลด MIDI...")
        self.status_var.set("กำลังดาวน์โหลด MIDI...")
        self._refresh_buttons()
        threading.Thread(
            target=self._download_worker, args=(url, self.browser_var.get()), daemon=True,
        ).start()

    def _download_worker(self, url: str, use_browser: bool) -> None:
        try:
            path = download_musescore_midi(
                url, use_browser=use_browser,
                on_status=lambda message: self.ui_queue.put(("download_status", message)),
            )
            self.ui_queue.put(("download_done", path))
        except Exception as exc:
            self.ui_queue.put(("download_error", str(exc)))

    def _browse(self) -> None:
        initial = Path(self.path_var.get()).expanduser().parent
        path = filedialog.askopenfilename(
            title="เลือกไฟล์ MIDI",
            initialdir=str(initial) if initial.is_dir() else str(Path.home()),
            filetypes=[("MIDI", "*.mid *.midi"), ("ทุกไฟล์", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self.info_var.set("")

    def _preset_key(self) -> str:
        mapping = {label: key for label, key in PRESETS_UI}
        return mapping.get(self.preset_var.get(), "virtualpiano61")

    def _get_keymap(self) -> KeyMap:
        preset = self._preset_key()
        if preset == "custom":
            return load_mapping(custom_mapping_path())
        return PRESETS[preset]()

    def _get_backend(self) -> PynputBackend:
        if self.backend is None:
            self.backend = PynputBackend()
        return self.backend

    def _load_midi(self, path: str):
        resolved = str(Path(path).expanduser().resolve())
        mtime = Path(resolved).stat().st_mtime
        if self._midi_cache and self._midi_cache[0] == resolved and self._midi_cache[1] == mtime:
            return self._midi_cache[2]
        info = load_midi(resolved)
        self._midi_cache = (resolved, mtime, info)
        return info

    def _is_active(self) -> bool:
        return self.player is not None and self.player.state in {
            "countdown", "playing", "paused",
        }

    def _toggle(self) -> None:
        if self._is_active():
            self._abort()
        else:
            self._start()

    def _start(self) -> None:
        if self._downloading:
            return
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("ยังไม่มีไฟล์", "เลือกไฟล์ MIDI ก่อน")
            return
        try:
            keymap = self._get_keymap()
            midi = self._load_midi(path)
            tempo = float(self.tempo_var.get())
            transpose = int(float(self.transpose_var.get()))
            octave = int(float(self.octave_var.get()))
            countdown = max(0.0, float(self.countdown_var.get()))
            if tempo <= 0:
                raise ValueError("ความเร็วต้องมากกว่า 0")
        except (ValueError, OSError, MidiError) as exc:
            messagebox.showerror("ตั้งค่าไม่ถูกต้อง", str(exc))
            return

        transformed = transform_notes(
            midi.notes,
            keymap,
            tempo=tempo,
            transpose=transpose,
            octave=octave,
            fold=self.fold_var.get(),
        )
        if not transformed.notes:
            messagebox.showerror(
                "เล่นไม่ได้",
                "ไม่มีโน้ตที่ map เข้าคีย์ได้ — ตรวจผังคีย์หรือเปิดการพับโน้ต",
            )
            return

        try:
            backend = self._get_backend()
        except RuntimeError as exc:
            messagebox.showerror("ขาดไลบรารี", str(exc))
            return

        if self.player is not None:
            self.player.stop(wait=True)

        self.player = Player(backend, on_state=lambda state: self.ui_queue.put(("state", state)))
        self.player.play(transformed.notes, countdown=countdown)
        self.progress.configure(maximum=max(self.player.duration, 0.1), value=0)
        self.status_var.set(STATE_LABELS["countdown"] if countdown else STATE_LABELS["playing"])

        total = len(midi.notes)
        folded = transformed.folded
        skipped = transformed.skipped
        self.info_var.set(
            f"{Path(path).name}: โน้ต {total} · เล่นได้ {len(transformed.notes)} · "
            f"พับ {folded} · ข้าม {skipped} · ยาว {midi.duration / tempo:.1f} วินาที · "
            f"ผัง {keymap.name}"
        )
        self._refresh_buttons()

    def _toggle_pause(self) -> None:
        if self.player is None:
            return
        if self.player.state == "paused":
            self.player.resume()
        elif self.player.state == "playing":
            self.player.pause()

    def _abort(self) -> None:
        if self.player is not None:
            self.player.stop(wait=True)
        if self.backend is not None:
            self.backend.release_all()
        self.status_var.set(STATE_LABELS["stopped"])
        self.progress.configure(value=0)
        self._refresh_buttons()

    # ------------------------------------------------------------- events
    def _start_hotkeys(self) -> None:
        try:
            self._hotkeys = Hotkeys(
                on_toggle=lambda: self.ui_queue.put(("hotkey", "toggle")),
                on_pause=lambda: self.ui_queue.put(("hotkey", "pause")),
                on_abort=lambda: self.ui_queue.put(("hotkey", "abort")),
                on_error=lambda message: self.ui_queue.put(("hotkey_error", message)),
            )
            self._hotkeys.start()
        except Exception as exc:
            self.status_var.set(f"global hotkey ไม่ทำงาน: {exc}")
            self._hotkeys = None

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.ui_queue.get_nowait()
                if kind == "state":
                    if value.startswith("error"):
                        self.status_var.set(f"ผิดพลาด: {value[6:].strip()}")
                    else:
                        self.status_var.set(STATE_LABELS.get(value, value))
                    self._refresh_buttons()
                elif kind == "hotkey":
                    if value == "toggle":
                        self._toggle()
                    elif value == "pause":
                        self._toggle_pause()
                    elif value == "abort":
                        self._abort()
                elif kind == "hotkey_error":
                    self.status_var.set(f"hotkey ผิดพลาด: {value}")
                elif kind == "download_status":
                    self.musescore_status_var.set(value)
                    self.status_var.set("กำลังดาวน์โหลด MIDI...")
                elif kind in {"download_done", "download_error"}:
                    self._downloading = False
                    self._refresh_buttons()
                    if kind == "download_done":
                        self.path_var.set(str(value))
                        self._midi_cache = None
                        self.info_var.set("")
                        self.status_var.set("พร้อมเล่น · กด F8 แล้วสลับไป Roblox")
                        self.musescore_status_var.set(f"บันทึกแล้ว: {value} · กด F8 เพื่อเล่น")
                    else:
                        self.status_var.set("ดาวน์โหลดไม่สำเร็จ")
                        self.musescore_status_var.set(f"ดาวน์โหลดไม่สำเร็จ: {value}")
                        messagebox.showerror("ดาวน์โหลด MuseScore ไม่สำเร็จ", value)
        except queue.Empty:
            pass

        if self.player is not None:
            if self.player.duration > 0:
                self.progress.configure(value=min(self.player.progress, self.player.duration))
            self._refresh_buttons()

        self.root.after(80, self._poll)

    def _refresh_buttons(self) -> None:
        active = self._is_active()
        paused = self.player is not None and self.player.state == "paused"
        self.start_button.configure(text="หยุด (F8)" if active else "เริ่มเล่น (F8)")
        self.start_button.configure(state="disabled" if self._downloading else "normal")
        self.download_button.configure(state="disabled" if self._downloading or active else "normal")
        self.pause_button.configure(state="normal" if active else "disabled")
        self.pause_button.configure(text="เล่นต่อ (F9)" if paused else "พัก (F9)")

    # -------------------------------------------------------------- close
    def _on_close(self) -> None:
        if self._downloading:
            messagebox.showwarning("กำลังดาวน์โหลด", "รอให้ดาวน์โหลดเสร็จก่อนปิดโปรแกรม")
            return
        if self.player is not None:
            self.player.stop(wait=False)
        if self.backend is not None:
            self.backend.release_all()
        if self._hotkeys is not None:
            self._hotkeys.stop()
        config.save_settings(
            {
                "midi_path": self.path_var.get(),
                "preset": self._preset_key(),
                "tempo": self.tempo_var.get(),
                "transpose": self.transpose_var.get(),
                "octave": self.octave_var.get(),
                "fold": self.fold_var.get(),
                "countdown": self.countdown_var.get(),
            }
        )
        self.root.destroy()


def run(initial_file: str | None = None) -> None:
    root = tk.Tk()
    app = App(root, initial_file)
    root.mainloop()
    _ = app  # keep reference alive
