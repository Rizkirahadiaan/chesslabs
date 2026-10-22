"""One-click entry point; writable data stays beside the portable executable."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import ctypes
import json
from pathlib import Path
import shutil
import sys
import traceback


def prepare_data(seed: Path, destination: Path) -> Path:
    """Seed once, preserve preferences and learned templates on later launches."""
    destination.mkdir(parents=True, exist_ok=True)
    config = destination / "config.json"
    if not config.exists():
        # Write config last so an interrupted first launch can safely be retried.
        shutil.copytree(seed / "templates", destination / "templates", dirs_exist_ok=True)
    for folder in ("engine", "licenses"):
        for source in (seed / folder).rglob("*"):
            if source.is_file():
                target = destination / source.relative_to(seed)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + ".initializing")
                    shutil.copy2(source, temporary)
                    temporary.replace(target)
    if not config.exists():
        temporary = destination / "config.initializing"
        shutil.copyfile(seed / "config.json", temporary)
        temporary.replace(config)
    (destination / "runtime").mkdir(exist_ok=True)
    return config


def self_test(config: Path) -> dict:
    """Exercise bundled native libraries, template loading, UCI, and the real GUI."""
    import chess
    from .coach import Coach
    from .config import load_settings
    from .engine import Stockfish
    from .vision import TemplateRecognizer

    settings = load_settings(config)
    recognizer = TemplateRecognizer(settings.templates_dir, settings.min_template_score)
    if len(recognizer.templates) != 13:
        raise RuntimeError("Template bawaan tidak lengkap")
    engine = Stockfish(settings.stockfish_path)
    try:
        move, score = engine.best_move(chess.Board(), depth=8, seconds=.3)
        if move not in chess.Board().legal_moves:
            raise RuntimeError("Stockfish mengembalikan langkah tidak legal")
        name = engine.engine.id.get("name", "Stockfish")
    finally:
        engine.close()
    app = Coach(config)
    try:
        app.pause()  # Do not scan the user's desktop during the packaging check.
        app.root.update_idletasks()
        title = app.root.title()
        human_style_moves = {}
        for enabled in (False, True):
            advice = app.service.submit(chess.Board(), .18, human_style=enabled).result(timeout=10)
            if advice.move not in chess.Board().legal_moves:
                raise RuntimeError("Gaya manusiawi mengembalikan langkah tidak legal")
            human_style_moves["ON" if enabled else "OFF"] = advice.move.uci()
        if app.human_style.get() != settings.human_style:
            raise RuntimeError("Pengaturan gaya manusiawi tidak dimuat ke menu")
        human_advice = app.service.submit(chess.Board(), .18, "Human").result(timeout=10)
        if human_advice.move not in chess.Board().legal_moves:
            raise RuntimeError("Level Human mengembalikan langkah tidak legal")
        styles = []
        for style in ("shadow", "dots"):
            app.overlay.set_style(style)
            app.root.update_idletasks()
            if app.overlay.style != style or app.overlay.visible:
                raise RuntimeError("Pergantian tampilan penanda gagal")
            for canvas in app.overlay.canvases:
                if style == "dots" and len(canvas.find_all()) != 1:
                    raise RuntimeError("Penanda titik tidak tersedia")
                if style == "shadow" and canvas.cget("background") != "#ff2020":
                    raise RuntimeError("Penanda bayangan tidak tersedia")
            styles.append(style)
        app.overlay.set_style(settings.overlay_style)
        app.root.after(100, app.close)
        app.run()
    finally:
        if not app.closed:
            app.close()
    return {"ok": True, "frozen": bool(getattr(sys, "frozen", False)),
            "config": str(config), "engine": name, "move": move.uci(),
            "score": score, "template_groups": len(recognizer.templates), "window": title,
            "overlay_styles": styles, "human_style_moves": human_style_moves,
            "human_level_move": human_advice.move.uci()}


def main() -> int:
    parser = argparse.ArgumentParser(description="ChessLab Coach portable")
    parser.add_argument("--self-test", type=Path, metavar="REPORT.json",
                        help="uji paket dan tulis laporan tanpa memantau papan")
    args = parser.parse_args()
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS)
        home = Path(sys.executable).resolve().parent
    else:
        raise RuntimeError("Gunakan Build-Portable.cmd untuk membuat aplikasi portable.")
    destination = home / "ChessLab-data"
    log_path = destination / "runtime" / "portable.log"
    try:
        config = prepare_data(bundle / "portable", destination)
        with ExitStack() as stack:
            # PyInstaller --windowed sets stdout/stderr to None. Keep diagnostics
            # (including Tk callback exceptions) available without a terminal.
            log = stack.enter_context(log_path.open("a", encoding="utf-8", buffering=1))
            stack.enter_context(redirect_stdout(log))
            stack.enter_context(redirect_stderr(log))
            if args.self_test:
                result = self_test(config)
                args.self_test.resolve().write_text(json.dumps(result, indent=2), encoding="utf-8")
            else:
                from .coach import Coach
                Coach(config).run()
        return 0
    except Exception:
        details = traceback.format_exc()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as log:
                log.write(details + "\n")
        except OSError:
            pass
        if args.self_test:
            args.self_test.resolve().write_text(json.dumps({"ok": False, "error": details}, indent=2),
                                              encoding="utf-8")
        else:
            ctypes.windll.user32.MessageBoxW(
                0, "ChessLab belum dapat dibuka.\n\n"
                "Letakkan EXE di folder yang bisa ditulis, misalnya Desktop atau USB.\n"
                f"Detail: {log_path}\n\n{details.splitlines()[-1]}",
                "ChessLab Coach", 0x10)
        return 1
