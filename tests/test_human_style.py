from pathlib import Path
import json

import chess
import chess.engine
import pytest

from chesslab.config import load_settings
from chesslab.engine import AnalysisService


def info(board, move, score=30, depth=12, mate=False):
    value = chess.engine.Mate(score) if mate else chess.engine.Cp(score)
    return {"pv": [chess.Move.from_uci(move)], "depth": depth,
            "score": chess.engine.PovScore(value, board.turn)}


class Engine:
    def __init__(self, baseline, candidates):
        self.baseline, self.candidates = baseline, candidates
        self.calls, self.options = [], {}

    def configure(self, options):
        self.options.update(options)

    def analyse(self, board, limit, **kwargs):
        self.calls.append((limit, kwargs))
        return self.candidates if "multipv" in kwargs else self.baseline

    def quit(self):
        pass


@pytest.fixture
def service():
    service = AnalysisService(Path("unused"))
    yield service
    service.close()
    service.pool.shutdown(wait=True)


@pytest.mark.parametrize("black", [False, True])
def test_style_prefers_development_only_among_equal_best_and_keeps_full_budget(service, black):
    board = chess.Board()
    if black:
        board.push_uci("e2e4")
    pawn, knight = ("a7a6", "g8f6") if black else ("a2a3", "g1f3")
    baseline = info(board, pawn)
    service.engine = Engine(baseline, [baseline, info(board, knight)])
    advice = service.submit(board, .2, human_style=True).result(timeout=2)
    assert advice.move.uci() == knight
    assert advice.score == "+0.30"
    assert advice.line == ("Nf6" if black else "Nf3")
    assert service.engine.options == {"Skill Level": 20, "UCI_LimitStrength": False}
    assert service.engine.calls[0][0].time == .2
    assert service.engine.calls[1][0].time == pytest.approx(.6)
    assert service.engine.calls[1][0].depth == 12
    assert service.engine.calls[1][1] == {"multipv": 3}


@pytest.mark.parametrize("score,depth,mate,bound", [
    (29, 12, False, False),  # Even one centipawn lower is excluded.
    (30, 11, False, False),  # Shallower search cannot justify changing the move.
    (3, 12, True, False),
    (30, 12, False, True),
])
def test_quality_guard_retains_baseline(service, score, depth, mate, bound):
    board = chess.Board()
    baseline = info(board, "a2a3")
    alternative = info(board, "g1f3", score, depth, mate)
    alternative["lowerbound"] = bound
    service.engine = Engine(baseline, [baseline, alternative])
    advice = service.submit(board, .2, human_style=True).result(timeout=2)
    assert advice.move.uci() == "a2a3"


def test_style_off_uses_single_original_search(service):
    board = chess.Board()
    baseline = info(board, "a2a3")
    service.engine = Engine(baseline, [info(board, "g1f3")])
    assert service.submit(board, .2).result(timeout=2).move.uci() == "a2a3"
    assert len(service.engine.calls) == 1


def test_style_retains_mate_and_does_not_run_extra_search(service):
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    service.engine = Engine(info(board, "f7g7", 1, mate=True), [])
    advice = service.submit(board, .2, human_style=True).result(timeout=2)
    assert advice.move.uci() == "f7g7" and advice.score == "Mat +1"
    assert len(service.engine.calls) == 1


def test_style_retains_forced_check_response(service):
    board = chess.Board("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")
    service.engine = Engine(info(board, "e1d1"), [])
    assert service.submit(board, .2, human_style=True).result(timeout=2).move.uci() == "e1d1"
    assert len(service.engine.calls) == 1


def test_comparison_must_not_regress_below_original_evaluation(service):
    board = chess.Board()
    service.engine = Engine(info(board, "a2a3", 40),
                            [info(board, "a2a3", 30), info(board, "g1f3", 30)])
    assert service.submit(board, .2, human_style=True).result(timeout=2).move.uci() == "a2a3"


def test_castling_preferred_among_equal_moves(service):
    board = chess.Board("r3k2r/ppp2ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP2PPP/R3K2R w KQkq - 0 8")
    baseline = info(board, "a2a3")
    service.engine = Engine(baseline, [baseline, info(board, "e1g1")])
    advice = service.submit(board, .2, human_style=True).result(timeout=2)
    assert advice.move.uci() == "e1g1" and advice.line == "O-O"


def test_config_defaults_off_and_round_trips_boolean(tmp_path):
    raw = {"stockfish_path": "engine.exe", "allowed_window_titles": [],
           "board": {"left": 0, "top": 0, "right": 800, "bottom": 800}}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    assert not load_settings(path).human_style
    raw["human_style"] = True
    path.write_text(json.dumps(raw))
    assert load_settings(path).human_style
    for invalid in ("OFF", "true", 1, None):
        raw["human_style"] = invalid
        path.write_text(json.dumps(raw))
        with pytest.raises(ValueError, match="human_style"):
            load_settings(path)


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("toggle", [False, True])
def test_human_level_can_choose_slightly_weaker_move_but_excludes_large_loss(service, black, toggle):
    from types import SimpleNamespace
    board = chess.Board()
    if black:
        board.push_uci("e2e4")
    moves = ("e7e5", "g8f6", "a7a6") if black else ("e2e4", "g1f3", "a2a3")
    candidates = [info(board, moves[0], 50), info(board, moves[1], 15), info(board, moves[2], 14)]
    service.engine = Engine(candidates[0], candidates)
    def choose(items, weights, k):
        assert [item["pv"][0].uci() for item in items] == list(moves[:2])
        assert all(weight > 0 for weight in weights)
        return [items[-1]]
    service.rng = SimpleNamespace(choices=choose)
    advice = service.submit(board, .2, "Human", human_style=toggle).result(timeout=2)
    assert advice.move.uci() == moves[1]
    assert advice.score == "+0.15" and advice.line == board.san(advice.move)
    assert service.engine.options["Skill Level"] == 20
    assert service.engine.calls[1][1]["multipv"] == 5


def test_human_level_endgame_has_stricter_tolerance(service):
    from types import SimpleNamespace
    board = chess.Board("7k/8/8/8/8/8/P7/4K3 w - - 0 1")
    candidates = [info(board, "a2a4", 50), info(board, "e1d2", 35), info(board, "a2a3", 34)]
    service.engine = Engine(candidates[0], candidates)
    def choose(items, **kwargs):
        assert len(items) == 2
        return [items[-1]]
    service.rng = SimpleNamespace(choices=choose)
    assert service.submit(board, .2, "Human").result(timeout=2).move.uci() == "e1d2"


def test_human_level_preserves_mate_and_ignores_losing_mate_candidates(service):
    board = chess.Board()
    baseline = info(board, "e2e4", 50)
    service.engine = Engine(baseline, [baseline, info(board, "a2a3", -3, mate=True)])
    assert service.submit(board, .2, "Human").result(timeout=2).move.uci() == "e2e4"
    service.engine = Engine(info(board, "e2e4", 3, mate=True), [])
    assert service.submit(board, .2, "Human").result(timeout=2).score == "Mat +3"
    assert len(service.engine.calls) == 1


def test_human_level_retains_baseline_when_extra_search_is_too_shallow(service):
    board = chess.Board()
    service.engine = Engine(info(board, "e2e4"), [info(board, "g1f3", depth=2)])
    assert service.submit(board, .2, "Human").result(timeout=2).move.uci() == "e2e4"
