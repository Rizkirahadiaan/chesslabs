from __future__ import annotations

from pathlib import Path
import time
from typing import NamedTuple
import zlib

import chess
import cv2
import numpy as np

from .board import PIECE_NAME_TO_SYMBOL, placement_fen, square_at
from .config import BoardBox, Settings
from .win32 import screenshot
from .images import read_image


class Recognition(NamedTuple):
    symbol: str | None
    score: float


class TemplateRecognizer:
    """Theme-specific normalized image-template recognizer.

    A template is an image of an entire square stored in templates/<piece name>/.
    Empty-square templates are trained alongside pieces, keeping the pipeline
    inspectable for local test boards and avoiding a guess from square colour alone.
    """

    def __init__(self, templates_dir: Path, min_score: float) -> None:
        self.min_score = min_score
        self.templates: dict[str | None, list[np.ndarray]] = {}
        known_templates = {**PIECE_NAME_TO_SYMBOL, "empty": None}
        for name, symbol in known_templates.items():
            images: list[np.ndarray] = []
            folder = templates_dir / name
            try:
                files = list(folder.iterdir())
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                raise PermissionError(
                    f"Folder template tidak dapat dibaca: {templates_dir}. "
                    "Pilih Di bawah: white/black sesuai papan, lalu klik "
                    "Deteksi & pelajari untuk membuat template baru."
                ) from exc
            for file in files:
                if file.suffix.lower() != ".png":
                    continue
                image = read_image(file, cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    images.append(image)
            if images:
                self.templates[symbol] = images
        if not self.templates:
            raise FileNotFoundError(
                f"No templates found in {templates_dir}. Run collect-templates first."
            )
        self.features = {symbol: [self._features(template) for template in images]
                         for symbol, images in self.templates.items()}
        self._tile_cache = {}
        self.classified_tiles = 0

    @staticmethod
    def _normalize(image: np.ndarray, size: int = 96) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
        return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _features(image):
        gray = TemplateRecognizer._normalize(image)
        crop = cv2.Canny(gray, 45, 110).astype(np.float32) / 255
        crop[:7] = 0
        # File letters at the bottom are not pieces (e.g. the 'b' on b1).
        crop[-16:] = 0
        crop[:, :9] = 0
        crop[:, -9:] = 0
        crop[:23, :25] = 0
        crop[:23, -25:] = 0
        return cv2.GaussianBlur(crop, (5, 5), 0), float(crop.sum()), float(np.median(gray[44:67, 36:60]))

    def classify(self, image: np.ndarray) -> Recognition:
        a, edge_count, tone = self._features(image)
        if edge_count < 45:
            return Recognition(None, 1.0)
        padded = cv2.copyMakeBorder(a, 16, 16, 16, 16, cv2.BORDER_CONSTANT)
        best_symbol: str | None = None
        best_score = -1.0
        for symbol, features in self.features.items():
            for b, ref_count, ref_tone in features:
                if symbol is None:
                    score = 1.0 if edge_count < 45 else 0.0
                else:
                    tone_factor = 1 - abs(tone - ref_tone) / 255
                    if ref_count < 45 or tone_factor <= best_score:
                        continue
                    # Blurred edges tolerate a few pixels of translation and scale
                    # error while removing the square's background colour.
                    corr = cv2.matchTemplate(padded, b, cv2.TM_CCORR_NORMED)
                    score = float(corr.max()) if ref_count > 25 and edge_count > 25 else 0.0
                    # Central piece fill separates white and black silhouettes.
                    score *= tone_factor
                if score > best_score:
                    best_symbol, best_score = symbol, score
                    if score >= .999:
                        return Recognition(best_symbol, score)
        return Recognition(best_symbol if best_score >= self.min_score else None, best_score)

    def recognize(self, screenshot: np.ndarray, box: BoardBox) -> tuple[str, dict[chess.Square, Recognition]]:
        cells: dict[chess.Square, str | None] = {}
        detail: dict[chess.Square, Recognition] = {}
        height, width = box.bottom - box.top, box.right - box.left
        if screenshot.shape[:2] != (height, width):
            raise ValueError("Ukuran screenshot tidak cocok dengan kalibrasi papan.")
        self.classified_tiles = 0
        for row in range(8):
            for col in range(8):
                y0, y1 = round(row * height / 8), round((row + 1) * height / 8)
                x0, x1 = round(col * width / 8), round((col + 1) * width / 8)
                crop = screenshot[y0:y1, x0:x1]
                square = square_at(row, col, box.orientation)
                key = (square, crop.shape, zlib.crc32(crop.tobytes()))
                cached = self._tile_cache.get(square)
                if cached is not None and cached[0] == key:
                    result = cached[1]
                else:
                    result = self.classify(crop)
                    self._tile_cache[square] = (key, result)
                    self.classified_tiles += 1
                cells[square], detail[square] = result.symbol, result
        return placement_fen(cells), detail


def guarded_screenshot(settings: Settings) -> np.ndarray:
    """Capture screenshot directly from configured board coordinates."""
    box = settings.board
    image = screenshot(box.left, box.top, box.right, box.bottom)
    return np.asarray(image)


def stable_position(settings: Settings, recognizer: TemplateRecognizer) -> str:
    """Return a board placement only after equal consecutive frames."""
    last: str | None = None
    count = 0
    while True:
        placement, details = recognizer.recognize(guarded_screenshot(settings), settings.board)
        uncertain = [chess.square_name(s) for s, result in details.items() if result.score < settings.min_template_score]
        if uncertain:
            raise ValueError("Pengenalan belum pasti pada petak: " + ", ".join(uncertain) + ". Periksa kalibrasi/template dengan inspect.")
        count = count + 1 if placement == last else 1
        if count >= settings.stable_frames:
            return placement
        last = placement
        time.sleep(settings.poll_interval_seconds)
