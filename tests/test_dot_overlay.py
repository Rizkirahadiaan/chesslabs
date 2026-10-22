import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import chess
import pytest

from chesslab.board import square_at
from chesslab.coach import Coach
from chesslab.config import BoardBox, load_settings
from chesslab.overlay import marker_rect


@pytest.mark.parametrize("orientation", ["white", "black"])
@pytest.mark.parametrize("size", [3, 5, 10])
def test_markers_stay_in_correct_square_corner(orientation, size):
    box = BoardBox(-800, 110, -104, 814, orientation)
    for row in range(8):
        for col in range(8):
            square = square_at(row, col, orientation)
            x, y, width, height = marker_rect(square, box, size)
            left, top = box.left + col*87, box.top + row*88
            assert left + 87/2 < x < x+width < left+87
            assert top < y < y+height < top+88/2
            assert width == height == size+2


def test_markers_reverse_with_board_orientation():
    box = BoardBox(0, 0, 800, 800)
    assert marker_rect(chess.E2, box, 5) == marker_rect(chess.D7, replace(box, orientation="black"), 5)


@pytest.mark.parametrize("key,value", [("marker_size", 2), ("marker_size", 11),
    ("marker_size", 5.5), ("marker_opacity", .01), ("marker_opacity", 1),
    ("marker_opacity", float("nan")), ("overlay_style", "unknown")])
def test_invalid_marker_settings_are_rejected(tmp_path, key, value):
    raw = json.loads(Path("config.example.json").read_text())
    raw[key] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=key):
        load_settings(path)


def test_marker_controls_persist_without_changing_board_or_strength(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(Path("config.example.json").read_text())
    coach = Coach.__new__(Coach)
    coach.path, coach.settings = path, load_settings(path)
    coach.marker_size = SimpleNamespace(get=lambda: 3)
    coach.opacity = SimpleNamespace(get=lambda: 25)
    calls = []
    coach.overlay = SimpleNamespace(set_size=lambda v: calls.append(v),
                                    set_opacity=lambda v: calls.append(v))
    old = coach.settings
    coach._save_marker_options()
    saved = load_settings(path)
    assert saved.marker_size == 3 and saved.marker_opacity == .25
    assert saved.board == old.board and saved.engine_strength == old.engine_strength
    assert calls == [3, .25]


def test_legacy_config_keeps_dots_and_shadow_selection_loads(tmp_path):
    raw = json.loads(Path("config.example.json").read_text())
    raw.pop("overlay_style", None)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    assert load_settings(path).overlay_style == "dots"
    raw["overlay_style"] = "shadow"
    path.write_text(json.dumps(raw))
    assert load_settings(path).overlay_style == "shadow"
