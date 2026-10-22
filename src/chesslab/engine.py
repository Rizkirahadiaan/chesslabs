from __future__ import annotations

from pathlib import Path
import chess
import chess.engine
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
import random
import math
import subprocess
import sys

from .config import STRENGTHS


def _open_engine(executable: Path):
    # A windowed portable app must not open a console for the UCI process.
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    return chess.engine.SimpleEngine.popen_uci(str(executable), timeout=10, **options)


@dataclass(frozen=True)
class Advice:
    fen: str
    move: chess.Move
    score: str
    line: str
    milliseconds: float
    depth: int
    complexity: str = ""


def _natural_move_priority(board: chess.Board, move: chess.Move) -> int:
    """Simple positional preferences, used ONLY after engine quality filtering."""
    piece = board.piece_type_at(move.from_square)
    home_rank = 0 if board.turn == chess.WHITE else 7
    priority = 0
    if board.is_castling(move):
        priority += 8
    if piece in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) == home_rank:
        priority += 5
    if move.to_square in (chess.D4, chess.E4, chess.D5, chess.E5):
        priority += 2
    if board.is_capture(move):
        priority += 2
        if board.move_stack and board.peek().to_square == move.to_square:
            priority += 3
    undeveloped = sum(board.piece_type_at(chess.square(file, home_rank)) in
                      (chess.KNIGHT, chess.BISHOP) for file in (1, 2, 5, 6))
    if piece == chess.QUEEN and undeveloped >= 2:
        priority -= 4
    return priority


def _position_complexity(board, candidates):
    valid = [item for item in candidates if item.get("pv")
             and item["pv"][0] in board.legal_moves and "score" in item
             and item.get("depth", 0) >= 6
             and not item.get("lowerbound") and not item.get("upperbound")]
    if len(valid) < 2:
        return "Sedang"
    valid.sort(key=lambda item: item["score"].pov(board.turn), reverse=True)
    scores = [item["score"].pov(board.turn) for item in valid]
    if scores[0].mate() == 1:
        return "Mudah"
    if any(score.is_mate() for score in scores) or board.is_check():
        return "Rumit"
    gap = scores[0].score() - scores[1].score()
    if gap >= 150:
        return "Mudah"
    tactical = any(board.is_capture(item["pv"][0]) or board.gives_check(item["pv"][0])
                   or item["pv"][0].promotion for item in valid)
    if gap <= 30 or tactical:
        return "Rumit"
    return "Sedang"


class AnalysisService:
    """One UCI process, used exclusively on one worker; GUI never blocks on it."""
    def __init__(self, executable: Path):
        self.executable = executable
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stockfish")
        self.engine = None
        self.closed = False
        self.rng = random.Random()

    def submit(self, board: chess.Board, seconds: float, strength: str = "Maksimal",
               human_style: bool = False, adaptive_timing: bool = False):
        if self.closed:
            raise RuntimeError("Engine sudah ditutup")
        if strength not in STRENGTHS:
            raise ValueError("Tingkat kecerdasan tidak dikenal")
        if not isinstance(human_style, bool):
            raise ValueError("human_style harus true atau false")
        if not isinstance(adaptive_timing, bool):
            raise ValueError("adaptive_timing harus true atau false")
        return self.pool.submit(self._analyse, board.copy(), seconds, strength, human_style, adaptive_timing)

    def _analyse(self, board, seconds, strength="Maksimal", human_style=False, adaptive_timing=False):
        started = perf_counter()
        if self.engine is None:
            self.engine = _open_engine(self.executable)
            self.engine.configure({"Threads": 2, "Hash": 128})
        complexity = ""
        if adaptive_timing:
            seconds, complexity = self._adaptive_budget(board, seconds)
        skill = {"Menengah": 10, "Pemula": 0}.get(strength, 20)
        self.engine.configure({"Skill Level": skill, "UCI_LimitStrength": False})
        if strength in ("Menengah", "Pemula"):
            # Skill Level affects the played move, not necessarily the first PV.
            result = self.engine.play(board, chess.engine.Limit(time=seconds * .65))
            if result.move not in board.legal_moves:
                raise RuntimeError("Stockfish tidak mengembalikan langkah legal")
            self.engine.configure({"Skill Level": 20})
            info = self.engine.analyse(board, chess.engine.Limit(time=seconds * .35),
                                       root_moves=[result.move])
        elif strength == "Blunder 15%" and self.rng.random() < .15:
            candidates = self.engine.analyse(board, chess.engine.Limit(time=seconds),
                                              multipv=board.legal_moves.count())
            candidates = [item for item in candidates if item.get("pv")
                          and item["pv"][0] in board.legal_moves and "score" in item]
            if not candidates:
                raise RuntimeError("Stockfish tidak mengembalikan langkah legal")
            candidates.sort(key=lambda item: item["score"].pov(board.turn).score(mate_score=100000),
                            reverse=True)
            best = candidates[0]["score"].pov(board.turn).score(mate_score=100000)
            weaker = [item for item in candidates[1:]
                      if best - item["score"].pov(board.turn).score(mate_score=100000) >= 150]
            # Prefer a loss of >= 1.5 pawns; forced/equal positions may not offer one.
            info = self.rng.choice(weaker) if weaker else candidates[-1]
        else:
            info = self.engine.analyse(board, chess.engine.Limit(time=seconds))
            if strength == "Human":
                info = self._human_level_advice(board, seconds, info)
            elif human_style:
                info = self._human_advice(board, seconds, info)
        pv = info.get("pv", [])
        if not pv or pv[0] not in board.legal_moves:
            raise RuntimeError("Stockfish tidak mengembalikan langkah legal")
        score = info["score"].pov(board.turn)
        value = f"Mat {score.mate():+d}" if score.is_mate() else f"{score.score()/100:+.2f}"
        trial = board.copy()
        line = []
        for move in pv[:6]:
            line.append(trial.san(move)); trial.push(move)
        return Advice(board.fen(), pv[0], value, "  ".join(line),
                      (perf_counter()-started)*1000, info.get("depth", 0), complexity)

    def _adaptive_budget(self, board, seconds):
        # A short full-strength probe allocates actual search time, without sleep.
        if board.legal_moves.count() <= 1:
            return max(.04, seconds * .5), "Mudah"
        probe_time = min(.12, seconds * .25)
        self.engine.configure({"Skill Level": 20, "UCI_LimitStrength": False})
        candidates = self.engine.analyse(board, chess.engine.Limit(time=probe_time),
                                         multipv=min(3, board.legal_moves.count()))
        complexity = _position_complexity(board, candidates)
        factor = {"Mudah": .6, "Sedang": 1., "Rumit": 2.}[complexity]
        return max(.04, seconds * factor - probe_time), complexity

    def _human_level_advice(self, board, seconds, baseline):
        """Weighted variety among strong moves, with a bounded estimated loss."""
        original = baseline["score"].pov(board.turn)
        if original.is_mate() or board.legal_moves.count() <= 1:
            return baseline
        candidates = self.engine.analyse(
            board, chess.engine.Limit(time=seconds * 3),
            multipv=min(5, board.legal_moves.count()))
        candidates = [item for item in candidates
                      if item.get("pv") and item["pv"][0] in board.legal_moves
                      and "score" in item and item.get("depth", 0) >= min(8, baseline.get("depth", 8))
                      and not item.get("lowerbound") and not item.get("upperbound")]
        if not candidates:
            return baseline
        winning_mates = [item for item in candidates
                         if item["score"].pov(board.turn).is_mate()
                         and item["score"].pov(board.turn) > chess.engine.Cp(0)]
        if winning_mates:
            return max(winning_mates, key=lambda item: item["score"].pov(board.turn))
        candidates = [item for item in candidates if not item["score"].pov(board.turn).is_mate()]
        if not candidates:
            return baseline
        best = max(original.score(), max(item["score"].pov(board.turn).score() for item in candidates))
        # Be stricter while escaping check and in sparse endgames.
        tolerance = 15 if board.is_check() or len(board.piece_map()) <= 10 else 35
        eligible = [item for item in candidates
                    if best - item["score"].pov(board.turn).score() <= tolerance]
        if not eligible:
            return baseline
        weights = [math.exp(-(best - item["score"].pov(board.turn).score()) / 18)
                   * math.exp(_natural_move_priority(board, item["pv"][0]) / 6)
                   for item in eligible]
        return self.rng.choices(eligible, weights=weights, k=1)[0]

    def _human_advice(self, board, seconds, baseline):
        # Keep the full original search budget. Extra MultiPV work may take up
        # to 3x that budget; incomplete/shallow comparisons retain the baseline.
        score = baseline["score"].pov(board.turn)
        depth = baseline.get("depth", 0)
        if (score.is_mate() or depth <= 0 or board.is_check()
                or board.legal_moves.count() <= 1):
            return baseline
        candidates = self.engine.analyse(
            board, chess.engine.Limit(time=seconds * 3, depth=depth),
            multipv=min(3, board.legal_moves.count()))
        if not candidates or any(
                not item.get("pv") or item["pv"][0] not in board.legal_moves
                or "score" not in item or item.get("depth", 0) < depth
                or item.get("lowerbound") or item.get("upperbound")
                for item in candidates):
            return baseline
        scores = [item["score"].pov(board.turn) for item in candidates]
        # Tactical mate lines retain the ordinary search's recommendation.
        if any(value.is_mate() for value in scores):
            return baseline
        best = max(value.score() for value in scores)
        if best < score.score():
            return baseline
        # Zero centipawn tolerance: style never deliberately buys a weaker eval.
        equal_best = [item for item, value in zip(candidates, scores) if value.score() == best]
        return max(equal_best, key=lambda item: _natural_move_priority(board, item["pv"][0]))

    def _quit(self):
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def close(self):
        if not self.closed:
            self.closed = True
            self.pool.submit(self._quit)
            self.pool.shutdown(wait=False)


class Stockfish:
    def __init__(self, executable: Path) -> None:
        if not executable.is_file():
            raise FileNotFoundError(f"Stockfish executable not found: {executable}")
        self.engine = _open_engine(executable)

    def best_move(self, board: chess.Board, depth: int, seconds: float | None = None) -> tuple[chess.Move, str]:
        info = self.engine.analyse(board, chess.engine.Limit(depth=depth, time=seconds))
        pv = info.get("pv")
        if not pv:
            raise RuntimeError("Stockfish returned no principal variation")
        score = info["score"].pov(board.turn)
        return pv[0], score.score(mate_score=100000).__str__()

    def close(self) -> None:
        self.engine.quit()
