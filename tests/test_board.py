import chess

from chesslab.board import apply_visible_move, grid_cell, square_at
from chesslab.config import BoardBox
from chesslab.cli import board_for_visible_position


def test_white_orientation_square_mapping_round_trip():
    box = BoardBox(0, 0, 800, 800, "white")
    assert square_at(7, 0, "white") == chess.A1
    assert square_at(0, 7, "white") == chess.H8
    assert grid_cell(chess.A1, box) == (50.0, 750.0)


def test_detects_only_legal_visible_move():
    board = chess.Board()
    board.push_uci("e2e4")
    expected = board.copy(stack=False)
    expected.push_uci("c7c5")
    assert apply_visible_move(board, expected.board_fen()) == chess.Move.from_uci("c7c5")


def test_authoritative_fen_must_match_the_image():
    with __import__("pytest").raises(ValueError):
        board_for_visible_position(chess.STARTING_BOARD_FEN, "white", "-", "-", "8/8/8/8/8/8/8/8 w - - 0 1")
