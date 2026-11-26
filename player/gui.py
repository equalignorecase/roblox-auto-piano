"""Tkinter GUI for the Roblox MIDI auto player."""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import config, fonts, i18n
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


PRESETS_UI = i18n.PRESETS_BY_LANG["th"]

STATE_LABELS = {
    "idle": "พร้อม",
    "countdown": "นับถอยหลัง... สลับไปที่ Roblox",
    "playing": "กำลังเล่น",
    "paused": "พักอยู่ (F8 เพื่อเล่นต่อ)",
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
        self.lang = settings.get("language", "th")
        if self.lang not in {"th", "en"}:
            self.lang = "th"
        self.lang_var = tk.StringVar(value="English" if self.lang == "en" else "ไทย")

        self.path_var = tk.StringVar(value=initial_file or settings["midi_path"])
        self.song_var = tk.StringVar()
        self._update_song()
        self.path_var.trace_add("write", self._update_song)
        self.musescore_url_var = tk.StringVar()
        self.browser_var = tk.BooleanVar(value=True)
        self.musescore_status_var = tk.StringVar(
            value=self._t("saved_to", path=Path.cwd())
        )
        self.preset_var = tk.StringVar(
            value=i18n.get_preset_label(settings.get("preset", "virtualpiano61"), self.lang)
        )
        self.tempo_var = tk.StringVar(value=settings["tempo"])
        self.tempo_var.trace_add("write", self._on_tempo_change)
        self.transpose_var = tk.StringVar(value=settings["transpose"])
        self.octave_var = tk.StringVar(value=settings["octave"])
        self.countdown_var = tk.StringVar(value=settings["countdown"])
        self.fold_var = tk.BooleanVar(value=bool(settings["fold"]))
        self.status_var = tk.StringVar(value=self._t("state_idle"))
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

    def _t(self, key: str, **kwargs) -> str:
        lang = getattr(self, "lang", "th")
        return i18n.tr(key, lang=lang, **kwargs)

    def _state_label(self, state: str) -> str:
        key = f"state_{state}"
        res = self._t(key)
        if res != key:
            return res
        return STATE_LABELS.get(state, state)

    # ------------------------------------------------------------------ UI
    def _apply_theme(self) -> None:
        fonts.load_bundled_fonts(BUNDLE_DIR, APP_DIR)
        font_family = fonts.get_preferred_font(self.root)

        background = "#151c24"
        surface = "#202a36"
        field = "#101720"
        text = "#eef3f8"
        muted = "#afbdcc"
        border = "#617287"
        accent = "#77dfb5"
        self.root.configure(background=background)

        default_font = tkfont.nametofont("TkDefaultFont", root=self.root)
        if font_family != "TkDefaultFont":
            default_font.configure(family=font_family, size=11)
        else:
            default_font.configure(size=11)

        for named in ("TkTextFont", "TkMenuFont"):
            try:
                fn = tkfont.nametofont(named, root=self.root)
                if font_family != "TkDefaultFont":
                    fn.configure(family=font_family, size=11)
                else:
                    fn.configure(size=11)
            except Exception:
                pass

        try:
            fn = tkfont.nametofont("TkHeadingFont", root=self.root)
            if font_family != "TkDefaultFont":
                fn.configure(family=font_family, size=13, weight="bold")
            else:
                fn.configure(size=13, weight="bold")
        except Exception:
            pass

        family = default_font.actual("family")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=background, foreground=text, font="TkDefaultFont")
        style.configure("TFrame", background=background)
        style.configure("Surface.TFrame", background=surface)
        style.configure("TLabel", background=background, foreground=text, font="TkDefaultFont")
        style.configure("Title.TLabel", font=(family, 14, "bold"))
        style.configure("Song.TLabel", background=surface, font=(family, 12, "bold"))
        style.configure("Muted.TLabel", foreground=muted, font=(family, 10))
        style.configure("SurfaceMuted.TLabel", background=surface, foreground=muted, font=(family, 10))
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
        self.header_topmost_label = ttk.Label(header, text=self._t("topmost"), style="Muted.TLabel")
        self.header_topmost_label.pack(side="right")

        song = ttk.Frame(main, style="Surface.TFrame", padding=12)
        song.grid(row=1, column=0, sticky="ew")
        song.columnconfigure(0, weight=1)
        self.song_label = ttk.Label(song, text=self._t("selected_song"), style="SurfaceMuted.TLabel")
        self.song_label.grid(row=0, column=0, sticky="w")
        ttk.Label(song, textvariable=self.song_var, style="Song.TLabel", wraplength=300).grid(
            row=1, column=0, sticky="w", pady=(4, 0),
        )
        self.browse_button = ttk.Button(song, text=self._t("browse"), command=self._browse)
        self.browse_button.grid(
            row=0, column=1, padx=(12, 0), sticky="ew",
        )
        self.sheet_button = ttk.Button(
            song, text=self._t("btn_export_sheet"), command=self._export_sheet_dialog
        )
        self.sheet_button.grid(
            row=1, column=1, padx=(12, 0), pady=(4, 0), sticky="ew",
        )

        controls = ttk.Frame(main)
        controls.grid(row=2, column=0, sticky="ew", pady=(12, 12))
        controls.columnconfigure(0, weight=3)
        controls.columnconfigure(1, weight=1)
        self.start_button = ttk.Button(controls, text=self._t("play_f8"), style="Accent.TButton", command=self._toggle)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.stop_button = ttk.Button(controls, text=self._t("reset_esc"), command=self._abort)
        self.stop_button.grid(row=0, column=1, sticky="ew")
        self.pause_button = None

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
        download_toggle = ttk.Button(
            sections, text=f"{self._t('musescore_panel')} +",
            command=lambda: self._toggle_panel("download"),
        )
        download_toggle.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        settings_toggle = ttk.Button(
            sections, text=f"{self._t('settings_panel')} +",
            command=lambda: self._toggle_panel("settings"),
        )
        settings_toggle.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        download = ttk.Frame(main, padding=(0, 12, 0, 0))
        download.grid(row=7, column=0, sticky="ew")
        download.columnconfigure(0, weight=1)
        self.musescore_url_label = ttk.Label(download, text=self._t("musescore_url_label"))
        self.musescore_url_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Entry(download, textvariable=self.musescore_url_var).grid(row=1, column=0, sticky="ew")
        self.download_button = ttk.Button(download, text=self._t("download_midi"), command=self._download)
        self.download_button.grid(row=1, column=1, padx=(8, 0))
        self.browser_check = ttk.Checkbutton(
            download, text=self._t("use_browser"), variable=self.browser_var,
        )
        self.browser_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(download, textvariable=self.musescore_status_var, style="Muted.TLabel", wraplength=440).grid(
            row=3, column=0, columnspan=2, sticky="w",
        )

        options = ttk.Frame(main, padding=(0, 12, 0, 0))
        options.grid(row=8, column=0, sticky="ew")
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)

        self.lang_label = ttk.Label(options, text=self._t("language_label"))
        self.lang_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.lang_box = ttk.Combobox(
            options,
            textvariable=self.lang_var,
            values=["ไทย", "English"],
            state="readonly",
        )
        self.lang_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        self.lang_box.bind("<<ComboboxSelected>>", self._on_language_change)

        self.midi_path_label = ttk.Label(options, text=self._t("midi_file_label"))
        self.midi_path_label.grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Entry(options, textvariable=self.path_var).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        self.preset_label = ttk.Label(options, text=self._t("keymap_label"))
        self.preset_label.grid(row=4, column=0, columnspan=2, sticky="w")
        self.preset_box = ttk.Combobox(
            options,
            textvariable=self.preset_var,
            values=[label for label, _ in i18n.PRESETS_BY_LANG[self.lang]],
            state="readonly",
        )
        self.preset_box.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        self.tempo_label = ttk.Label(options, text=self._t("tempo_label"))
        self.tempo_label.grid(row=6, column=0, sticky="w")
        ttk.Spinbox(
            options, from_=0.25, to=4.0, increment=0.05, width=8,
            textvariable=self.tempo_var,
        ).grid(row=7, column=0, sticky="ew", padx=(0, 8), pady=(4, 12))

        self.countdown_label = ttk.Label(options, text=self._t("countdown_label"))
        self.countdown_label.grid(row=6, column=1, sticky="w")
        ttk.Spinbox(
            options, from_=0, to=15, width=8, textvariable=self.countdown_var
        ).grid(row=7, column=1, sticky="ew", pady=(4, 12))

        self.transpose_label = ttk.Label(options, text=self._t("transpose_label"))
        self.transpose_label.grid(row=8, column=0, sticky="w")
        ttk.Spinbox(
            options, from_=-24, to=24, width=8, textvariable=self.transpose_var
        ).grid(row=9, column=0, sticky="ew", padx=(0, 8), pady=(4, 12))

        self.octave_label = ttk.Label(options, text=self._t("octave_label"))
        self.octave_label.grid(row=8, column=1, sticky="w")
        ttk.Spinbox(
            options, from_=-3, to=3, width=8, textvariable=self.octave_var
        ).grid(row=9, column=1, sticky="ew", pady=(4, 12))

        self.fold_check = ttk.Checkbutton(
            options, text=self._t("fold_label"), variable=self.fold_var
        )
        self.fold_check.grid(row=10, column=0, columnspan=2, sticky="w")

        self.active_hint_label = ttk.Label(
            main, text=self._t("roblox_active_hint"),
            style="Muted.TLabel", wraplength=440,
        )
        self.active_hint_label.grid(row=9, column=0, sticky="w", pady=(12, 0))

        self._panels = {
            "download": (download, download_toggle, self._t("musescore_panel")),
            "settings": (options, settings_toggle, self._t("settings_panel")),
        }
        download.grid_remove()
        options.grid_remove()

    def _on_language_change(self, *_args) -> None:
        selected_label = self.lang_var.get()
        new_lang = "en" if selected_label == "English" else "th"
        if new_lang == getattr(self, "lang", "th"):
            return
        self.lang = new_lang

        # Update presets combobox options and value
        current_preset = self._preset_key()
        presets = i18n.PRESETS_BY_LANG[self.lang]
        if hasattr(self, "preset_box"):
            self.preset_box.configure(values=[label for label, _ in presets])
        self.preset_var.set(i18n.get_preset_label(current_preset, self.lang))

        # Update static labels and buttons
        if hasattr(self, "header_topmost_label"):
            self.header_topmost_label.configure(text=self._t("topmost"))
        if hasattr(self, "song_label"):
            self.song_label.configure(text=self._t("selected_song"))
        if hasattr(self, "browse_button"):
            self.browse_button.configure(text=self._t("browse"))
        if hasattr(self, "sheet_button"):
            self.sheet_button.configure(text=self._t("btn_export_sheet"))
        if hasattr(self, "stop_button"):
            self.stop_button.configure(text=self._t("reset_esc"))

        if hasattr(self, "_panels"):
            if "download" in self._panels:
                panel, btn, _ = self._panels["download"]
                self._panels["download"] = (panel, btn, self._t("musescore_panel"))
                symbol = "−" if panel.winfo_manager() else "+"
                btn.configure(text=f"{self._t('musescore_panel')} {symbol}")
            if "settings" in self._panels:
                panel, btn, _ = self._panels["settings"]
                self._panels["settings"] = (panel, btn, self._t("settings_panel"))
                symbol = "−" if panel.winfo_manager() else "+"
                btn.configure(text=f"{self._t('settings_panel')} {symbol}")

        if hasattr(self, "musescore_url_label"):
            self.musescore_url_label.configure(text=self._t("musescore_url_label"))
        if hasattr(self, "download_button"):
            self.download_button.configure(text=self._t("download_midi"))
        if hasattr(self, "browser_check"):
            self.browser_check.configure(text=self._t("use_browser"))

        if hasattr(self, "lang_label"):
            self.lang_label.configure(text=self._t("language_label"))
        if hasattr(self, "midi_path_label"):
            self.midi_path_label.configure(text=self._t("midi_file_label"))
        if hasattr(self, "preset_label"):
            self.preset_label.configure(text=self._t("keymap_label"))
        if hasattr(self, "tempo_label"):
            self.tempo_label.configure(text=self._t("tempo_label"))
        if hasattr(self, "countdown_label"):
            self.countdown_label.configure(text=self._t("countdown_label"))
        if hasattr(self, "transpose_label"):
            self.transpose_label.configure(text=self._t("transpose_label"))
        if hasattr(self, "octave_label"):
            self.octave_label.configure(text=self._t("octave_label"))
        if hasattr(self, "fold_check"):
            self.fold_check.configure(text=self._t("fold_label"))
        if hasattr(self, "active_hint_label"):
            self.active_hint_label.configure(text=self._t("roblox_active_hint"))

        # Update dynamic texts if they are in idle/default state
        if not self.path_var.get().strip():
            self.song_var.set(self._t("no_song"))
        if not self._is_active() and not self._downloading:
            self.status_var.set(self._t("state_idle"))
            self.musescore_status_var.set(self._t("saved_to", path=Path.cwd()))

        self._refresh_buttons()
        self._fit_window()

    def _update_song(self, *_args) -> None:
        path = self.path_var.get().strip()
        self.song_var.set(Path(path).name if path else self._t("no_song"))

    def _fit_window(self, *_args) -> None:
        self.root.update_idletasks()
        self.root.geometry(f"{max(480, self.root.winfo_width())}x{self.root.winfo_reqheight()}")

    def _toggle_panel(self, name: str) -> None:
        selected = self._panels[name][0]
        opening = not selected.winfo_manager()
        for key, item in self._panels.items():
            panel, button = item[0], item[1]
            label = item[2] if len(item) > 2 else name
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
            self.info_var.set(self._t("macos_access_hint"))

    # ------------------------------------------------------------ actions
    def _download(self) -> None:
        if self._downloading or self._is_active():
            return
        url = self.musescore_url_var.get().strip()
        if not url:
            messagebox.showwarning(self._t("no_url_title"), self._t("no_url_msg"))
            return
        self._downloading = True
        self.musescore_status_var.set(self._t("downloading"))
        self.status_var.set(self._t("downloading"))
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
            title=self._t("browse_title"),
            initialdir=str(initial) if initial.is_dir() else str(Path.home()),
            filetypes=[("MIDI", "*.mid *.midi"), (self._t("filetypes_all"), "*.*")],
        )
        if path:
            self.path_var.set(path)
            self.info_var.set("")

    def _export_sheet_dialog(self) -> None:
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning(self._t("no_file_title"), self._t("no_file_msg"))
            return
        try:
            keymap = self._get_keymap()
            midi = self._load_midi(path)
            tempo = float(self.tempo_var.get())
            transpose = int(float(self.transpose_var.get()))
            octave = int(float(self.octave_var.get()))
            if tempo <= 0:
                raise ValueError(self._t("tempo_invalid_msg"))
        except (ValueError, OSError, MidiError) as exc:
            messagebox.showerror(self._t("invalid_settings_title"), str(exc))
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
            messagebox.showerror(self._t("cannot_play_title"), self._t("no_mapped_notes_msg"))
            return

        from .sheet import notes_to_sheet

        sheet_text = notes_to_sheet(transformed.notes)

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(sheet_text)
        except Exception:
            pass

        dlg = tk.Toplevel(self.root)
        dlg.title(f"{self._t('sheet_window_title')} - {Path(path).name}")
        dlg.attributes("-topmost", True)
        dlg.configure(background="#151c24")
        dlg.minsize(480, 360)

        top_frame = ttk.Frame(dlg, padding=12)
        top_frame.pack(fill="both", expand=True)

        ttk.Label(
            top_frame,
            text=self._t("sheet_copied_hint"),
            style="Muted.TLabel",
            wraplength=460,
        ).pack(anchor="w", pady=(0, 8))

        text_box = tk.Text(
            top_frame,
            wrap="word",
            background="#101720",
            foreground="#eef3f8",
            insertbackground="#eef3f8",
            relief="flat",
            font=("Consolas", 11),
            padx=8,
            pady=8,
        )
        text_box.insert("1.0", sheet_text)
        text_box.pack(fill="both", expand=True)

        btn_bar = ttk.Frame(top_frame)
        btn_bar.pack(fill="x", pady=(8, 0))

        def copy_all():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text_box.get("1.0", "end-1c"))
                messagebox.showinfo(self._t("sheet_window_title"), self._t("sheet_copied_alert"), parent=dlg)
            except Exception:
                pass

        def save_file():
            default_name = f"{Path(path).stem}_sheet.txt"
            target = filedialog.asksaveasfilename(
                title=self._t("sheet_save_title"),
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=[("Text file", "*.txt"), (self._t("filetypes_all"), "*.*")],
                parent=dlg,
            )
            if target:
                Path(target).write_text(text_box.get("1.0", "end-1c"), encoding="utf-8")
                messagebox.showinfo(
                    self._t("sheet_window_title"),
                    self._t("sheet_file_saved", path=target),
                    parent=dlg,
                )

        ttk.Button(btn_bar, text=self._t("sheet_copy_again"), command=copy_all).pack(side="left", padx=(0, 6))
        ttk.Button(btn_bar, text=self._t("sheet_save_file"), command=save_file).pack(side="left")
        ttk.Button(btn_bar, text=self._t("sheet_close"), command=dlg.destroy).pack(side="right")

    def _preset_key(self) -> str:
        return i18n.get_preset_key(self.preset_var.get())

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
        if self.player is None or self.player.state in {"idle", "stopped", "finished"}:
            self._start()
        elif self.player.state == "paused":
            self.player.resume()
        elif self.player.state in {"playing", "countdown"}:
            self.player.pause()

    def _start(self) -> None:
        if self._downloading:
            return
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning(self._t("no_file_title"), self._t("no_file_msg"))
            return
        try:
            keymap = self._get_keymap()
            midi = self._load_midi(path)
            tempo = float(self.tempo_var.get())
            transpose = int(float(self.transpose_var.get()))
            octave = int(float(self.octave_var.get()))
            countdown = max(0.0, float(self.countdown_var.get()))
            if tempo <= 0:
                raise ValueError(self._t("tempo_invalid_msg"))
        except (ValueError, OSError, MidiError) as exc:
            messagebox.showerror(self._t("invalid_settings_title"), str(exc))
            return

        transformed = transform_notes(
            midi.notes,
            keymap,
            tempo=1.0,
            transpose=transpose,
            octave=octave,
            fold=self.fold_var.get(),
        )
        if not transformed.notes:
            messagebox.showerror(
                self._t("cannot_play_title"),
                self._t("no_mapped_notes_msg"),
            )
            return

        try:
            backend = self._get_backend()
        except RuntimeError as exc:
            messagebox.showerror(self._t("missing_library_title"), str(exc))
            return

        if self.player is not None:
            self.player.stop(wait=True)

        self.player = Player(backend, on_state=lambda state: self.ui_queue.put(("state", state)))
        self.player.play(transformed.notes, countdown=countdown, tempo=tempo)
        self.progress.configure(maximum=max(self.player.duration, 0.1), value=0)
        self.status_var.set(self._state_label("countdown") if countdown else self._state_label("playing"))

        total = len(midi.notes)
        folded = transformed.folded
        skipped = transformed.skipped
        self.info_var.set(
            self._t(
                "info_stats",
                name=Path(path).name,
                total=total,
                playable=len(transformed.notes),
                folded=folded,
                skipped=skipped,
                duration=midi.duration / tempo,
                keymap=keymap.name,
            )
        )
        self._refresh_buttons()

    def _toggle_pause(self) -> None:
        self._toggle()

    def _abort(self) -> None:
        if self.player is not None:
            self.player.stop(wait=True)
        if self.backend is not None:
            self.backend.release_all()
        self.status_var.set(self._state_label("stopped"))
        self.progress.configure(value=0)
        self._refresh_buttons()

    # ------------------------------------------------------------- events
    def _adjust_speed(self, delta: float) -> None:
        try:
            curr = float(self.tempo_var.get())
        except (ValueError, TypeError):
            curr = 1.0
        new_speed = round(max(0.25, min(4.0, curr + delta)), 2)
        self.tempo_var.set(f"{new_speed:.2f}")

    def _on_tempo_change(self, *_args) -> None:
        try:
            val = float(self.tempo_var.get())
            if val <= 0:
                return
            if self.player is not None:
                self.player.set_tempo(val)
                if self._is_active():
                    state_text = self._state_label(self.player.state)
                    self.status_var.set(f"{state_text} · {self._t('speed_status')}: {val:.2f}x")
        except (ValueError, TypeError):
            pass

    def _start_hotkeys(self) -> None:
        try:
            self._hotkeys = Hotkeys(
                on_toggle=lambda: self.ui_queue.put(("hotkey", "toggle")),
                on_pause=lambda: self.ui_queue.put(("hotkey", "pause")),
                on_abort=lambda: self.ui_queue.put(("hotkey", "abort")),
                on_speed_up=lambda: self.ui_queue.put(("hotkey", "speed_up")),
                on_speed_down=lambda: self.ui_queue.put(("hotkey", "speed_down")),
                on_error=lambda message: self.ui_queue.put(("hotkey_error", message)),
            )
            self._hotkeys.start()
        except Exception as exc:
            self.status_var.set(self._t("hotkey_failed", error=exc))
            self._hotkeys = None

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.ui_queue.get_nowait()
                if kind == "state":
                    if value.startswith("error"):
                        self.status_var.set(self._t("error_prefix", error=value[6:].strip()))
                    else:
                        self.status_var.set(self._state_label(value))
                    self._refresh_buttons()
                elif kind == "hotkey":
                    if value == "toggle":
                        self._toggle()
                    elif value == "pause":
                        self._toggle_pause()
                    elif value == "abort":
                        self._abort()
                    elif value == "speed_up":
                        self._adjust_speed(0.10)
                    elif value == "speed_down":
                        self._adjust_speed(-0.10)
                elif kind == "hotkey_error":
                    self.status_var.set(self._t("hotkey_error", error=value))
                elif kind == "download_status":
                    self.musescore_status_var.set(value)
                    self.status_var.set(self._t("downloading"))
                elif kind in {"download_done", "download_error"}:
                    self._downloading = False
                    self._refresh_buttons()
                    if kind == "download_done":
                        self.path_var.set(str(value))
                        self._midi_cache = None
                        self.info_var.set("")
                        self.status_var.set(self._t("download_done_status"))
                        self.musescore_status_var.set(self._t("download_saved", path=value))
                    else:
                        self.status_var.set(self._t("download_failed_short"))
                        self.musescore_status_var.set(self._t("download_failed_detail", error=value))
                        messagebox.showerror(self._t("download_failed_title"), value)
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
        playing = self.player is not None and self.player.state in {"playing", "countdown"}
        if hasattr(self, "start_button"):
            if paused:
                btn_text = self._t("resume_f8")
            elif playing:
                btn_text = self._t("pause_f8")
            else:
                btn_text = self._t("play_f8")
            self.start_button.configure(text=btn_text)
            self.start_button.configure(state="disabled" if self._downloading else "normal")
        if hasattr(self, "stop_button"):
            self.stop_button.configure(text=self._t("reset_esc"))
            self.stop_button.configure(state="normal" if active else "disabled")
        if hasattr(self, "download_button"):
            self.download_button.configure(state="disabled" if self._downloading or active else "normal")
        if hasattr(self, "pause_button") and self.pause_button is not None:
            self.pause_button.configure(state="normal" if active else "disabled")
            self.pause_button.configure(text=self._t("resume_f8") if paused else self._t("pause_f8"))

    # -------------------------------------------------------------- close
    def _on_close(self) -> None:
        if self._downloading:
            messagebox.showwarning(
                self._t("closing_download_warning_title"),
                self._t("closing_download_warning_msg"),
            )
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
                "language": getattr(self, "lang", "th"),
            }
        )
        self.root.destroy()


def run(initial_file: str | None = None) -> None:
    root = tk.Tk()
    app = App(root, initial_file)
    root.mainloop()
    _ = app  # keep reference alive
