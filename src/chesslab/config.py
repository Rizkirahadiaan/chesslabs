from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

STRENGTHS = ("Maksimal", "Human", "Menengah", "Pemula", "Blunder 15%")


@dataclass(frozen=True)
class BoardBox:
    left: int
    top: int
    right: int
    bottom: int
    orientation: str = "white"

    @property
    def square_size(self) -> float:
        return min((self.right - self.left) / 8, (self.bottom - self.top) / 8)


@dataclass(frozen=True)
class Settings:
    stockfish_path: Path
    allowed_window_titles: tuple[str, ...]
    templates_dir: Path
    runtime_dir: Path
    min_template_score: float
    stable_frames: int
    poll_interval_seconds: float
    board: BoardBox
    player_colour: str = "auto"
    orientation_mode: str = "auto"
    auto_start: bool = True
    engine_strength: str = "Maksimal"
    startup_turn: str = "auto"
    marker_size: int = 5
    marker_opacity: float = .45
    overlay_style: str = "dots"
    human_style: bool = False
    adaptive_timing: bool = False


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    root = config_path.parent
    board = BoardBox(**raw["board"])
    player_colour = raw.get("player_colour", "auto")
    orientation_mode = raw.get("orientation_mode", "auto")
    auto_start = raw.get("auto_start", True)
    engine_strength = raw.get("engine_strength", "Maksimal")
    human_style = raw.get("human_style", False)
    adaptive_timing = raw.get("adaptive_timing", False)
    if not isinstance(adaptive_timing, bool):
        raise ValueError("adaptive_timing harus true atau false")
    if not isinstance(human_style, bool):
        raise ValueError("human_style harus true atau false")
    marker_size = raw.get("marker_size", 5)
    marker_opacity = raw.get("marker_opacity", .45)
    overlay_style = raw.get("overlay_style", "dots")
    if overlay_style not in ("dots", "shadow"):
        raise ValueError("overlay_style harus 'dots' atau 'shadow'")
    if type(marker_size) is not int or not 3 <= marker_size <= 10:
        raise ValueError("marker_size harus bilangan bulat 3 sampai 10 piksel")
    if type(marker_opacity) not in (int, float) or not .15 <= marker_opacity <= .80:
        raise ValueError("marker_opacity harus antara 0.15 dan 0.80")
    if engine_strength not in STRENGTHS:
        raise ValueError("engine_strength harus salah satu: " + ", ".join(STRENGTHS))
    if not isinstance(auto_start, bool):
        raise ValueError("auto_start must be true or false")
    if orientation_mode not in {"auto", "white", "black"}:
        raise ValueError("orientation_mode must be 'auto', 'white' or 'black'")
    if player_colour not in {"auto", "white", "black"}:
        raise ValueError("player_colour must be 'auto', 'white' or 'black'")
    if board.orientation not in {"white", "black"}:
        raise ValueError("board.orientation must be 'white' or 'black'")
    if board.right <= board.left or board.bottom <= board.top:
        raise ValueError("board coordinates are invalid")
    return Settings(
        stockfish_path=(root / raw["stockfish_path"]).resolve(),
        allowed_window_titles=tuple(raw["allowed_window_titles"]),
        templates_dir=(root / raw.get("templates_dir", "templates")).resolve(),
        runtime_dir=(root / raw.get("runtime_dir", "runtime")).resolve(),
        min_template_score=float(raw.get("min_template_score", 0.74)),
        stable_frames=int(raw.get("stable_frames", 2)),
        poll_interval_seconds=float(raw.get("poll_interval_seconds", 0.35)),
        board=board,
        player_colour=player_colour,
        orientation_mode=orientation_mode,
        auto_start=auto_start,
        engine_strength=engine_strength,
        human_style=human_style,
        adaptive_timing=adaptive_timing,
        marker_size=marker_size,
        marker_opacity=float(marker_opacity),
        overlay_style=overlay_style,
    )
