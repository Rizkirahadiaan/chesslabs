from pathlib import Path
from types import SimpleNamespace

import chess
import chess.engine
import pytest

from chesslab.engine import AnalysisService


class Engine:
    def __init__(self):
        self.options = {}
        self.played_skills = []

    def configure(self, options):
        self.options.update(options)

    def play(self, board, limit):
        self.played_skills.append(self.options["Skill Level"])
        return SimpleNamespace(move=chess.Move.from_uci("a2a3"))

    def analyse(self, board, limit, root_moves=None, multipv=None):
        def info(uci, value):
            return {"pv": [chess.Move.from_uci(uci)], "depth": 8,
                    "score": chess.engine.PovScore(chess.engine.Cp(value), board.turn)}
        if root_moves:
            return info(root_moves[0].uci(), -20)
        if multipv:
            return [info("e2e4", 50), info("d2d4", 45), info("a2a3", -200)]
        return info("e2e4", 50)

    def quit(self):
        pass


@pytest.fixture
def service():
    service = AnalysisService(Path("unused"))
    service.engine = Engine()
    yield service
    service.close()
    service.pool.shutdown(wait=True)


@pytest.mark.parametrize("strength,skill", [("Menengah", 10), ("Pemula", 0)])
@pytest.mark.parametrize("human_style", [False, True])
def test_strength_uses_played_move_and_matching_evaluation(service, strength, skill, human_style):
    advice = service.submit(chess.Board(), .2, strength, human_style=human_style).result(timeout=2)
    assert service.engine.played_skills == [skill]
    assert advice.move.uci() == "a2a3"
    assert advice.line == "a3" and advice.score == "-0.20"
    maximum = service.submit(chess.Board(), .2, "Maksimal").result(timeout=2)
    assert maximum.move.uci() == "e2e4"
    assert service.engine.options["Skill Level"] == 20


@pytest.mark.parametrize("roll,expected", [(0.149, "a2a3"), (0.15, "e2e4"), (.99, "e2e4")])
def test_blunder_probability_boundary_and_legal_weaker_move(service, roll, expected):
    service.rng = SimpleNamespace(random=lambda: roll, choice=lambda items: items[0])
    advice = service.submit(chess.Board(), .2, "Blunder 15%").result(timeout=2)
    assert advice.move.uci() == expected
    assert advice.move in chess.Board().legal_moves


def test_invalid_strength_is_rejected(service):
    with pytest.raises(ValueError):
        service.submit(chess.Board(), .2, "unknown")
