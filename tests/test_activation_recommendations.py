"""Regresi aktivasi ke rekomendasi; tidak memakai lisensi/data perangkat pengguna."""
import base64
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from uuid import uuid4

import chess
import httpx
import numpy as np
from PIL import Image
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from chesslab.coach import Coach
from chesslab.config import BoardBox, load_settings
from chesslab.detection import detect_board
from chesslab.engine import AnalysisService
from chesslab.licensing.api import LicenseAPIClient
from chesslab.licensing.manager import LicenseManager
from chesslab.licensing.verifier import LicenseTokenVerifier
from chesslab.vision import TemplateRecognizer

ROOT = Path(__file__).resolve().parents[1]


class Value:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


@pytest.fixture
def licensed_manager():
    """Grant QA sungguhan secara kriptografis, melalui API transport khusus test."""
    key = Ed25519PrivateKey.generate()
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    public = encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    device = "a" * 64
    now = int(time.time())
    header = encode(json.dumps({"alg": "EdDSA", "typ": "CLG", "kid": "qa-replay"}).encode())
    payload = encode(json.dumps(dict(v=1, product="chesslab-pc", device=device,
        license=str(uuid4()), activation=str(uuid4()), status="ACTIVE", edition="QA replay",
        activated=now-1, iat=now, exp=now+120, subscription_exp=now+3600)).encode())
    message = header + "." + payload
    token = message + "." + encode(key.sign(message.encode("ascii")))
    class Memory:
        def load(self): return {}
        def save(self, value): pass
    transport = httpx.MockTransport(lambda request: httpx.Response(200,
        json={"grant": token, "activation_secret": "qa-fixture-only"}))
    manager = LicenseManager(LicenseAPIClient("http://localhost:8080", "chesslab-pc", device, transport),
                             LicenseTokenVerifier({"qa-replay": public}, "chesslab-pc", device), Memory())
    assert not manager.entitled
    return manager


@pytest.mark.parametrize("manual_pause,auto_start,expected", [(False, True, 1), (True, True, 0), (False, False, 0)])
def test_activation_resumes_autostart_without_overriding_user_pause(licensed_manager, manual_pause, auto_start, expected):
    c = Coach.__new__(Coach)
    c.settings = SimpleNamespace(auto_start=auto_start)
    c.running = c.closed = False
    c.generation = int(manual_pause)
    c.status = Value()
    c.license_manager = licensed_manager
    pending, started = [], []
    c.root = SimpleNamespace(after=lambda delay, callback: pending.append(callback))
    c.start = lambda **kwargs: started.append(kwargs)
    c._license_changed(False, False, "Aktivasi diperlukan")
    assert c.license_manager.refresh("QA-TEST-ONLY") and c.license_manager.entitled
    c._license_changed(True, False, "Aktif")
    while pending:
        pending.pop(0)()
    assert len(started) == expected
    if expected:
        assert started == [{"automatic": True}]
    c._license_changed(True, True, "Memperbarui status")
    assert not pending


def test_revoked_license_still_stops_analysis():
    c = Coach.__new__(Coach)
    c.running = True
    c.status, c.variation, c.suggestion = Value(), Value("old"), Value()
    c.advice = object()
    c._license_was_entitled = True
    def pause(): c.running = False
    c.pause = pause
    c._license_changed(False, False, "Lisensi tidak aktif")
    assert not c.running and c.advice is None and c.variation.get() == ""
    assert c.suggestion.get() == "Lisensi tidak aktif"


@pytest.fixture
def learned_board(tmp_path, monkeypatch):
    image = Image.open(ROOT / "tests/fixtures/start-board-green.png").convert("RGB")
    frame = np.array(image)
    c = Coach.__new__(Coach)
    c.path = tmp_path / "config.json"
    raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    raw.update(templates_dir=str(ROOT / "templates"), runtime_dir=str(tmp_path / "runtime"))
    c.path.write_text(json.dumps(raw), encoding="utf-8")
    c.settings = load_settings(c.path)
    c.closed, c.running, c.generation = False, False, 1
    c.status, c.fen = Value(), Value(chess.STARTING_FEN)
    monkeypatch.setattr("chesslab.coach.ImageGrab.grab", lambda **kwargs: image)
    monkeypatch.setattr("chesslab.coach.foreground", lambda: 7)
    monkeypatch.setattr("chesslab.coach.rect", lambda _: (0, 0, 784, 784))
    c._prepare_capture(1, chess.Board(), "white")
    assert "Papan dan template siap" in c.status.get()
    c.recognizer = TemplateRecognizer(c.settings.templates_dir, c.settings.min_template_score)
    return c, frame


def test_user_board_detected_and_learned_at_original_scale(learned_board):
    c, frame = learned_board
    assert detect_board(frame) == BoardBox(0, 0, 784, 784)
    placement, detail = c.recognizer.recognize(frame, c.settings.board)
    assert placement == chess.STARTING_BOARD_FEN
    assert all(d.score >= c.settings.min_template_score for d in detail.values())
    assert len(list(c.settings.templates_dir.rglob("*.png"))) == 64
    assert c._locate(frame, (0, 0, 784, 784)) == BoardBox(0, 0, 784, 784)


def test_unmatched_theme_explains_training_without_lowering_threshold():
    c = Coach.__new__(Coach)
    from chesslab.tracker import PositionTracker
    c.settings = SimpleNamespace(board=BoardBox(0, 0, 784, 784), min_template_score=.74)
    c.tracker = PositionTracker(chess.STARTING_FEN, allow_opening=True)
    c.recognizer = TemplateRecognizer(ROOT / "templates", .74)
    frame = np.array(Image.open(ROOT / "tests/fixtures/start-board-green.png").convert("RGB"))
    with pytest.raises(ValueError, match="Deteksi & pelajari"):
        c._locate(frame, (0, 0, 784, 784))
    assert c.settings.min_template_score == .74


def test_licensed_replay_reaches_real_stockfish_and_recommendation_overlay(learned_board, licensed_manager, monkeypatch):
    engine = os.environ.get("CHESSLAB_TEST_ENGINE")
    if not engine:
        pytest.skip("CHESSLAB_TEST_ENGINE belum disediakan untuk integrasi Stockfish nyata")
    c, frame = learned_board
    c.license_manager = licensed_manager
    assert c.license_manager.refresh("QA-TEST-ONLY")
    c.running, c.position_ready = True, False
    c.last, c.count, c.advice = None, 0, None
    c.active_board = c.engine_future = c.engine_token = None
    c.colour, c.mode = Value("white"), Value("Cepat")
    c.overlay_enabled = True
    c.target, c.target_rect = 7, (0, 0, 784, 784)
    c._visible = lambda: True
    c.root = SimpleNamespace(after=lambda *args: None)
    c.suggestion, c.variation = Value(), Value()
    shown = []
    c.overlay = SimpleNamespace(hide=lambda: None, show=lambda move, box: shown.append((move, box)))
    c.service = AnalysisService(Path(engine))
    try:
        assert c._process(frame)[0] is None
        board = c._process(frame)[0]
        assert board is not None and board.fen() == chess.STARTING_FEN
        c.active_board, c.position_ready, c.my_colour = board, True, chess.WHITE
        c._request_advice(board)
        assert c.engine_future is not None
        c.engine_future.result(timeout=10)
        c._engine_tick()
        assert c.advice.move in board.legal_moves
        assert c.advice.move.uci() in c.suggestion.get()
        assert shown and shown[0][0] == c.advice.move
    finally:
        c.service.close()
        c.service.pool.shutdown(wait=True)
