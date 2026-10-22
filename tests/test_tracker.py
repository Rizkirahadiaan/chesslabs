import chess
from chesslab.tracker import PositionTracker


def test_missed_two_plies_preserve_metadata():
    t = PositionTracker(chess.STARTING_FEN)
    assert t.observe(chess.STARTING_BOARD_FEN)
    b = chess.Board()
    b.push_uci("e2e4"); b.push_uci("e7e5")
    assert t.observe(b.board_fen())
    assert t.board.fen() == b.fen()
    assert t.board.move_stack == b.move_stack


def test_initial_mismatch_does_not_invent_turn():
    t = PositionTracker(chess.STARTING_FEN)
    b = chess.Board(); b.push_uci("e2e4")
    assert not t.observe(b.board_fen())
    assert t.board.fen() == chess.STARTING_FEN


def test_castling_and_promotion():
    for fen, uci in [("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
                     ("7k/P7/8/8/8/8/8/7K w - - 0 1", "a7a8q")]:
        t = PositionTracker(fen)
        assert t.observe(t.board.board_fen())
        b = chess.Board(fen); b.push_uci(uci)
        assert t.observe(b.board_fen())
        assert t.board.fen() == b.fen()
