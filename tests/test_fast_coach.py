from pathlib import Path
from types import SimpleNamespace
import chess
import numpy as np
from chesslab.config import BoardBox
from chesslab.vision import TemplateRecognizer, Recognition
from chesslab.coach import frame_changed
from chesslab.engine import AnalysisService
from chesslab import windowing
from chesslab.coach import Coach
from chesslab.engine import Advice
from concurrent.futures import Future


def test_cache_classifies_only_changed_tiles():
    recognizer = TemplateRecognizer.__new__(TemplateRecognizer)
    recognizer._tile_cache = {}
    calls = []
    def classify(image):
        calls.append(1)
        return Recognition(None, 1.0)
    recognizer.classify = classify
    image = np.zeros((160,160,3),np.uint8)
    box = BoardBox(0,0,160,160)
    recognizer.recognize(image, box)
    assert len(calls) == 64
    recognizer.recognize(image, box)
    assert len(calls) == 64
    image[30,30] = 255
    recognizer.recognize(image, box)
    assert len(calls) == 65


def test_panel_focus_allowed_only_outside_board(monkeypatch):
    monkeypatch.setattr(windowing, "u", SimpleNamespace(IsIconic=lambda _:False))
    monkeypatch.setattr(windowing, "foreground", lambda:2)
    box = BoardBox(10,10,810,810)
    assert windowing.board_visible(1,2,box,(820,10,1300,600))
    assert not windowing.board_visible(1,2,box,(500,10,1100,600))
    monkeypatch.setattr(windowing, "foreground", lambda:3)
    assert not windowing.board_visible(1,2,box,(820,10,1300,600))


def test_piece_change_invalidates_old_overlay_frame():
    old = np.zeros((160,160,3), np.uint8)
    new = old.copy(); new[20:35,20:35] = 255
    assert not frame_changed(old,old.copy())
    assert frame_changed(old,new)


def test_engine_reuses_one_process_and_quits(monkeypatch):
    import chess.engine
    events = []
    class Fake:
        def configure(self, options): events.append("configure")
        def analyse(self, board, limit):
            return {"pv":[next(iter(board.legal_moves))], "score":chess.engine.PovScore(chess.engine.Cp(34),board.turn), "depth":12}
        def quit(self): events.append("quit")
    def open_engine(*args, **kwargs):
        events.append("open"); return Fake()
    monkeypatch.setattr(chess.engine.SimpleEngine,"popen_uci",open_engine)
    service = AnalysisService(Path("fake.exe"))
    board = chess.Board()
    first = service.submit(board,.18).result(timeout=2)
    board.push_uci("e2e4")
    second = service.submit(board,.18).result(timeout=2)
    service.close(); service.pool.shutdown(wait=True)
    assert events.count("open") == 1
    assert events.count("quit") == 1
    assert first.fen != second.fen
    assert first.score == "+0.34"


def test_stale_engine_result_never_reaches_overlay():
    coach = Coach.__new__(Coach)
    old = chess.Board()
    coach.active_board = old.copy(); coach.active_board.push_uci("e2e4")
    coach.closed, coach.running, coach.generation = False, True, 3
    coach.engine_token = (3, old.fen(), "Cepat")
    coach.mode = SimpleNamespace(get=lambda:"Cepat")
    coach.settings = SimpleNamespace(engine_strength="Maksimal", human_style=False, adaptive_timing=False)
    coach.root = SimpleNamespace(after=lambda *args:None)
    coach.advice = None
    coach.position_ready = False
    shown = []
    coach._show_advice = lambda:shown.append(True)
    coach.engine_future = Future()
    coach.engine_future.set_result(Advice(old.fen(),chess.Move.from_uci("e2e4"),"+0.3","e4",180,12))
    coach._engine_tick()
    assert shown == []
    assert coach.advice is None
    assert coach.engine_future is None
