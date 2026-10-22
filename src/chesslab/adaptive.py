"""Pure state rules for orientation changes and new-game detection."""
from copy import deepcopy
import chess
from .tracker import PositionTracker


class RecoveryGate:
    """Wait out animations; rate-limit expensive recovery scans."""
    def __init__(self):
        self.failed_since = None

    def should_scan(self, now, valid, last_scan):
        if valid:
            self.failed_since = None
            return False
        if self.failed_since is None:
            self.failed_since = now
        return now-self.failed_since >= 1.0 and now-last_scan >= 3.0


def resolve_position(tracker, placement):
    """Return a candidate tracker and reset flag, without mutating live history."""
    candidate = deepcopy(tracker)
    if candidate.observe(placement):
        return candidate, False
    opening = PositionTracker(chess.STARTING_FEN, allow_opening=True)
    if opening.observe(placement):
        return opening, True
    return None, False
