"""Join an observed game without inventing unseen move history."""
import chess

from .board import placement_fen
from .tracker import PositionTracker


def possible_boards(placement, turn="auto"):
    """Unknown castling/EP rights are omitted; exact FEN remains the override."""
    boards = []
    for colour in ("white", "black") if turn == "auto" else (turn,):
        try:
            board = chess.Board(f"{placement} {'w' if colour == 'white' else 'b'} - - 0 1")
        except ValueError:
            continue
        if board.is_valid():
            boards.append(board)
    return boards


def orient_midgame(placement, orientation, mode="auto"):
    board = chess.Board(f"{placement} w - - 0 1")
    flipped = placement_fen({63-s: piece.symbol() for s, piece in board.piece_map().items()})
    alternatives = [(placement, orientation),
                    (flipped, "black" if orientation == "white" else "white")]
    alternatives = [(p, o) for p, o in alternatives
                    if (mode == "auto" or mode == o) and possible_boards(p)]
    if len(alternatives) == 1:
        return alternatives[0]
    if len(alternatives) != 2:
        return None
    # Home-rank pawns provide orientation evidence, not the side to move.
    # Sparse/endgame positions need an explicit orientation instead of guessing.
    def evidence(item):
        b = possible_boards(item[0])[0]
        return (sum(chess.square_rank(s) in (1, 2) for s in b.pieces(chess.PAWN, chess.WHITE))
                + sum(chess.square_rank(s) in (5, 6) for s in b.pieces(chess.PAWN, chess.BLACK)))
    alternatives.sort(key=evidence, reverse=True)
    return alternatives[0] if evidence(alternatives[0]) - evidence(alternatives[1]) >= 3 else None


class MidgameBootstrap:
    def __init__(self):
        self.boards = []

    def observe(self, placement, turn="auto"):
        if turn == "auto" and self.boards:
            matches = {}
            for previous in self.boards:
                for move in list(previous.legal_moves):
                    trial = previous.copy()
                    trial.push(move)
                    if trial.board_fen() == placement:
                        matches[trial.fen()] = trial
            if len(matches) == 1:
                return self._tracker(next(iter(matches.values())))
        boards = possible_boards(placement, turn)
        self.boards = boards
        # Check may prove the turn; otherwise wait or accept the user's choice.
        if len(boards) == 1:
            return self._tracker(boards[0])
        return None

    @staticmethod
    def _tracker(board):
        tracker = PositionTracker(board.fen(), allow_opening=True)
        tracker.board = board
        tracker.synced = True
        tracker.partial_history = True
        return tracker
