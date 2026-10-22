from pathlib import Path
from unittest.mock import Mock

import chess
import chess.engine
import pytest

from chesslab.engine import AnalysisService, _position_complexity


def candidates(first=50, second=40, depth=12, turn=chess.WHITE):
    return [dict(pv=[chess.Move.from_uci(move)], depth=depth,
                 score=chess.engine.PovScore(chess.engine.Cp(score), turn))
            for move, score in (("e2e4", first), ("d2d4", second))]


@pytest.mark.parametrize("first,second,expected", [(200, 0, "Mudah"),
                                                    (90, 20, "Sedang"), (50, 40, "Rumit")])
def test_gap_drives_budget(first, second, expected):
    service = AnalysisService(Path("unused"))
    service.engine = Mock()
    service.engine.analyse.return_value = candidates(first, second)
    try:
        budget, label = service._adaptive_budget(chess.Board(), .45)
        assert label == expected
        factor = {"Mudah": .6, "Sedang": 1, "Rumit": 2}[expected]
        assert budget + .1125 == pytest.approx(.45 * factor)
    finally:
        service.close()


def test_incomplete_probe_does_not_shorten_search():
    assert _position_complexity(chess.Board(), candidates(depth=2)) == "Sedang"
    assert _position_complexity(chess.Board(), []) == "Sedang"


def test_mate_and_black_perspective():
    board = chess.Board().mirror()
    data = candidates()
    for item in data:
        item["pv"] = [chess.Move(chess.square_mirror(item["pv"][0].from_square),
                                 chess.square_mirror(item["pv"][0].to_square))]
    data[0]["score"] = chess.engine.PovScore(chess.engine.Mate(1), chess.BLACK)
    assert _position_complexity(board, data) == "Mudah"
    data[0]["score"] = chess.engine.PovScore(chess.engine.Mate(4), chess.BLACK)
    assert _position_complexity(board, data) == "Rumit"


@pytest.mark.parametrize("strength", ["Maksimal", "Human", "Menengah", "Pemula", "Blunder 15%"])
def test_off_keeps_original_search_and_on_restores_strength(strength):
    service = AnalysisService(Path("unused"))
    service.engine = Mock()
    service.engine.analyse.side_effect = lambda *args, **kwargs: candidates() if "multipv" in kwargs else candidates()[0]
    service.engine.play.return_value.move = chess.Move.from_uci("e2e4")
    service.rng.random = lambda: 1
    try:
        off = service.submit(chess.Board(), .18, strength).result()
        assert off.complexity == ""
        service.engine.reset_mock()
        on = service.submit(chess.Board(), .18, strength, adaptive_timing=True).result()
        assert on.complexity == "Rumit" and on.move in chess.Board().legal_moves
        skill = {"Menengah": 10, "Pemula": 0}.get(strength, 20)
        assert service.engine.configure.call_args_list[1].args[0]["Skill Level"] == skill
    finally:
        service.close()
