import numpy as np
from chesslab.detection import detect_board


def test_detect_board_offset_with_pieces():
    image = np.zeros((800, 1000, 3), np.uint8)
    for row in range(8):
        for col in range(8):
            x, y = 200+col*60, 90+row*60
            image[y:y+60, x:x+60] = (235, 235, 205) if (row+col)%2 == 0 else (120, 150, 80)
            if row in (0, 1, 6, 7):
                image[y+15:y+48, x+20:x+40] = 245 if row>4 else 45
    box = detect_board(image)
    assert (box.left, box.top, box.right, box.bottom) == (200, 90, 680, 570)
