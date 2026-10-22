"""Use Python filesystem paths for OpenCV images, including Unicode on Windows."""
from pathlib import Path

import cv2
import numpy as np


def read_image(path, flags=cv2.IMREAD_COLOR):
    data = Path(path).read_bytes()
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), flags) if data else None


def write_image(path, image):
    path = Path(path)
    ok, encoded = cv2.imencode(path.suffix, image)
    if ok:
        path.write_bytes(encoded.tobytes())
    return ok
