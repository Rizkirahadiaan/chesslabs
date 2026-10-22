import json
from pathlib import Path

import numpy as np

from chesslab.config import load_settings
from chesslab.images import write_image
from chesslab.portable import prepare_data
from chesslab.vision import TemplateRecognizer


def make_seed(tmp_path):
    seed = tmp_path / "bundle"
    for folder in ("engine", "licenses", "templates/empty"):
        (seed / folder).mkdir(parents=True, exist_ok=True)
    (seed / "engine/stockfish.exe").write_bytes(b"engine")
    (seed / "licenses/Stockfish-Copying.txt").write_text("license")
    (seed / "templates/empty/a3.png").write_bytes(b"template")
    raw = json.loads(Path("config.example.json").read_text())
    raw.update(stockfish_path="engine/stockfish.exe", templates_dir="templates")
    (seed / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    return seed


def test_portable_paths_follow_config_after_move(tmp_path, monkeypatch):
    seed = make_seed(tmp_path)
    destination = tmp_path / "USB folder" / "ChessLab-data"
    config = prepare_data(seed, destination)
    moved = tmp_path / "Pindah folder" / "ChessLab-data"
    moved.parent.mkdir()
    destination.rename(moved)
    monkeypatch.chdir(tmp_path)
    settings = load_settings(moved / config.name)
    assert settings.stockfish_path == moved / "engine/stockfish.exe"
    assert settings.stockfish_path.read_bytes() == b"engine"
    assert (settings.templates_dir / "empty/a3.png").read_bytes() == b"template"
    assert settings.runtime_dir == moved / "runtime"


def test_relaunch_preserves_preferences_and_learned_templates(tmp_path):
    seed = make_seed(tmp_path)
    destination = tmp_path / "ChessLab-data"
    config = prepare_data(seed, destination)
    raw = json.loads(config.read_text())
    raw["engine_strength"] = "Pemula"
    config.write_text(json.dumps(raw))
    template = destination / "templates/empty/a3.png"
    template.write_bytes(b"new learned template")
    prepare_data(seed, destination)
    assert json.loads(config.read_text())["engine_strength"] == "Pemula"
    assert template.read_bytes() == b"new learned template"


def test_retry_interrupted_initialization_and_restore_missing_engine(tmp_path):
    seed = make_seed(tmp_path)
    destination = tmp_path / "ChessLab-data"
    (destination / "templates/empty").mkdir(parents=True)
    config = prepare_data(seed, destination)
    (destination / "engine/stockfish.exe").unlink()
    prepare_data(seed, destination)
    assert config.is_file()
    assert (destination / "engine/stockfish.exe").read_bytes() == b"engine"


def test_learned_template_round_trip_in_unicode_portable_folder(tmp_path):
    templates = tmp_path / "USB caf\u00e9 \u68cb" / "templates"
    piece = templates / "white_king"
    piece.mkdir(parents=True)
    image = np.zeros((96, 96, 3), dtype=np.uint8)
    image[20:70, 30:60] = 230
    assert write_image(piece / "e1.png", image)
    recognizer = TemplateRecognizer(templates, .74)
    assert "K" in recognizer.templates
    assert recognizer.classify(image).symbol == "K"
