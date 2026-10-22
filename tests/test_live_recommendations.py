from concurrent.futures import Future
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import chess
import pytest

from chesslab.adaptive import RecoveryGate
from chesslab.board import placement_fen
from chesslab.coach import Coach
from chesslab.config import BoardBox, Settings, load_settings
from chesslab.engine import Advice
from chesslab.tracker import PositionTracker
from chesslab.vision import Recognition


class Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_coach(monkeypatch, orientation="black", colour="auto"):
    c = Coach.__new__(Coach)
    c.settings = Settings(Path("engine"), (), Path("templates"), Path("runtime"),
                          .74, 2, .35, BoardBox(0, 0, 800, 800, orientation))
    c.colour, c.orientation, c.mode = Value(colour), Value(orientation), Value("Cepat")
    c.my_colour = c._selected_colour()
    c.running, c.closed, c.generation = True, False, 1
    c.position_ready = c.persist_layout = False
    c.active_board = c.advice = c.engine_future = c.engine_token = None
    c.tracker = PositionTracker(chess.STARTING_FEN, allow_opening=True)
    c.last, c.count, c.failures = None, 0, 0
    c.recovery, c.last_scan = RecoveryGate(), 0
    c.capture_ms, c.cycle_started = 0, perf_counter()
    c.target, c.target_rect = 7, (0, 0, 900, 900)
    c.overlay_enabled = True
    c._visible = lambda: True
    c.root = SimpleNamespace(after=lambda *args: None)
    for name in ("fen", "history", "variation", "suggestion", "metrics", "status"):
        setattr(c, name, Value())
    shown, submitted = [], []
    c.overlay = SimpleNamespace(hide=lambda: None,
                                show=lambda move, box: shown.append((move, box.orientation)))
    def submit(board, seconds, strength="Maksimal", human_style=False, adaptive_timing=False):
        future = Future()
        submitted.append((board.copy(), future))
        return future
    c.service = SimpleNamespace(submit=submit)
    monkeypatch.setattr("chesslab.coach.rect", lambda _: c.target_rect)
    return c, shown, submitted


def observe(c, board, flipped=False):
    cells = {s: board.piece_at(s).symbol() if board.piece_at(s) else None
             for s in chess.SQUARES}
    if flipped:
        cells = {63-s: symbol for s, symbol in cells.items()}
    details = {s: Recognition(symbol, 1.) for s, symbol in cells.items()}
    c.recognizer = SimpleNamespace(classified_tiles=64,
                                  recognize=lambda *args: (placement_fen(cells), details))
    for _ in range(2):
        c.future = Future()
        c.future.set_result(c._process(None))
        c._result(c.generation)


def finish_search(c, submitted, index=-1):
    board, future = submitted[index]
    move = next(iter(board.legal_moves))
    future.set_result(Advice(board.fen(), move, "+0.10", board.san(move), 10, 8))
    c._engine_tick()
    return move


@pytest.mark.parametrize("orientation,colour,expected", [
    ("black", "auto", chess.BLACK), ("white", "auto", chess.WHITE),
    ("black", "white", chess.WHITE), ("white", "black", chess.BLACK),
])
def test_player_colour_follows_orientation_unless_explicit(monkeypatch, orientation, colour, expected):
    c, _, _ = make_coach(monkeypatch, orientation, colour)
    assert c.my_colour == expected


def test_black_recommendations_follow_both_players_automatically(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch)
    board = chess.Board()
    observe(c, board)
    assert not submitted  # White moves first, even when the player is black.
    board.push_uci("e2e4")
    observe(c, board)
    first = finish_search(c, submitted)
    assert shown == [(first, "black")]

    board.push_uci("c7c5")  # The player may choose a different legal move.
    observe(c, board)
    assert c.advice is None and c.variation.get() == ""
    assert c.suggestion.get() == "Menunggu lawan"
    assert len(submitted) == 1
    board.push_uci("g1f3")
    observe(c, board)
    second = finish_search(c, submitted)
    assert len(submitted) == 2
    assert submitted[-1][0].fen() == board.fen()
    assert shown[-1] == (second, "black")


def test_stale_search_immediately_replaced_after_two_missed_plies(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch)
    board = chess.Board()
    board.push_uci("e2e4")
    observe(c, board)
    board.push_uci("c7c5")
    board.push_uci("g1f3")
    observe(c, board)
    assert len(submitted) == 1
    finish_search(c, submitted, 0)
    assert shown == []
    assert len(submitted) == 2
    assert submitted[-1][0].fen() == board.fen()
    finish_search(c, submitted)
    assert shown[-1][1] == "black"


@pytest.mark.parametrize("orientation", ["white", "black"])
def test_ignoring_advice_continues_from_actual_moves(monkeypatch, orientation):
    c, shown, submitted = make_coach(monkeypatch, orientation=orientation)
    board = chess.Board()
    if orientation == "black":
        board.push_uci("e2e4")
    observe(c, board)
    suggested = finish_search(c, submitted)
    played = next(move for move in board.legal_moves if move != suggested)
    board.push(played)
    board.push(next(iter(board.legal_moves)))
    # Both moves can occur before the next captured frame.
    observe(c, board)
    assert c.running and c.tracker.board.fen() == board.fen()
    assert submitted[-1][0].fen() == board.fen()
    assert finish_search(c, submitted) in board.legal_moves


def test_old_search_failure_does_not_stop_after_alternative_move(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch)
    board = chess.Board()
    board.push_uci("e2e4")
    observe(c, board)
    board.push_uci("c7c5")
    board.push_uci("g1f3")
    observe(c, board)
    submitted[0][1].set_exception(RuntimeError("obsolete search failed"))
    c._engine_tick()
    assert c.running and not shown
    assert len(submitted) == 2
    assert submitted[-1][0].fen() == board.fen()


@pytest.mark.parametrize("strength", ["Pemula", "Human"])
def test_strength_change_persists_and_discards_pending_advice(monkeypatch, tmp_path, strength):
    import json
    c, shown, submitted = make_coach(monkeypatch, orientation="white")
    c.path = tmp_path / "config.json"
    c.path.write_text('{"auto_start": true}')
    c.strength = Value(strength)
    observe(c, chess.Board())
    c._strength_changed()
    assert json.loads(c.path.read_text()) == {"auto_start": True, "engine_strength": strength}
    assert c.settings.engine_strength == strength
    finish_search(c, submitted, 0)
    assert not shown and len(submitted) == 2
    assert c.engine_token[-1] == strength
    finish_search(c, submitted)
    assert shown
    for _ in range(3):
        observe(c, chess.Board())
    assert len(submitted) == 2  # No re-roll on unchanged frames.


def test_human_style_toggle_persists_and_discards_pending_advice(monkeypatch, tmp_path):
    import json
    c, shown, submitted = make_coach(monkeypatch, orientation="white")
    c.path = tmp_path / "config.json"
    c.path.write_text('{"auto_start": true}')
    c.human_style = Value(True)
    observe(c, chess.Board())
    c._human_style_changed()
    assert json.loads(c.path.read_text()) == {"auto_start": True, "human_style": True}
    assert c.settings.human_style
    finish_search(c, submitted, 0)
    assert not shown and len(submitted) == 2
    finish_search(c, submitted)
    assert shown
    for _ in range(3):
        observe(c, chess.Board())
    assert len(submitted) == 2
    c.human_style.set(False)
    c._human_style_changed()
    assert not c.settings.human_style and not json.loads(c.path.read_text())["human_style"]
    assert c.advice is None and len(submitted) == 3


def test_human_style_save_failure_restores_toggle(monkeypatch, tmp_path):
    c, _, _ = make_coach(monkeypatch, orientation="white")
    c.path = tmp_path / "missing" / "config.json"
    c.human_style = Value(True)
    c._human_style_changed()
    assert not c.settings.human_style and not c.human_style.get()
    assert "belum tersimpan" in c.status.get()


def test_auto_colour_changes_after_detected_board_flip(monkeypatch):
    c, _, submitted = make_coach(monkeypatch, orientation="white")
    c.orientation.set("auto")
    c._save_layout = lambda: setattr(c, "persist_layout", False)
    board = chess.Board()
    board.push_uci("e2e4")
    observe(c, board, flipped=True)
    assert c.settings.board.orientation == "black"
    assert c.orientation.get() == "auto"
    assert c.my_colour == chess.BLACK
    assert submitted[-1][0].fen() == board.fen()


def test_start_catches_up_from_learned_black_to_move_position():
    board = chess.Board()
    board.push_uci("e2e4")
    tracker = PositionTracker(board.fen(), allow_opening=True)
    board.push_uci("c7c5")
    board.push_uci("g1f3")
    assert tracker.observe(board.board_fen())
    assert tracker.synced
    assert tracker.board.fen() == board.fen()
    assert tracker.board.turn == chess.BLACK


def test_legacy_config_defaults_to_auto_and_preserves_explicit_colour(tmp_path):
    import json
    raw = {"stockfish_path": "engine.exe", "allowed_window_titles": [],
           "board": {"left": 0, "top": 0, "right": 800, "bottom": 800,
                     "orientation": "black"}}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    assert load_settings(path).player_colour == "auto"
    assert load_settings(path).orientation_mode == "auto"
    raw["player_colour"] = "white"
    path.write_text(json.dumps(raw))
    assert load_settings(path).player_colour == "white"


def test_select_auto_preserves_concrete_board_orientation(monkeypatch, tmp_path):
    import json
    c, _, _ = make_coach(monkeypatch)
    c.path = tmp_path / "config.json"
    c.path.write_text("{}")
    c.orientation.set("auto")
    c._orientation_changed()
    assert c.pending_layout[0].orientation == "black"
    assert json.loads(c.path.read_text())["orientation_mode"] == "auto"


def test_training_auto_recognizes_black_orientation(monkeypatch):
    c, _, _ = make_coach(monkeypatch, orientation="white")
    board = chess.Board()
    board.push_uci("e2e4")
    cells = {63-s: board.piece_at(s).symbol() if board.piece_at(s) else None
             for s in chess.SQUARES}
    def recognize(frame, box):
        placement = board.board_fen() if box.orientation == "black" else placement_fen(cells)
        return placement, {s: Recognition(None, 1.) for s in chess.SQUARES}
    monkeypatch.setattr("chesslab.coach.TemplateRecognizer",
                        lambda *args: SimpleNamespace(recognize=recognize))
    assert c._training_orientation(None, c.settings.board, chess.Board()) == "black"


def test_training_auto_requires_templates_before_labelling(monkeypatch):
    c, _, _ = make_coach(monkeypatch)
    def missing(*args):
        raise FileNotFoundError("no templates")
    monkeypatch.setattr("chesslab.coach.TemplateRecognizer", missing)
    with pytest.raises(ValueError, match="belajar pertama kali"):
        c._training_orientation(None, c.settings.board, chess.Board())


def test_autostart_does_not_override_manual_pause(monkeypatch):
    c, _, _ = make_coach(monkeypatch)
    calls = []
    c.start = lambda **kwargs: calls.append(kwargs)
    c.running, c.generation = False, 0
    c._autostart()
    assert calls == [{"automatic": True}]
    c.generation = 1
    c._autostart()
    assert len(calls) == 1


def test_discovery_commits_black_board_and_starts_capture(monkeypatch):
    c, _, _ = make_coach(monkeypatch, orientation="white")
    c.orientation.set("auto")
    c.recognizer = SimpleNamespace(_tile_cache={1: "old"})
    c.coach_hwnd = 99
    monkeypatch.setattr("chesslab.coach.foreground", lambda: 7)
    cycles = []
    c._cycle = lambda token: cycles.append(token)
    future = Future()
    future.set_result(BoardBox(10, 20, 810, 820, "black"))
    c._auto_found(1, 7, c.target_rect, future)
    assert cycles == [1]
    assert c.my_colour == chess.BLACK
    assert c.orientation.get() == "auto"
    assert c.recognizer._tile_cache == {}
    assert c.persist_layout


def test_discovery_retries_and_discards_results_after_pause(monkeypatch):
    c, _, _ = make_coach(monkeypatch)
    callbacks = []
    c.root = SimpleNamespace(after=lambda delay, callback: callbacks.append((delay, callback)))
    future = Future()
    future.set_exception(ValueError("No board"))
    c._auto_found(1, 7, c.target_rect, future)
    assert callbacks[0][0] == 1000
    c.running = False
    c._auto_found(1, 7, c.target_rect, future)
    assert len(callbacks) == 1
    # The already scheduled retry is also cancelled by the pause state.
    callbacks[0][1]()
    assert len(callbacks) == 1


def test_terminal_board_then_new_match_with_colour_swap(monkeypatch):
    c, shown, submitted = make_coach(monkeypatch, orientation="white")
    c.orientation.set("auto")
    c._save_layout = lambda: setattr(c, "persist_layout", False)
    archived = []
    c._archive_game = lambda: archived.append(c.active_board.fen())
    ended = chess.Board()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        ended.push_uci(uci)
    assert ended.is_checkmate()
    c.tracker = PositionTracker(ended.fen(), allow_opening=True)
    observe(c, ended)
    assert c.running and not c.position_ready
    assert not submitted
    assert "match baru" in c.suggestion.get()
    new = chess.Board()
    new.push_uci("e2e4")
    observe(c, new, flipped=True)
    assert not submitted  # New games require a third stable frame.
    c.future = Future()
    c.future.set_result(c._process(None))
    c._result(c.generation)
    assert archived == [ended.fen()]
    assert c.running and c.my_colour == chess.BLACK
    assert c.orientation.get() == "auto"
    assert submitted[-1][0].fen() == new.fen()
    finish_search(c, submitted)
    assert shown[-1][1] == "black"


def test_adaptive_timing_toggle_persists_and_discards_pending_advice(monkeypatch, tmp_path):
    import json
    c, shown, submitted = make_coach(monkeypatch, orientation="white")
    c.path = tmp_path / "config.json"
    c.path.write_text('{"auto_start": true}')
    c.adaptive_timing = Value(True)
    observe(c, chess.Board())
    c._adaptive_timing_changed()
    assert json.loads(c.path.read_text()) == {"auto_start": True, "adaptive_timing": True}
    assert c.settings.adaptive_timing
    finish_search(c, submitted, 0)
    assert not shown and len(submitted) == 2
    finish_search(c, submitted)
    assert shown
    for _ in range(3):
        observe(c, chess.Board())
    assert len(submitted) == 2
    c.adaptive_timing.set(False)
    c._adaptive_timing_changed()
    assert not c.settings.adaptive_timing and not json.loads(c.path.read_text())["adaptive_timing"]
    assert c.advice is None and len(submitted) == 3


def test_adaptive_timing_save_failure_restores_toggle(monkeypatch, tmp_path):
    c, _, _ = make_coach(monkeypatch, orientation="white")
    c.path = tmp_path / "missing" / "config.json"
    c.adaptive_timing = Value(True)
    c._adaptive_timing_changed()
    assert not c.settings.adaptive_timing and not c.adaptive_timing.get()
    assert "belum tersimpan" in c.status.get()

