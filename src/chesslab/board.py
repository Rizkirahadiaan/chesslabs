from __future__ import annotations

from dataclasses import dataclass
import chess

from .config import BoardBox

PIECE_NAME_TO_SYMBOL = {
    "white_pawn": "P", "white_knight": "N", "white_bishop": "B",
    "white_rook": "R", "white_queen": "Q", "white_king": "K",
    "black_pawn": "p", "black_knight": "n", "black_bishop": "b",
    "black_rook": "r", "black_queen": "q", "black_king": "k",
}


def square_at(row: int, col: int, orientation: str) -> chess.Square:
    """Map displayed grid row/column to a python-chess square."""
    if orientation == "white":
        return chess.square(col, 7 - row)
    return chess.square(7 - col, row)


def grid_cell(square: chess.Square, box: BoardBox) -> tuple[float, float]:
    file, rank = chess.square_file(square), chess.square_rank(square)
    if box.orientation == "white":
        col, row = file, 7 - rank
    else:
        col, row = 7 - file, rank
    width, height = (box.right - box.left) / 8, (box.bottom - box.top) / 8
    return box.left + (col + .5) * width, box.top + (row + .5) * height


def placement_fen(cells: dict[chess.Square, str | None]) -> str:
    rows: list[str] = []
    for rank in range(7, -1, -1):
        empty = 0
        row = ""
        for file in range(8):
            piece = cells.get(chess.square(file, rank))
            if piece is None:
                empty += 1
            else:
                row += str(empty) if empty else ""
                empty = 0
                row += piece
        rows.append(row + (str(empty) if empty else ""))
    return "/".join(rows)


def position_from_placement(placement: str, turn: bool = chess.WHITE) -> chess.Board:
    """Build a board only for display; authoritative state comes from legal moves."""
    return chess.Board(f"{placement} {'w' if turn else 'b'} - - 0 1")


def apply_visible_move(previous: chess.Board, observed_placement: str) -> chess.Move | None:
    """Find the unique legal move whose piece layout equals the observed image."""
    matches: list[chess.Move] = []
    for move in previous.legal_moves:
        trial = previous.copy(stack=False)
        trial.push(move)
        if trial.board_fen() == observed_placement:
            matches.append(move)
    return matches[0] if len(matches) == 1 else None
