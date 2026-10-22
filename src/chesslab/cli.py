from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import chess
import cv2

from .board import PIECE_NAME_TO_SYMBOL, apply_visible_move
from .config import BoardBox, load_settings
from .engine import Stockfish
from .vision import TemplateRecognizer, guarded_screenshot, stable_position
from .win32 import cursor_position
from .images import write_image


def board_for_visible_position(placement: str, turn: str, castling: str, ep: str, supplied_fen: str | None) -> chess.Board:
    """Keep state metadata only when its piece placement matches the current image."""
    board = chess.Board(supplied_fen) if supplied_fen else chess.Board(
        f"{placement} {'w' if turn == 'white' else 'b'} {castling} {ep} 0 1"
    )
    if board.board_fen() != placement:
        raise ValueError("Supplied FEN does not match the recognized board image.")
    return board


def _save_config(path: Path, box: BoardBox) -> None:
    width, height = box.right - box.left, box.bottom - box.top
    if width < 160 or height < 160 or abs(width - height) / max(width, height) > 0.10:
        raise ValueError("Kalibrasi ditolak: pilih sudut kiri-atas dan kanan-bawah seluruh papan 8x8 yang hampir persegi. Konfigurasi lama tidak diubah.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["board"] = vars(box)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


def calibrate(args: argparse.Namespace) -> None:
    path = Path(args.config).resolve()
    # Calibration must be able to repair an invalid existing board rectangle.
    json.loads(path.read_text(encoding="utf-8"))
    print("Tekan Enter untuk mulai. Anda punya 5 detik untuk mengarahkan mouse ke sudut KIRI-ATAS seluruh papan. Jangan klik terminal lagi.")
    input()
    time.sleep(5)
    left, top = cursor_position()
    print(f"Sudut pertama: ({left}, {top}). Dalam 5 detik, arahkan mouse ke sudut KANAN-BAWA seluruh papan.", flush=True)
    time.sleep(5)
    right, bottom = cursor_position()
    _save_config(path, BoardBox(left, top, right, bottom, args.orientation))
    print(f"Kalibrasi tersimpan: ({left}, {top})–({right}, {bottom}), orientasi {args.orientation}.")


def collect_templates(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    board = chess.Board(args.fen)
    print("Dalam 5 detik, aktifkan jendela papan lokal yang diizinkan (Alt+Tab).", flush=True)
    time.sleep(5)
    screen = guarded_screenshot(settings)
    box = settings.board
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        name = "empty" if piece is None else next(key for key, value in PIECE_NAME_TO_SYMBOL.items() if value == piece.symbol())
        col = chess.square_file(square) if box.orientation == "white" else 7 - chess.square_file(square)
        row = 7 - chess.square_rank(square) if box.orientation == "white" else chess.square_rank(square)
        y0, y1 = round(row * screen.shape[0] / 8), round((row + 1) * screen.shape[0] / 8)
        x0, x1 = round(col * screen.shape[1] / 8), round((col + 1) * screen.shape[1] / 8)
        folder = settings.templates_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        write_image(folder / f"{chess.square_name(square)}.png", cv2.cvtColor(screen[y0:y1, x0:x1], cv2.COLOR_RGB2BGR))
    print(f"Template ditulis ke {settings.templates_dir}")


def inspect(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    recognizer = TemplateRecognizer(settings.templates_dir, settings.min_template_score)
    print("Dalam 5 detik, aktifkan jendela papan lokal yang diizinkan (Alt+Tab).", flush=True)
    time.sleep(5)
    screen = guarded_screenshot(settings)
    placement, details = recognizer.recognize(screen, settings.board)
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    write_image(settings.runtime_dir / "last-board.png", cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))
    uncertain = [f"{chess.square_name(s)}={d.score:.2f}" for s, d in details.items() if d.score < settings.min_template_score]
    print("placement:", placement)
    print("uncertain:", ", ".join(uncertain) if uncertain else "none")


def analyze(args: argparse.Namespace) -> None:
    from .licensing.manager import default_manager
    manager = default_manager()
    if not manager.entitled:
        manager.refresh()
    if not manager.entitled:
        raise RuntimeError("Lisensi tidak aktif. Buka perintah coach untuk aktivasi atau perpanjangan.")
    settings = load_settings(args.config)
    recognizer = TemplateRecognizer(settings.templates_dir, settings.min_template_score)
    print("Dalam 5 detik, aktifkan jendela papan lokal yang diizinkan (Alt+Tab).", flush=True)
    time.sleep(5)
    placement = stable_position(settings, recognizer)
    board = board_for_visible_position(placement, args.turn, args.castling, args.ep, args.fen)
    if not board.is_valid():
        raise ValueError("Recognized position is invalid. Recalibrate or add better templates.")
    sf = Stockfish(settings.stockfish_path)
    try:
        move, score = sf.best_move(board, args.depth)
        print(f"FEN: {board.fen()}\nBest: {move.uci()}  score: {score}")
    finally:
        sf.close()


def play_local(args: argparse.Namespace) -> None:
    print("Klik otomatis sudah diganti. Gunakan: chesslab --config config.json coach")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChessLab: local/test chess vision only")
    parser.add_argument("--config", default="config.json")
    subs = parser.add_subparsers(required=True)
    def command(name: str) -> argparse.ArgumentParser:
        sub = subs.add_parser(name)
        # Also accept --config after the verb, a common Windows CLI convention.
        sub.add_argument("--config", default=argparse.SUPPRESS)
        return sub
    p = command("calibrate"); p.add_argument("--orientation", choices=("white", "black"), default="white"); p.set_defaults(func=calibrate)
    p = command("collect-templates"); p.add_argument("--fen", required=True); p.set_defaults(func=collect_templates)
    p = command("inspect"); p.set_defaults(func=inspect)
    from .coach import launch
    p = command("coach"); p.set_defaults(func=launch)
    p = command("analyze"); p.add_argument("--depth", type=int, default=16); p.add_argument("--turn", choices=("white", "black"), default="white"); p.add_argument("--castling", default="-"); p.add_argument("--ep", default="-"); p.add_argument("--fen", help="Authoritative full FEN; must match the image placement."); p.set_defaults(func=analyze)
    p = command("play-local"); p.add_argument("--my-color", choices=("white", "black"), required=True); p.add_argument("--depth", type=int, default=16); p.add_argument("--initial-turn", choices=("white", "black"), default="white"); p.add_argument("--castling", default="-"); p.add_argument("--ep", default="-"); p.add_argument("--initial-fen", help="Full initial FEN; must match the image placement."); p.add_argument("--confirm-local-test", action="store_true"); p.set_defaults(func=play_local)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
