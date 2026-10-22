from __future__ import annotations

import chess

from .board import grid_cell
from .config import Settings
from .vision import guarded_screenshot
from .win32 import click


def execute_local_move(settings: Settings, move: chess.Move) -> None:
    """Click a move only after the target-window gate is rechecked."""
    guarded_screenshot(settings)  # Active title allowlist check immediately before input.
    start = grid_cell(move.from_square, settings.board)
    end = grid_cell(move.to_square, settings.board)
    click(*start)
    click(*end)
