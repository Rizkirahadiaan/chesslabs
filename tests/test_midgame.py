from dataclasses import replace
from types import SimpleNamespace

import chess
import pytest

from chesslab.board import placement_fen
from chesslab.config import BoardBox
from chesslab.midgame import MidgameBootstrap, orient_midgame, possible_boards
from chesslab.tracker import PositionTracker
from chesslab.vision import Recognition
from test_live_recommendations import make_coach, observe, finish_search


# Position transcribed from the user's screenshot, after ...bxc4.
PLACEMENT = "r1bq1rk1/5ppp/p1pb4/3n4/2p5/1B6/PP1P1PPP/RNBQR1K1"


def test_auto_waits_for_move_then_knows_turn_and_tracks_actual_position():
    bootstrap = MidgameBootstrap()
    assert bootstrap.observe(PLACEMENT) is None
    assert bootstrap.observe(PLACEMENT) is None
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    board.push_uci("b3c4")
    tracker = bootstrap.observe(board.board_fen())
    assert tracker.synced and tracker.partial_history
    assert tracker.board.fen() == board.fen()
    assert tracker.board.turn == chess.BLACK
    board.push(next(iter(board.legal_moves)))
    assert tracker.observe(board.board_fen())


@pytest.mark.parametrize("turn", ["white", "black"])
def test_explicit_turn_bootstraps_immediately_without_invented_rights(turn):
    tracker = MidgameBootstrap().observe(PLACEMENT, turn)
    assert tracker.board.turn == (turn == "white")
    assert tracker.board.castling_rights == 0 and tracker.board.ep_square is None
    assert tracker.partial_history


def test_check_can_prove_the_turn():
    placement = "6k1/8/8/8/8/8/8/4K1R1"
    tracker = MidgameBootstrap().observe(placement)
    assert tracker.board.turn == chess.BLACK and tracker.board.is_check()


def test_invalid_board_never_bootstraps():
    assert not possible_boards("8/8/8/8/8/8/8/8")
    assert MidgameBootstrap().observe("8/8/8/8/8/8/8/8", "white") is None


def test_orientation_from_home_pawns_and_explicit_endgame_override():
    assert orient_midgame(PLACEMENT, "white") == (PLACEMENT, "white")
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    flipped = placement_fen({63-s: p.symbol() for s, p in board.piece_map().items()})
    assert orient_midgame(flipped, "black") == (PLACEMENT, "white")
    sparse = "6k1/8/8/8/8/8/8/4K3"
    assert orient_midgame(sparse, "white") is None
    assert orient_midgame(sparse, "white", "white") == (sparse, "white")


def enable_midgame(c, turn="auto"):
    c.settings = replace(c.settings, startup_turn=turn)
    c.tracker.allow_midgame = True
    c.midgame = MidgameBootstrap()
    c._save_layout = lambda: setattr(c, "persist_layout", False)


def test_coach_joins_screenshot_position_then_recommends_after_opponent_move(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch, orientation="black")
    enable_midgame(c)
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    observe(c, board)
    observe(c, board)
    assert not submitted and not c.tracker.synced
    assert "Giliran awal" in c.status.get()
    board.push_uci("b3c4")
    observe(c, board)
    observe(c, board)
    assert c.tracker.synced and c.running
    assert submitted[-1][0].fen() == board.fen()
    finish_search(c, submitted)
    assert shown


def test_coach_explicit_turn_requires_stable_frames_and_preserves_followup(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch, orientation="white")
    enable_midgame(c, "white")
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    observe(c, board)
    assert not submitted
    observe(c, board)
    assert len(submitted) == 1
    finish_search(c, submitted)
    board.push_uci("b3c4")
    board.push(next(iter(board.legal_moves)))
    observe(c, board)
    assert submitted[-1][0].fen() == board.fen()
    assert c.tracker.partial_history


def test_existing_synced_game_never_replaced_by_arbitrary_midgame(monkeypatch):
    c, _, submitted = make_coach(monkeypatch, orientation="white")
    enable_midgame(c, "white")
    c.tracker.synced = True
    before = c.tracker.board.fen()
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    observe(c, board)
    observe(c, board)
    assert c.tracker.board.fen() == before
    assert not submitted


def test_discovery_accepts_midgame_without_matching_initial_fen(monkeypatch):
    import numpy as np
    c, _, _ = make_coach(monkeypatch, orientation="white")
    enable_midgame(c)
    box = BoardBox(0, 0, 160, 160, "white")
    monkeypatch.setattr("chesslab.coach.detect_board", lambda *args: box)
    board = chess.Board(f"{PLACEMENT} w - - 0 1")
    def recognize(frame, oriented):
        cells = {s: p.symbol() for s, p in board.piece_map().items()}
        if oriented.orientation == "black":
            cells = {63-s: p for s, p in cells.items()}
        return placement_fen(cells), {s: Recognition(cells.get(s), 1.) for s in chess.SQUARES}
    c.recognizer = SimpleNamespace(recognize=recognize)
    found = c._locate(np.zeros((160, 160, 3)), (30, 40, 190, 200))
    assert found == BoardBox(30, 40, 190, 200, "white")
