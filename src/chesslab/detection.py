"""Find a flat-colour 2D chessboard from repeated square backgrounds."""
from collections import Counter
import cv2
import numpy as np

from .config import BoardBox


def detect_board(rgb: np.ndarray, orientation="white") -> BoardBox:
    # Quantized dominant colours reduce the search space without assuming a theme.
    small = rgb[::4, ::4, :3] // 8
    colours = Counter(map(tuple, small.reshape(-1, 3))).most_common(18)
    candidates = []
    pixels = rgb[:, :, :3].astype(np.int16)
    for colour, _ in colours:
        target = np.asarray(colour, dtype=np.int16) * 8 + 4
        mask = (np.max(np.abs(pixels - target), axis=2) <= 7).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        boxes = []
        for x, y, w, h, area in stats[1:]:
            if min(w, h) >= 35 and abs(w-h) <= 3 and area > w*h*.28:
                boxes.append((int(x), int(y), int(w), int(h)))
        searched_sizes = set()
        for seed in boxes:
            size = (seed[2] + seed[3]) / 2
            if size in searched_sizes:
                continue
            searched_sizes.add(size)
            group = [b for b in boxes if abs(b[2]-size) <= 2 and abs(b[3]-size) <= 2]
            if len(group) < 14:
                continue
            left, top = min(b[0] for b in group), min(b[1] for b in group)
            aligned = [b for b in group if 0 <= (b[0]-left)/size < 8 and 0 <= (b[1]-top)/size < 8
                       and abs((b[0]-left)/size-round((b[0]-left)/size)) < .08
                       and abs((b[1]-top)/size-round((b[1]-top)/size)) < .08]
            right, bottom = round(left + 8*size), round(top + 8*size)
            if len(aligned) >= 14 and right <= rgb.shape[1] and bottom <= rgb.shape[0]:
                candidates.append((len(aligned), BoardBox(left, top, right, bottom, orientation)))
    if not candidates:
        raise ValueError("Papan tidak ditemukan. Tampilkan seluruh papan 2D, atau gunakan kalibrasi manual.")
    return max(candidates, key=lambda item: (item[0], item[1].right-item[1].left))[1]
