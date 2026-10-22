"""Responsive Windows chess coach. Observation and engine run independently."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from copy import deepcopy
from time import perf_counter
import ctypes
import json
import tkinter as tk
from tkinter import ttk, filedialog

import chess
import chess.pgn
import cv2
import numpy as np
from PIL import ImageGrab

from .board import PIECE_NAME_TO_SYMBOL, square_at, placement_fen
from .config import load_settings, STRENGTHS
from .detection import detect_board
from .engine import AnalysisService
from .overlay import ShadowOverlay
from .tracker import PositionTracker, reconcile_opening
from .vision import TemplateRecognizer, guarded_screenshot
from .windowing import foreground, rect, board_visible
from .win32 import screenshot
from .hotkeys import GlobalHotkeys
from .adaptive import resolve_position, RecoveryGate
from .midgame import MidgameBootstrap, orient_midgame
from .images import write_image


AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
PROFILES = {"Cepat": (80, .18), "Seimbang": (120, .45), "Mendalam": (180, 1.2)}


def frame_changed(old, new):
    return old is None or old.shape != new.shape or bool(np.mean(
        np.max(np.abs(old.astype(np.int16)-new.astype(np.int16)), axis=2) > 20) > .001)


class Coach:
    def __init__(self, config):
        self.path = Path(config).resolve()
        self.settings = load_settings(self.path)
        self.root = tk.Tk()
        self.root.title("ChessLab Coach • Live")
        self.root.geometry("700x880")
        self.root.minsize(650, 860)
        self.running = self.closed = False
        self.license_manager = None
        self.license_controller = None
        self.generation = 0
        self.future = self.engine_future = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision")
        self.scan_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="board-search")
        self.scan_future = None
        self.pending_layout = None
        self.recovery = RecoveryGate()
        self.service = AnalysisService(self.settings.stockfish_path)
        self.tracker = None
        self.target = self.target_rect = None
        self.last = None
        self.count = 0
        self.active_board = None
        self.advice = None
        self.position_ready = False
        self.previous_frame = None
        self.engine_token = None
        self.overlay_enabled = True
        self.force_scan = False
        self.last_scan = perf_counter()
        self.last_visual_change = 0.0
        self.failures = 0
        self.persist_layout = False
        self.mode = tk.StringVar(value="Cepat")
        self.strength = tk.StringVar(value=self.settings.engine_strength)
        self.human_style = tk.BooleanVar(value=self.settings.human_style)
        self.adaptive_timing = tk.BooleanVar(value=self.settings.adaptive_timing)
        self.startup_turn = tk.StringVar(value="auto")
        self.midgame = MidgameBootstrap()
        self.fen = tk.StringVar(value=chess.STARTING_FEN)
        self.colour = tk.StringVar(value=self.settings.player_colour)
        self.orientation = tk.StringVar(value=self.settings.orientation_mode)
        self.status = tk.StringVar(value="Pilih FEN yang sesuai. Pelajari hanya jika tema/batas papan berubah.")
        self.suggestion = tk.StringVar(value="Siap memantau")
        self.variation = tk.StringVar(value="")
        self.metrics = tk.StringVar(value="Baca: —   Tangkap: —   Stockfish: —")
        self.opacity = tk.DoubleVar(value=self.settings.marker_opacity*100)
        self.marker_size = tk.IntVar(value=self.settings.marker_size)
        self.overlay_style = tk.StringVar(value=self.settings.overlay_style)
        self.overlay_hint = tk.StringVar()
        self.history = tk.StringVar(value="Belum ada langkah terekam")
        body = ttk.Frame(self.root, padding=18); body.pack(fill="both", expand=True)
        ttk.Label(body, text="ChessLab Coach", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(body, text="Latihan bot / lokal • Rekomendasi langsung • Gerakan manual").pack(anchor="w", pady=(0,12))
        from .licensing.ui import install_license_ui
        install_license_ui(self, body)
        self.root.geometry("700x1030")
        self.root.minsize(650, 980)
        row = ttk.Frame(body); row.pack(fill="x")
        for label, variable, values in [("Anda", self.colour, ("auto", "white", "black")),
                                         ("Di bawah", self.orientation, ("auto", "white", "black")),
                                         ("Respons", self.mode, tuple(PROFILES))]:
            ttk.Label(row, text=label).pack(side="left")
            box = ttk.Combobox(row, textvariable=variable, values=values, state="readonly", width=9)
            box.pack(side="left", padx=(4,10))
            if variable is self.mode:
                box.bind("<<ComboboxSelected>>", lambda _: self._mode_changed())
            elif variable is self.colour:
                box.bind("<<ComboboxSelected>>", lambda _: self._colour_changed())
            elif variable is self.orientation:
                box.bind("<<ComboboxSelected>>", lambda _: self._orientation_changed())
        strength_row = ttk.Frame(body); strength_row.pack(fill="x", pady=(8, 0))
        ttk.Label(strength_row, text="Kecerdasan").pack(side="left")
        strength_box = ttk.Combobox(strength_row, textvariable=self.strength,
                                   values=STRENGTHS, state="readonly", width=14)
        strength_box.pack(side="left", padx=8)
        strength_box.bind("<<ComboboxSelected>>", lambda _: self._strength_changed())
        ttk.Label(strength_row, text="Human: variasi langkah kuat, toleransi hingga 0,35 pion", wraplength=340).pack(side="left")
        timing_row = ttk.Frame(body); timing_row.pack(fill="x", pady=(4, 0))
        ttk.Label(timing_row, text="Waktu adaptif (mudah cepat, rumit lebih lama)").pack(side="left")
        self.adaptive_timing_buttons = []
        for label, value in (("ON", True), ("OFF", False)):
            button = ttk.Radiobutton(timing_row, text=label, value=value,
                                     variable=self.adaptive_timing, command=self._adaptive_timing_changed)
            button.pack(side="left", padx=8)
            self.adaptive_timing_buttons.append(button)
        human_row = ttk.Frame(body); human_row.pack(fill="x", pady=(8, 0))
        ttk.Label(human_row, text="Gaya setara (mode selain Human)").pack(side="left")
        self.human_style_buttons = []
        for label, value in (("ON", True), ("OFF", False)):
            button = ttk.Radiobutton(human_row, text=label, value=value, variable=self.human_style,
                                     command=self._human_style_changed)
            button.pack(side="left", padx=8)
            self.human_style_buttons.append(button)
        self._update_human_controls()
        ttk.Label(body, text="Memilih alternatif setara; analisis bisa lebih lama. Mode kecerdasan tetap berlaku.",
                  wraplength=630).pack(anchor="w", pady=(4, 0))
        join_row = ttk.Frame(body); join_row.pack(fill="x", pady=(8, 0))
        ttk.Label(join_row, text="Giliran awal").pack(side="left")
        turn_box = ttk.Combobox(join_row, textvariable=self.startup_turn,
                               values=("auto", "white", "black"), state="readonly", width=9)
        turn_box.pack(side="left", padx=8)
        turn_box.bind("<<ComboboxSelected>>", lambda _: self.join_midgame())
        ttk.Button(join_row, text="Baca posisi sekarang", command=self.join_midgame).pack(side="left")
        ttk.Label(body, text="Tengah match: Auto menunggu satu langkah; pilih giliran untuk langsung analisis.\nTanpa FEN lengkap, riwayat lama dan hak rokade tidak diketahui.",
                  wraplength=630).pack(anchor="w", pady=(4, 0))
        ttk.Label(body, text="FEN opsional untuk posisi lengkap (termasuk giliran dan hak rokade):").pack(anchor="w", pady=(12,3))
        ttk.Entry(body, textvariable=self.fen).pack(fill="x")
        row = ttk.Frame(body); row.pack(fill="x", pady=5)
        ttk.Button(row, text="Posisi awal", command=lambda: self.set_position(chess.STARTING_FEN)).pack(side="left")
        ttk.Button(row, text="Setelah e4 e5", command=lambda: self.set_position(AFTER_E4_E5)).pack(side="left", padx=5)
        ttk.Button(row, text="Setelah 1.e4", command=lambda: self.set_position(AFTER_E4)).pack(side="left", padx=5)
        ttk.Button(row, text="Salin FEN", command=self.copy_fen).pack(side="left")
        ttk.Button(row, text="Simpan PGN", command=self.export_pgn).pack(side="left", padx=5)
        row = ttk.Frame(body); row.pack(fill="x", pady=10)
        ttk.Button(row, text="Deteksi & pelajari (3 dtk)", command=self.prepare).pack(side="left")
        ttk.Button(row, text="Mulai / lanjut (3 dtk)", command=self.start).pack(side="left", padx=6)
        ttk.Button(row, text="Jeda", command=self.pause).pack(side="left")
        ttk.Button(row, text="Cari papan", command=self.request_rescan).pack(side="left", padx=5)
        ttk.Label(body, textvariable=self.suggestion, font=("Segoe UI",12), foreground="#526273").pack(anchor="w", pady=(8,3))
        ttk.Label(body, textvariable=self.variation, wraplength=595).pack(anchor="w")
        ttk.Label(body, textvariable=self.metrics, foreground="#526273").pack(anchor="w", pady=8)
        ttk.Label(body, textvariable=self.status, wraplength=595).pack(anchor="w")
        ttk.Label(body, textvariable=self.history, wraplength=595).pack(anchor="w", pady=8)
        style_row = ttk.Frame(body); style_row.pack(fill="x", pady=(0, 6))
        ttk.Label(style_row, text="Tampilan rekomendasi:").pack(side="left", padx=(0, 8))
        for label, value in (("Bayangan", "shadow"), ("Titik", "dots")):
            ttk.Radiobutton(style_row, text=label, value=value, variable=self.overlay_style,
                            command=self._overlay_style_changed).pack(side="left", padx=6)
        row = ttk.Frame(body); row.pack(fill="x")
        ttk.Label(row, text="Ukuran titik (px)").pack(side="left")
        size_box = ttk.Combobox(row, textvariable=self.marker_size, values=tuple(range(3, 11)),
                               state="readonly", width=3)
        size_box.pack(side="left", padx=6)
        self.marker_size_box = size_box
        size_box.bind("<<ComboboxSelected>>", self._save_marker_options)
        ttk.Label(row, text="Kejelasan").pack(side="left")
        opacity_scale = ttk.Scale(row, from_=15, to=80, variable=self.opacity, command=self._opacity_changed)
        opacity_scale.pack(side="left", fill="x", expand=True, padx=10)
        opacity_scale.bind("<ButtonRelease-1>", self._save_marker_options)
        opacity_scale.bind("<KeyRelease>", self._save_marker_options)
        ttk.Button(row, text="Minimalkan panel", command=self.root.iconify).pack(side="left")
        ttk.Label(body, textvariable=self.overlay_hint, wraplength=595).pack(anchor="w", pady=8)
        self.overlay = ShadowOverlay(self.root, self.settings.marker_size, self.settings.marker_opacity,
                                     self.settings.overlay_style)
        self._update_overlay_controls()
        self.shortcuts_status = tk.StringVar(value="Ctrl+Alt+P: jeda/lanjut   •   Ctrl+Alt+H: penanda   •   Ctrl+Alt+R: cari papan")
        ttk.Label(body, textvariable=self.shortcuts_status, wraplength=610).pack(anchor="w", pady=5)
        self.root.update_idletasks()
        self.coach_hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _: self.pause())
        self.root.after(20, self._engine_tick)
        self.hotkeys = GlobalHotkeys()
        self.root.after(40, self._hotkey_tick)
        if self.settings.auto_start:
            self.root.after(250, self._autostart)

    def _autostart(self):
        # A manual pause/prepare before this callback takes precedence.
        if not self.closed and not self.running and self.generation == 0:
            self.start(automatic=True)

    def _license_changed(self, entitled, busy, message):
        """Aktivasi pertama melanjutkan autostart yang sebelumnya ditolak lisensi."""
        was_entitled = getattr(self, "_license_was_entitled", False)
        self._license_was_entitled = entitled
        if not entitled:
            if self.running:
                self.pause()
                self.advice = None
                self.variation.set("")
                self.suggestion.set("Lisensi tidak aktif")
            self.status.set(message)
        elif not was_entitled and self.settings.auto_start:
            # Guard generation di _autostart mempertahankan Jeda/Persiapan manual.
            self.root.after(0, self._autostart)

    def _hotkey_tick(self):
        if self.closed:
            return
        for action, message in self.hotkeys.poll():
            if action == "pause":
                self.pause() if self.running else self.start()
            elif action == "shadow":
                self.overlay_enabled = not self.overlay_enabled
                if not self.overlay_enabled:
                    self.overlay.hide()
                else:
                    self._show_advice()
            elif action == "rescan":
                self.request_rescan()
            elif action == "error":
                self.shortcuts_status.set(message)
        self.root.after(40, self._hotkey_tick)

    def request_rescan(self):
        self.force_scan = True
        self.position_ready = False
        self.overlay.hide()
        if not self.running:
            self.start()
        self.status.set("Pencarian papan dijadwalkan. Aktifkan jendela papan.")

    def _save_layout(self):
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["board"] = asdict(self.settings.board)
        self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        self.persist_layout = False
        self.last_scan = perf_counter()

    def _archive_game(self):
        if self.active_board is None or not self.active_board.move_stack:
            return
        directory = self.settings.runtime_dir / "games"
        directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("game-%Y%m%d-%H%M%S-") + uuid4().hex[:8] + ".pgn"
        game = chess.pgn.Game.from_board(self.active_board)
        game.headers["Event"] = "ChessLab bot practice"
        (directory / filename).write_text(str(game)+"\n", encoding="utf-8")

    def _opacity_changed(self, value):
        if hasattr(self, "overlay"):
            self.overlay.set_opacity(float(value)/100)

    def _update_overlay_controls(self):
        dots = self.overlay_style.get() == "dots"
        self.marker_size_box.configure(state="readonly" if dots else "disabled")
        self.overlay_hint.set(
            "Sudut kanan atas petak: lingkaran kosong = asal, titik penuh = tujuan. Panel boleh diminimalkan."
            if dots else "Bayangan merah: lebih samar = petak asal, lebih kuat = petak tujuan. Panel boleh diminimalkan.")

    def _overlay_style_changed(self):
        style = self.overlay_style.get()
        self.overlay.set_style(style)
        self._update_overlay_controls()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            raw["overlay_style"] = style
            self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            self.settings = replace(self.settings, overlay_style=style)
        except (OSError, ValueError) as exc:
            self.status.set(f"Pilihan tampilan belum tersimpan: {exc}")

    def _save_marker_options(self, event=None):
        size = self.marker_size.get()
        opacity = round(self.opacity.get()/100, 3)
        self.overlay.set_size(size)
        self.overlay.set_opacity(opacity)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            raw.update(marker_size=size, marker_opacity=opacity)
            self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            self.settings = replace(self.settings, marker_size=size, marker_opacity=opacity)
        except (OSError, ValueError) as exc:
            self.status.set(f"Pengaturan penanda belum tersimpan: {exc}")

    def _mode_changed(self):
        self.advice = None
        self.engine_token = None
        self.overlay.hide()

    def _strength_changed(self):
        selected = self.strength.get()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["engine_strength"] = selected
        self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        self.settings = replace(self.settings, engine_strength=selected)
        self._update_human_controls()
        self._mode_changed()
        self.variation.set("")
        self.suggestion.set("Menghitung ulang…" if self.running else "Dijeda")
        self.status.set(f"Kecerdasan: {selected}. Rekomendasi mengikuti langkah yang Anda mainkan.")
        if (self.running and self.position_ready and self.active_board is not None
                and self.active_board.turn == self.my_colour and not self.active_board.is_game_over()):
            self._request_advice(self.active_board)

    def _update_human_controls(self):
        for button in getattr(self, "human_style_buttons", ()):
            button.configure(state="disabled" if self.settings.engine_strength == "Human" else "normal")

    def _human_style_changed(self):
        selected = self.human_style.get()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            raw["human_style"] = selected
            self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            self.human_style.set(self.settings.human_style)
            self.status.set(f"Gaya manusiawi belum tersimpan: {exc}")
            return
        self.settings = replace(self.settings, human_style=selected)
        self._mode_changed()
        self.variation.set("")
        self.suggestion.set("Menghitung ulang…" if self.running else "Dijeda")
        self.status.set("Gaya manusiawi: " + ("ON — alternatif dengan evaluasi setara." if selected else "OFF — rekomendasi biasa."))
        if (self.running and self.position_ready and self.active_board is not None
                and self.active_board.turn == self.my_colour and not self.active_board.is_game_over()):
            self._request_advice(self.active_board)

    def _adaptive_timing_changed(self):
        selected = self.adaptive_timing.get()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            raw["adaptive_timing"] = selected
            self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            self.adaptive_timing.set(self.settings.adaptive_timing)
            self.status.set(f"Waktu adaptif belum tersimpan: {exc}")
            return
        self.settings = replace(self.settings, adaptive_timing=selected)
        self._mode_changed()
        self.variation.set("")
        self.suggestion.set("Menghitung ulang..." if self.running else "Dijeda")
        self.status.set("Waktu adaptif: " + ("ON" if selected else "OFF"))
        if (self.running and self.position_ready and self.active_board is not None
                and self.active_board.turn == self.my_colour and not self.active_board.is_game_over()):
            self._request_advice(self.active_board)

    def _colour_changed(self):
        self.my_colour = self._selected_colour()
        self.advice = self.engine_token = None
        self.overlay.hide()
        self.variation.set("")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["player_colour"] = self.colour.get()
        self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def _selected_colour(self):
        colour = self.colour.get()
        return (self.settings.board.orientation if colour == "auto" else colour) == "white"

    def _orientation_changed(self):
        selected = self.orientation.get()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["orientation_mode"] = selected
        self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        # Apply between captures so a vision worker never sees half an update.
        if self.running:
            orientation = self.settings.board.orientation if selected == "auto" else selected
            box = replace(self.settings.board, orientation=orientation)
            self.pending_layout = (box, self.target_rect, self.settings.board)
            self.position_ready = False
            self.overlay.hide()

    def _training_orientation(self, crop, box, board):
        """Use trusted piece templates to avoid learning a flipped, mislabelled set."""
        try:
            recognizer = TemplateRecognizer(self.settings.templates_dir, self.settings.min_template_score)
        except FileNotFoundError as exc:
            raise ValueError("Auto belum memiliki template. Pilih Di bawah: white/black untuk belajar pertama kali, lalu gunakan auto.") from exc
        matches = []
        for orientation in ("white", "black"):
            placement, details = recognizer.recognize(crop, replace(box, orientation=orientation))
            tracker = PositionTracker(board.fen(), allow_opening=True)
            if (all(d.score >= self.settings.min_template_score for d in details.values())
                    and tracker.observe(placement)):
                matches.append(orientation)
        if len(matches) != 1:
            raise ValueError("Untuk match berjalan, gunakan Baca posisi sekarang. Untuk belajar tema baru, sesuaikan FEN dan pilih Di bawah: white/black.")
        return matches[0]

    def set_position(self, fen):
        self.pause(); self.fen.set(fen)

    def join_midgame(self):
        """Explicitly discard the old session and read the visible position."""
        self.pause()
        if self.future and not self.future.done():
            self.status.set("Pembacaan sedang selesai; klik Baca posisi sekarang lagi sebentar.")
            return
        self._archive_game()
        self.tracker = None
        self.fen.set(chess.STARTING_FEN)
        self.midgame = MidgameBootstrap()
        self.start(automatic=True)

    def copy_fen(self):
        self.root.clipboard_clear(); self.root.clipboard_append(self.fen.get())
        self.status.set("FEN disalin.")

    def export_pgn(self):
        if self.active_board is None:
            self.status.set("Belum ada posisi tersinkron untuk diekspor."); return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".pgn", filetypes=[("Chess PGN", "*.pgn")])
        if path:
            game = chess.pgn.Game.from_board(self.active_board)
            game.headers["Event"] = "ChessLab bot practice"
            Path(path).write_text(str(game)+"\n", encoding="utf-8")
            self.status.set("Riwayat sesi tersimpan sebagai PGN.")

    def pause(self):
        self.running = False
        self.pending_layout = None
        self.generation += 1
        self.position_ready = False
        self.overlay.hide()
        self.status.set("Dijeda. FEN terakhir dipertahankan; lanjutkan jika papan belum berubah.")
        self.suggestion.set("Dijeda")

    def prepare(self):
        self.pause()
        if self.future and not self.future.done():
            self.status.set("Pembacaan sedang selesai; coba lagi sebentar."); return
        try:
            board = chess.Board(self.fen.get().strip())
            if not board.is_valid():
                raise ValueError("FEN tidak valid")
        except ValueError as exc:
            self.status.set(str(exc)); return
        token, orientation = self.generation, self.orientation.get()
        self.status.set("Dalam 3 detik Alt+Tab ke papan. Jangan melabeli posisi berjalan sebagai posisi awal.")
        self.root.after(3000, lambda: self._prepare_capture(token, board, orientation))

    def _prepare_capture(self, token, board, orientation):
        if token != self.generation or self.closed:
            return
        try:
            image = np.asarray(ImageGrab.grab().convert("RGB"))
            box = detect_board(image, self.settings.board.orientation if orientation == "auto" else orientation)
            crop = image[box.top:box.bottom, box.left:box.right]
            if orientation == "auto":
                orientation = self._training_orientation(crop, box, board)
                box = replace(box, orientation=orientation)
            names = {symbol: name for name, symbol in PIECE_NAME_TO_SYMBOL.items()}
            tiles = {}
            for row in range(8):
                for col in range(8):
                    square = square_at(row, col, orientation)
                    tiles[square] = crop[round(row*crop.shape[0]/8):round((row+1)*crop.shape[0]/8),
                                         round(col*crop.shape[1]/8):round((col+1)*crop.shape[1]/8)]
            occupied = {s for s, tile in tiles.items() if TemplateRecognizer._features(tile)[1] >= 45}
            board = reconcile_opening(board, occupied)
            samples = []
            for row in range(8):
                for col in range(8):
                    square = square_at(row, col, orientation)
                    piece = board.piece_at(square)
                    name = names[piece.symbol()] if piece else "empty"
                    tile = crop[round(row*crop.shape[0]/8):round((row+1)*crop.shape[0]/8),
                                round(col*crop.shape[1]/8):round((col+1)*crop.shape[1]/8)]
                    edges = TemplateRecognizer._features(tile)[1]
                    if (piece and edges < 45) or (not piece and edges >= 80):
                        raise ValueError(f"FEN tidak cocok dengan petak {chess.square_name(square)}. Sesuaikan FEN; template lama dipertahankan.")
                    samples.append((name, square, tile))
            profiles = self.path.parent / "templates"; profiles.mkdir(parents=True, exist_ok=True)
            # Persistent profiles must inherit project permissions. mkdtemp()
            # restricts Windows access to its creator, which may be a sandbox user.
            profile = profiles / f"coach-{uuid4().hex}"
            profile.mkdir()
            for name, square, tile in samples:
                folder = profile / name; folder.mkdir(parents=True, exist_ok=True)
                if not write_image(folder / f"{chess.square_name(square)}.png", cv2.cvtColor(tile, cv2.COLOR_RGB2BGR)):
                    raise OSError("Template gagal disimpan")
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            raw.update(board=asdict(box), templates_dir=str(profile.relative_to(self.path.parent)))
            self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            self.settings = load_settings(self.path)
            self.fen.set(board.fen())
            self.tracker = PositionTracker(board.fen(), allow_opening=True)
            self.target = foreground(); self.target_rect = rect(self.target)
            turn = "putih" if board.turn else "hitam"
            self.status.set(f"Papan dan template siap. Giliran {turn}; FEN sudah disesuaikan. Klik Mulai.")
        except Exception as exc:
            self.status.set(f"Persiapan gagal: {exc}")

    def start(self, automatic=False):
        if not self._license_allowed():
            self.status.set("Aktivasi atau perpanjang lisensi untuk memulai analisis.")
            if hasattr(self, "license_panel") and not automatic:
                self.license_panel.open_activation()
            return
        self.pause()
        if self.future and not self.future.done():
            self.status.set("Pembacaan sedang selesai; coba Mulai sebentar lagi."); return
        try:
            self.settings = load_settings(self.path)
            self.settings = replace(self.settings, startup_turn=self.startup_turn.get())
            self.recognizer = TemplateRecognizer(self.settings.templates_dir, self.settings.min_template_score)
            entered = self.fen.get().strip()
            # Preserve history if resuming precisely the last accepted state.
            if self.tracker is None or self.tracker.board.fen() != entered:
                self.tracker = PositionTracker(entered, allow_opening=True)
                self.tracker.allow_midgame = entered == chess.STARTING_FEN
                self.midgame = MidgameBootstrap()
            if self.orientation.get() != "auto" and self.orientation.get() != self.settings.board.orientation:
                self.settings = replace(self.settings, board=replace(
                    self.settings.board, orientation=self.orientation.get()))
                self.persist_layout = True
            if self.service.executable != self.settings.stockfish_path:
                self.service.close(); self.service = AnalysisService(self.settings.stockfish_path)
        except Exception as exc:
            self.status.set(str(exc)); return
        self.my_colour = self._selected_colour()
        self.last, self.count, self.advice, self.previous_frame = None, 0, None, None
        self.active_board = None
        self.failures = 0
        self.recovery = RecoveryGate()
        self.running = True
        token = self.generation
        if automatic:
            self.status.set("Mencari papan otomatis. Tampilkan dan aktifkan jendela papan.")
            self._auto_find(token)
            return
        self.status.set("Dalam 3 detik Alt+Tab ke papan. Panel boleh digunakan setelah pemantauan dimulai.")
        self.root.after(3000, lambda: self._begin(token))

    def _auto_find(self, token):
        if self.closed or not self.running or token != self.generation:
            return
        target = foreground()
        target_rect = rect(target)
        if not target or target == self.coach_hwnd or not target_rect:
            self.status.set("Menunggu papan. Aktifkan jendela papan; Coach akan mulai otomatis.")
            self.root.after(1000, lambda: self._auto_find(token))
            return
        future = self.scan_pool.submit(
            self._locate_snapshot, self.settings, deepcopy(self.tracker), target_rect)
        self.root.after(25, lambda: self._auto_found(token, target, target_rect, future))

    def _auto_found(self, token, target, target_rect, future):
        if self.closed or not self.running or token != self.generation:
            return
        if not future.done():
            self.root.after(25, lambda: self._auto_found(token, target, target_rect, future))
            return
        try:
            box = future.result()
            if foreground() != target or rect(target) != target_rect:
                raise ValueError("Jendela berubah selama pencarian")
        except Exception as exc:
            self.suggestion.set("Menunggu papan dan template yang cocok")
            self.status.set(f"Menunggu papan yang dikenali: {exc}")
            self.root.after(1000, lambda: self._auto_find(token))
            return
        self.target, self.target_rect = target, target_rect
        self.settings = replace(self.settings, board=box)
        if self.orientation.get() != "auto":
            self.orientation.set(box.orientation)
        self.my_colour = self._selected_colour()
        self.recognizer._tile_cache.clear()
        self.last, self.count, self.previous_frame = None, 0, None
        self.persist_layout = True
        self.position_ready = False
        self.status.set("Papan ditemukan. Menyinkronkan posisi dan menyiapkan rekomendasi…")
        self._cycle(token)

    def _begin(self, token):
        if not self.running or token != self.generation:
            return
        current = foreground()
        if current != self.coach_hwnd:
            self.target = current
        if not self.target:
            self.pause(); self.status.set("Aktifkan jendela papan saat hitung mundur."); return
        self.target_rect = rect(self.target)
        self._cycle(token)

    def _visible(self):
        return board_visible(self.target, self.coach_hwnd, self.settings.board,
                             rect(self.coach_hwnd) or (0,0,0,0))

    def _cycle(self, token):
        if not self.running or token != self.generation or self.closed:
            return
        # Commit background geometry only between vision jobs, never while a
        # worker is using settings or its tile cache.
        if self.pending_layout is not None:
            box, scan_rect, old_box = self.pending_layout
            self.pending_layout = None
            if rect(self.target) == scan_rect and self.settings.board == old_box:
                self.settings = replace(self.settings, board=box)
                if self.orientation.get() != "auto":
                    self.orientation.set(box.orientation)
                self.target_rect = scan_rect
                self.last, self.count, self.previous_frame = None, 0, None
                self.recognizer._tile_cache.clear()
                self.position_ready = False
                self.overlay.hide()
                self.persist_layout = True
        if not self._visible():
            self.position_ready = False; self.overlay.hide()
            current = foreground()
            if self.settings.auto_start and current not in (self.coach_hwnd, self.target):
                self._auto_find(token)
                return
            self.status.set("Papan tertutup / jendela lain aktif. Pindahkan panel keluar area papan.")
            self.root.after(150, lambda: self._cycle(token)); return
        current_rect = rect(self.target)
        if current_rect and self.target_rect and current_rect != self.target_rect:
            self.position_ready = False
            self.overlay.hide()
            if perf_counter()-self.last_scan > .75:
                self.force_scan = True
        # No periodic scans after ordinary moves. A scan has its own executor
        # and immutable snapshot; the normal observation loop keeps running.
        if self.force_scan:
            self._rescan(token)
        if not self.overlay.capture_excluded:
            self.overlay.hide()
            self.root.after(25, lambda: self._capture(token))
        else:
            self._capture(token)

    def _capture(self, token):
        if not self.running or token != self.generation:
            return
        if not self._visible():
            self.root.after(100, lambda: self._cycle(token)); return
        try:
            started = perf_counter()
            frame = guarded_screenshot(self.settings)
            self.capture_ms = (perf_counter()-started)*1000
            self.cycle_started = started
            if frame_changed(self.previous_frame, frame):
                self.last_visual_change = perf_counter()
                self.position_ready = False; self.overlay.hide()
                self.suggestion.set("Membaca perubahan…")
            self.previous_frame = frame
            self.future = self.pool.submit(self._process, frame)
            self.root.after(8, lambda: self._result(token))
        except Exception as exc:
            self.pause(); self.status.set(str(exc))

    def _rescan(self, token):
        if self.scan_future is not None and not self.scan_future.done():
            self.force_scan = False
            return
        self.force_scan = False
        self.last_scan = perf_counter()
        self.position_ready = False
        self.overlay.hide()
        try:
            target_rect = rect(self.target)
            if not target_rect:
                raise ValueError("Jendela papan tidak tersedia")
            settings = self.settings
            tracker = deepcopy(self.tracker)
            self.scan_future = self.scan_pool.submit(self._locate_snapshot, settings, tracker, target_rect)
            future = self.scan_future
            self.root.after(25, lambda: self._scan_result(token, target_rect, settings.board, future))
        except Exception as exc:
            self.status.set(f"Pencarian tertunda: {exc}")

    @staticmethod
    def _locate_snapshot(settings, tracker, target_rect):
        # No shared mutable recognition cache, tracker or Tk calls on this thread.
        worker = Coach.__new__(Coach)
        worker.settings = settings
        worker.tracker = tracker
        worker.recognizer = TemplateRecognizer(settings.templates_dir, settings.min_template_score)
        image = np.asarray(screenshot(*target_rect).convert("RGB"))
        return worker._locate(image, target_rect)

    def _locate(self, image, target_rect):
        box = detect_board(image, self.settings.board.orientation)
        cropped = image[box.top:box.bottom, box.left:box.right]
        first_placement = None
        for orientation in (box.orientation, "black" if box.orientation == "white" else "white"):
            oriented = replace(box, orientation=orientation)
            placement, details = self.recognizer.recognize(cropped, oriented)
            if all(d.score >= self.settings.min_template_score for d in details.values()):
                if orientation == box.orientation:
                    first_placement = placement
                candidate, _ = resolve_position(self.tracker, placement)
                if candidate is not None:
                    return replace(oriented, left=box.left+target_rect[0], right=box.right+target_rect[0],
                                   top=box.top+target_rect[1], bottom=box.bottom+target_rect[1])
        if (first_placement is not None and not self.tracker.synced
                and self.tracker.allow_midgame):
            layout = orient_midgame(first_placement, box.orientation, self.settings.orientation_mode)
            if layout is not None:
                return replace(box, orientation=layout[1], left=box.left+target_rect[0],
                               right=box.right+target_rect[0], top=box.top+target_rect[1],
                               bottom=box.bottom+target_rect[1])
            raise ValueError("Orientasi tengah match belum pasti. Pilih Di bawah: white/black, lalu Baca posisi sekarang.")
        raise ValueError(
            "Papan ditemukan, tetapi posisi belum cocok dengan template/FEN. "
            "Untuk tema atau ukuran baru: pilih Di bawah white/black sesuai papan, "
            "sesuaikan FEN (Posisi awal untuk papan awal), lalu Deteksi & pelajari (3 dtk). "
            "Aktifkan jendela papan selama hitung mundur, kemudian klik Mulai / lanjut.")

    def _scan_result(self, token, target_rect, old_box, future):
        if self.closed or not self.running or token != self.generation or future is not self.scan_future:
            return
        if not future.done():
            self.root.after(25, lambda: self._scan_result(token, target_rect, old_box, future)); return
        try:
            box = future.result()
            if rect(self.target) != target_rect:
                raise ValueError("Jendela masih bergerak")
            # An unchanged box must not reset stabilization or the fast cache.
            if box != self.settings.board or target_rect != self.target_rect:
                self.pending_layout = (box, target_rect, old_box)
        except Exception as exc:
            self.status.set(str(exc))

    def _process(self, frame):
        started = perf_counter()
        placement, detail = self.recognizer.recognize(frame, self.settings.board)
        tiles = self.recognizer.classified_tiles
        orientation = self.settings.board.orientation
        uncertain = [chess.square_name(s) for s, r in detail.items() if r.score < self.settings.min_template_score]
        candidate, reset = (None, False) if uncertain else resolve_position(self.tracker, placement)
        if candidate is None and not uncertain:
            opposite = "black" if orientation == "white" else "white"
            other_placement = placement_fen({63-s: d.symbol for s, d in detail.items()})
            other, other_reset = resolve_position(self.tracker, other_placement)
            if other is not None:
                candidate, reset, orientation, placement = other, other_reset, opposite, other_placement
        joining = candidate is None and not uncertain and not self.tracker.synced and self.tracker.allow_midgame
        layout = None
        if joining:
            layout = orient_midgame(placement, orientation, self.settings.orientation_mode)
            if layout is not None:
                placement, orientation = layout
        elapsed = (perf_counter()-started)*1000
        if uncertain:
            self.last, self.count = None, 0
            return None, "Petak belum pasti: " + ", ".join(uncertain), elapsed, tiles, orientation, False
        key = (orientation, placement)
        self.count = self.count+1 if key == self.last else 1
        self.last = key
        if self.count < max(3 if reset or joining else 2, self.settings.stable_frames):
            return None, "Menunggu frame stabil…", elapsed, tiles, orientation, False
        if candidate is None:
            if joining:
                if layout is None:
                    return None, "Pilih Di bawah: white/black lalu Baca posisi sekarang.", elapsed, tiles, orientation, False
                candidate = self.midgame.observe(placement, self.settings.startup_turn)
                if candidate is None:
                    return None, "Posisi terbaca. Menunggu satu langkah untuk mengetahui giliran; atau pilih Giliran awal: white/black.", elapsed, tiles, orientation, False
        if candidate is None:
            return None, "Mencari kembali posisi/papan yang cocok…", elapsed, tiles, orientation, False
        self.tracker = candidate
        return self.tracker.board.copy(), "Partai baru terdeteksi" if reset else "Posisi tersinkron", elapsed, tiles, orientation, reset

    def _result(self, token):
        if self.closed or token != self.generation or not self.running:
            return
        if not self.future.done():
            self.root.after(8, lambda: self._result(token)); return
        try:
            board, message, read_ms, tiles, orientation, reset = self.future.result()
            self.position_ready = board is not None
            if board is not None:
                self.failures = 0
                self.recovery.should_scan(perf_counter(), True, self.last_scan)
                if reset:
                    self._archive_game()
                    self.advice = self.engine_token = None
                    self.overlay.hide()
                    self.variation.set("")
                if orientation != self.settings.board.orientation:
                    self.settings = replace(self.settings, board=replace(self.settings.board, orientation=orientation))
                    if self.orientation.get() != "auto":
                        self.orientation.set(orientation)
                    self.persist_layout = True
                    self.overlay.hide()
                if self.persist_layout:
                    self._save_layout()
                self.my_colour = self._selected_colour()
                if self.active_board is None or self.active_board.fen() != board.fen():
                    # Follow the observed legal position, including moves that
                    # differ from the advice and two plies between captures.
                    self.advice = self.engine_token = None
                    self.variation.set("")
                    self.overlay.hide()
                self.active_board = board
                self.fen.set(board.fen())
                uci = [m.uci() for m in board.move_stack[-8:]]
                prefix = "Sesi dimulai tengah match; rokade lama tidak diketahui. Langkah: " if self.tracker.partial_history else "Langkah sesi: "
                self.history.set(prefix + (" → ".join(uci) if uci else "belum ada"))
                if board.is_game_over():
                    self.position_ready = False; self.overlay.hide()
                    self.advice = self.engine_token = None
                    self.variation.set("")
                    self.suggestion.set("Partai selesai — menunggu match baru")
                    message = "Permainan selesai: " + board.result() + ". Match baru akan dipantau otomatis."
                elif board.turn != self.my_colour:
                    self.overlay.hide(); self.suggestion.set("Menunggu lawan")
                    message = "Giliran lawan. Rekomendasi berikutnya muncul otomatis setelah langkah lawan terbaca."
                else:
                    message = "Stockfish sedang menghitung…" if self.advice is None or self.advice.fen != board.fen() else "Gerakkan bidak mengikuti petak merah."
                    self._request_advice(board)
                    self._show_advice()
            else:
                self.failures += 1
                waiting_stable = message.startswith("Menunggu frame")
                if self.recovery.should_scan(perf_counter(), waiting_stable, self.last_scan):
                    self.force_scan = True
                self.overlay.hide(); self.suggestion.set("Menunggu posisi stabil")
            engine_ms = f"{self.advice.milliseconds:.0f} ms / depth {self.advice.depth}" if self.advice else "—"
            self.metrics.set(f"Baca {read_ms:.1f} ms ({tiles}/64 petak)  •  Tangkap {self.capture_ms:.0f} ms  •  Mesin {engine_ms}")
            self.status.set(("Partai baru terdeteksi. " if reset else "") + message)
        except Exception as exc:
            self.pause(); self.status.set(f"Pemantauan berhenti: {exc}"); return
        interval = PROFILES[self.mode.get()][0]
        delay = max(5, interval-int((perf_counter()-self.cycle_started)*1000))
        self.root.after(delay, lambda: self._cycle(token))

    def _request_advice(self, board):
        if not self._license_allowed():
            return
        if self.advice and self.advice.fen == board.fen():
            return
        if self.engine_future is not None:
            return
        self.engine_token = self._analysis_token(board)
        self.engine_future = self.service.submit(board, PROFILES[self.mode.get()][1],
                                                 self.settings.engine_strength,
                                                 human_style=self.settings.human_style,
                                                 adaptive_timing=self.settings.adaptive_timing)

    def _analysis_token(self, board):
        return (self.generation, board.fen(), self.mode.get(),
                self.settings.human_style, self.settings.adaptive_timing, self.settings.engine_strength)

    def _engine_tick(self):
        if self.closed:
            return
        if self.engine_future is not None and self.engine_future.done():
            pending, token = self.engine_future, self.engine_token
            self.engine_future = None
            try:
                advice = pending.result()
                expected = self._analysis_token(self.active_board) if self.active_board else None
                if self.running and token == expected:
                    self.advice = advice
                    self._show_advice()
            except Exception as exc:
                expected = self._analysis_token(self.active_board) if self.active_board else None
                if self.running and token is not None and token == expected:
                    self.pause(); self.status.set(f"Stockfish berhenti: {exc}")
            # A newer board may have arrived while the previous search ran.
            # Start its analysis immediately instead of waiting for another capture.
            if (self.running and self.position_ready and self.active_board is not None
                    and self.active_board.turn == self.my_colour
                    and not self.active_board.is_game_over()):
                self._request_advice(self.active_board)
        self.root.after(15, self._engine_tick)

    def _show_advice(self):
        if not self._license_allowed():
            self.overlay.hide()
            return
        if (not self.running or not self.position_ready or not self.advice or not self.active_board
                or self.advice.fen != self.active_board.fen() or self.active_board.turn != self.my_colour
                or rect(self.target) != self.target_rect
                or not self._visible()):
            return
        move = self.advice.move
        self.suggestion.set(f"{self.active_board.san(move)}  •  {move.uci()}  •  {self.advice.score}")
        difficulty = f"Perkiraan {self.advice.complexity.lower()} | " if self.advice.complexity else ""
        self.variation.set(difficulty + "Rencana: " + self.advice.line)
        if self.overlay_enabled:
            self.overlay.show(move, self.settings.board)

    def _license_allowed(self):
        # Objek unit lama melalui __new__ tidak menjalankan lifecycle aplikasi.
        if not hasattr(self, "license_manager"):
            return True
        return self.license_manager is not None and self.license_manager.entitled

    def close(self):
        if self.license_controller is not None:
            self.license_controller.close()
        self.closed = True; self.running = False
        self.generation += 1
        self.overlay.close()
        self.hotkeys.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.scan_pool.shutdown(wait=False, cancel_futures=True)
        self.service.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def launch(args):
    Coach(args.config).run()
