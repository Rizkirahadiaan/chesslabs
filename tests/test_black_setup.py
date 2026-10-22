import chess
import pytest
from chesslab.board import grid_cell, square_at
from chesslab.config import BoardBox
from chesslab.tracker import PositionTracker, reconcile_opening


@pytest.mark.parametrize("uci", ["e2e4", "d2d4", "g1f3", "c2c4"])
def test_setup_after_white_opening_infers_black_turn(uci):
    board = chess.Board(); board.push_uci(uci)
    result = reconcile_opening(chess.Board(), set(board.piece_map()))
    assert result.fen() == board.fen()
    assert result.turn == chess.BLACK
    assert result.castling_rights == board.castling_rights
    assert result.ep_square == board.ep_square


def test_white_moves_between_training_and_start():
    tracker = PositionTracker(chess.STARTING_FEN, allow_opening=True)
    board = chess.Board(); board.push_uci("e2e4")
    assert tracker.observe(board.board_fen())
    assert tracker.board.fen() == board.fen()
    board.push_uci("c7c5")
    assert tracker.observe(board.board_fen())
    assert tracker.board.turn == chess.WHITE


def test_unknown_opening_position_not_guessed():
    board = chess.Board(); board.remove_piece_at(chess.E2)
    with pytest.raises(ValueError):
        reconcile_opening(chess.Board(), set(board.piece_map()))


def test_black_overlay_coordinates_all_squares():
    box = BoardBox(14,9,798,793,"black")
    for row in range(8):
        for col in range(8):
            square = square_at(row,col,"black")
            assert grid_cell(square, box) == (14+(col+.5)*98, 9+(row+.5)*98)
    assert square_at(0,0,"black") == chess.H1
    assert square_at(7,7,"black") == chess.A8
