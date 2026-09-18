from datetime import time

import cv2
import numpy as np

from app.everytime_importer import parse_everytime_image


def test_parser_hands_quarter_hour_geometry_to_busy_block_contract() -> None:
    image = np.full((650, 530, 3), 255, dtype=np.uint8)
    grid_color = (230, 230, 230)
    left, day_width, top, hour_height = 30, 100, 40, 120
    for x in range(left, 531, day_width):
        cv2.line(image, (x, 0), (x, 649), grid_color, 2)
    for y in range(top, 641, hour_height):
        cv2.line(image, (0, y), (529, y), grid_color, 2)
    # Monday 09:15–10:45 and Wednesday 12:00–13:00.
    cv2.rectangle(
        image,
        (left + 3, top + 30),
        (left + day_width - 3, top + 210),
        (80, 180, 230),
        -1,
    )
    cv2.rectangle(
        image,
        (left + day_width * 2 + 3, top + 360),
        (left + day_width * 3 - 3, top + 480),
        (100, 190, 120),
        -1,
    )
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    titles = iter([("First class", 1.0), ("Second class", 1.0)])
    preview = parse_everytime_image(encoded.tobytes(), title_reader=lambda _: next(titles))

    assert [(block.weekday, block.start_time, block.end_time) for block in preview.blocks] == [
        (0, time(9, 15), time(10, 45)),
        (2, time(12), time(13)),
    ]
    assert [item.title for item in preview.to_busy_block_inputs()] == [
        "First class",
        "Second class",
    ]
