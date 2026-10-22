import argparse
import json

import pytest

from chesslab import cli
from chesslab.config import BoardBox


def test_recalibrate_invalid_existing_coordinates(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"stockfish_path": "keep.exe", "board": {"left": 1104, "top": 940, "right": 860, "bottom": 861}}))
    positions = iter([(100, 100), (900, 900)])
    monkeypatch.setattr(cli, "cursor_position", lambda: next(positions))
    monkeypatch.setattr("builtins.input", lambda: "")
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    cli.calibrate(argparse.Namespace(config=str(path), orientation="white"))
    result = json.loads(path.read_text())
    assert result["board"] == dict(left=100, top=100, right=900, bottom=900, orientation="white")
    assert result["stockfish_path"] == "keep.exe"


def test_bad_capture_does_not_overwrite_configuration(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"board": "original"}')
    with pytest.raises(ValueError):
        cli._save_config(path, BoardBox(1104, 940, 860, 861))
    assert path.read_text() == '{"board": "original"}'
