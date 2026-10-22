from types import SimpleNamespace
from queue import Queue
import chess
import chess.pgn
from chesslab.adaptive import resolve_position
from chesslab.tracker import PositionTracker
from chesslab.config import BoardBox
from chesslab.coach import Coach
from chesslab.hotkeys import GlobalHotkeys
from chesslab.vision import Recognition
from chesslab.board import placement_fen


def progressed_tracker():
    t = PositionTracker(chess.STARTING_FEN)
    t.synced = True
    for uci in ('e2e4','e7e5','g1f3','b8c6'):
        t.board.push_uci(uci)
    return t


def test_new_game_does_not_mutate_prior_history():
    previous = progressed_tracker()
    before = previous.board.fen()
    result, reset = resolve_position(previous,chess.STARTING_BOARD_FEN)
    assert reset and result.board.fen() == chess.STARTING_FEN
    assert previous.board.fen() == before
    assert len(previous.board.move_stack) == 4


def test_new_game_after_white_opening():
    new = chess.Board(); new.push_uci('d2d4')
    result, reset = resolve_position(progressed_tracker(),new.board_fen())
    assert reset and result.board.fen() == new.fen()


def test_knight_repetition_not_mistaken_for_new_game():
    t = PositionTracker(chess.STARTING_FEN); t.synced = True
    t.board.push_uci('g1f3'); t.board.push_uci('g8f6')
    result, reset = resolve_position(t,chess.STARTING_BOARD_FEN)
    assert not reset
    assert result.board.fullmove_number == 3
    assert len(result.board.move_stack) == 4


def test_reset_requires_three_stable_frames():
    coach = Coach.__new__(Coach)
    coach.settings = SimpleNamespace(board=BoardBox(0,0,800,800),min_template_score=.74,stable_frames=2)
    coach.tracker = progressed_tracker()
    coach.last, coach.count = None,0
    coach.recognizer = SimpleNamespace(classified_tiles=64, recognize=lambda frame,box:
                                      (chess.STARTING_BOARD_FEN,{0:Recognition('R',1.)}))
    assert coach._process(None)[0] is None
    assert coach._process(None)[0] is None
    result = coach._process(None)
    assert result[0].fen() == chess.STARTING_FEN and result[5]
    assert not coach._process(None)[5]


def test_flip_preserves_game_and_returns_new_orientation():
    coach = Coach.__new__(Coach)
    coach.settings = SimpleNamespace(board=BoardBox(0,0,800,800),min_template_score=.74,stable_frames=2)
    coach.tracker = progressed_tracker()
    fen = coach.tracker.board.fen()
    coach.last, coach.count = None,0
    rotated = {63-s: coach.tracker.board.piece_at(s).symbol() if coach.tracker.board.piece_at(s) else None for s in chess.SQUARES}
    calls = []
    def recognize(frame, box):
        calls.append(box)
        return placement_fen(rotated), {s:Recognition(p,1.) for s,p in rotated.items()}
    coach.recognizer = SimpleNamespace(classified_tiles=64, recognize=recognize)
    assert coach._process(None)[0] is None
    result = coach._process(None)
    assert result[0].fen() == fen and result[4] == 'black' and not result[5]
    assert len(calls) == 2  # One recognition per frame, including a flip.


def test_prior_game_archive_is_recoverable(tmp_path):
    coach = Coach.__new__(Coach)
    coach.active_board = progressed_tracker().board
    coach.settings = SimpleNamespace(runtime_dir=tmp_path)
    coach._archive_game()
    files = list((tmp_path/'games').glob('*.pgn'))
    assert len(files)==1
    with files[0].open() as f:
        game = chess.pgn.read_game(f)
    assert list(game.mainline_moves()) == coach.active_board.move_stack


def test_hotkey_queue_drains_once():
    keys = GlobalHotkeys.__new__(GlobalHotkeys)
    keys.events = Queue()
    keys.events.put(('pause','')); keys.events.put(('shadow',''))
    assert keys.poll() == [('pause',''),('shadow','')]
    assert keys.poll() == []
