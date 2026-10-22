"""Legal state tracking; visual observations never guess turn or castling rights."""
import chess


def reconcile_opening(board: chess.Board, occupied: set[int]) -> chess.Board:
    """During setup, accept only the initial layout or one unique opening move.

    Occupancy is sufficient here: each legal first move has distinct from/to
    squares. Never infer an arbitrary midgame FEN from occupancy alone.
    """
    if set(board.piece_map()) == occupied:
        return board
    if board.fen() != chess.STARTING_FEN:
        raise ValueError("FEN tidak cocok dengan papan; sesuaikan FEN posisi saat ini.")
    matches = []
    for move in list(board.legal_moves):
        trial = board.copy()
        trial.push(move)
        if set(trial.piece_map()) == occupied:
            matches.append(trial)
    if len(matches) != 1:
        raise ValueError("Posisi bukan awal / satu langkah pembuka yang pasti. Sesuaikan FEN.")
    return matches[0]


class PositionTracker:
    def __init__(self, fen: str, allow_opening: bool = False):
        self.board = chess.Board(fen)
        if not self.board.is_valid():
            raise ValueError("FEN awal tidak valid.")
        self.synced = False
        self.allow_opening = allow_opening
        self.allow_midgame = False
        self.partial_history = False

    def observe(self, placement: str) -> bool:
        if self.board.board_fen() == placement:
            self.synced = True
            return True
        # Coach may start after either side has already moved from the supplied
        # FEN, including a black-to-move position learned during preparation.
        if not self.synced and not self.allow_opening:
            return False
        matches = []
        first_positions = []
        for move in list(self.board.legal_moves):
            first = self.board.copy()
            first.push(move)
            if first.board_fen() == placement:
                matches.append(first)
            first_positions.append(first)
        if len(matches) == 1:
            self.board = matches[0]
            self.synced = True
            return True
        if matches:
            return False
        for first in first_positions:
            # The user and bot may both move between two captured frames.
            for reply in list(first.legal_moves):
                second = first.copy()
                second.push(reply)
                if second.board_fen() == placement:
                    matches.append(second)
        if len(matches) != 1:
            return False
        self.board = matches[0]
        self.synced = True
        return True
