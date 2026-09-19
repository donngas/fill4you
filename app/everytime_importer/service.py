from collections.abc import Callable
from datetime import time

import cv2
import numpy as np

from app.everytime_importer.schemas import EverytimeImportBlock, TimetableImportPreview

ADAPTER_VERSION = "everytime-export-v1"
FIRST_HOUR = 9
MIN_CLASS_QUARTERS = 1

# An OCR implementation receives a BGR crop and returns (title, confidence).  It is deliberately
# injected: geometry remains deterministic, while the application can select an on-device Korean
# OCR backend without coupling the adapter to a cloud service.
TitleReader = Callable[[np.ndarray], tuple[str | None, float]]


class EverytimeParseError(ValueError):
    pass


def parse_everytime_image(
    image_bytes: bytes,
    *,
    title_reader: TitleReader | None = None,
) -> TimetableImportPreview:
    """Parse a canonical Everytime export into editable timetable blocks.

    The timetable is located from its grid, so exported images may have a different resolution,
    height, or number of visible weekday columns.  Weekdays always begin with Monday in Everytime.
    """
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise EverytimeParseError("The uploaded file is not a readable image")

    grid = _detect_grid(image)
    blocks: list[EverytimeImportBlock] = []
    for weekday in range(grid.day_count):
        x0 = round(grid.left + weekday * grid.day_width)
        x1 = round(grid.left + (weekday + 1) * grid.day_width)
        for top, bottom in _occupied_runs(image, x0, x1, grid):
            start_quarter = _snap_quarter((top - grid.top) / grid.hour_height * 4)
            end_quarter = _snap_quarter((bottom - grid.top) / grid.hour_height * 4)
            if end_quarter - start_quarter < MIN_CLASS_QUARTERS:
                continue
            title, title_confidence = _read_title(image, x0, x1, top, bottom, title_reader)
            blocks.append(
                EverytimeImportBlock(
                    title=title or "Untitled class",
                    weekday=weekday,
                    start_time=_quarter_to_time(start_quarter),
                    end_time=_quarter_to_time(end_quarter),
                    geometry_confidence=1.0,
                    title_confidence=title_confidence,
                )
            )

    warnings: list[str] = []
    if title_reader is None and blocks:
        warnings.append("Course titles need Korean OCR before this preview can be confirmed.")
    if not blocks:
        warnings.append("No class blocks were detected in this Everytime export.")
    return TimetableImportPreview(ADAPTER_VERSION, tuple(blocks), tuple(warnings))


class _Grid:
    def __init__(
        self, left: float, day_width: float, day_count: int, top: float, hour_height: float
    ):
        self.left = left
        self.day_width = day_width
        self.day_count = day_count
        self.top = top
        self.hour_height = hour_height


def _detect_grid(image: np.ndarray) -> _Grid:
    height, width = image.shape[:2]
    neutral = _neutral_grid_mask(image)
    vertical_score = neutral.sum(axis=0)
    left_candidates = np.where(vertical_score > height * 0.55)[0]
    left_candidates = left_candidates[
        (left_candidates > width * 0.02) & (left_candidates < width * 0.09)
    ]
    if not len(left_candidates):
        raise EverytimeParseError("Could not locate the Everytime weekday grid")
    left = float(np.median(left_candidates))

    # Everytime displays five, six, or seven sequential weekday columns.  The correct count is
    # the lattice whose internal dividers best coincide with neutral vertical grid lines.
    best: tuple[float, int, float] | None = None
    for day_count in range(5, 8):
        day_width = (width - left) / day_count
        positions = [round(left + day_width * index) for index in range(day_count)]
        score = sum(_window_max(vertical_score, position, 3) / height for position in positions)
        if best is None or score > best[0]:
            best = (score, day_count, day_width)
    assert best is not None
    score, day_count, day_width = best
    if score < day_count * 0.35:
        raise EverytimeParseError("The weekday grid does not match an Everytime export")

    horizontal_score = neutral.sum(axis=1)
    horizontal_lines = _line_centers(horizontal_score, width * 0.5)
    top_candidates = [line for line in horizontal_lines if height * 0.01 < line < height * 0.12]
    if not top_candidates:
        raise EverytimeParseError("Could not locate the 09:00 grid line")
    top = top_candidates[0]
    next_candidates = [
        line for line in horizontal_lines if top + height * 0.04 < line < top + height * 0.2
    ]
    if not next_candidates:
        raise EverytimeParseError("Could not determine the Everytime hourly scale")
    next_line = next_candidates[0]
    hour_height = next_line - top
    if hour_height < height * 0.04:
        raise EverytimeParseError("The detected hourly scale is invalid")
    return _Grid(left, day_width, day_count, top, hour_height)


def _neutral_grid_mask(image: np.ndarray) -> np.ndarray:
    maximum = image.max(axis=2)
    minimum = image.min(axis=2)
    # Everytime uses neutral gray grid lines in both themes.  Light exports use a pale gray
    # (roughly RGB 230), whereas dark exports use RGB 49 over an RGB 17 background.  Looking
    # for both ranges keeps class tiles out of the lattice score: their coloured fills have a
    # substantially wider channel spread.
    neutral = (maximum - minimum) < 10
    light_grid = (maximum > 180) & (maximum < 250)
    dark_grid = (maximum > 35) & (maximum < 100)
    return neutral & (light_grid | dark_grid)


def _window_max(values: np.ndarray, center: int, radius: int) -> float:
    return float(values[max(0, center - radius) : center + radius + 1].max(initial=0))


def _line_centers(scores: np.ndarray, threshold: float) -> list[float]:
    """Collapse the two-to-three raster rows of each grid line into one position."""
    indexes = np.where(scores > threshold)[0]
    if not len(indexes):
        return []
    groups: list[list[int]] = [[int(indexes[0])]]
    for index in indexes[1:]:
        if index <= groups[-1][-1] + 1:
            groups[-1].append(int(index))
        else:
            groups.append([int(index)])
    return [float(np.mean(group)) for group in groups]


def _occupied_runs(image: np.ndarray, x0: int, x1: int, grid: _Grid) -> list[tuple[float, float]]:
    # Sample the central 60% of a day column; dividers and overlapping class edges are excluded.
    inset = max(3, round((x1 - x0) * 0.2))
    column = image[:, x0 + inset : x1 - inset]
    hsv = cv2.cvtColor(column, cv2.COLOR_BGR2HSV)
    colorful = hsv[:, :, 1] > 45
    occupied = colorful.mean(axis=1) > 0.42
    # White lettering creates short holes in an otherwise solid class rectangle.  Close only those
    # holes; the kernel remains much shorter than the smallest supported 15-minute block.
    closing_height = max(3, round(grid.hour_height * 0.18))
    occupied = cv2.morphologyEx(
        occupied.astype(np.uint8)[:, None],
        cv2.MORPH_CLOSE,
        np.ones((closing_height, 1), dtype=np.uint8),
    ).ravel().astype(bool)
    occupied[: max(0, round(grid.top))] = False

    runs: list[tuple[float, float]] = []
    start: int | None = None
    for index, is_occupied in enumerate(occupied):
        if is_occupied and start is None:
            start = index
        elif not is_occupied and start is not None:
            if index - start >= grid.hour_height / 5:
                runs.append((float(start), float(index)))
            start = None
    if start is not None and len(occupied) - start >= grid.hour_height / 5:
        runs.append((float(start), float(len(occupied))))
    return _merge_nearby_runs(runs, grid.hour_height)


def _merge_nearby_runs(
    runs: list[tuple[float, float]], hour_height: float
) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] < hour_height * 0.08:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _read_title(
    image: np.ndarray,
    x0: int,
    x1: int,
    top: float,
    bottom: float,
    title_reader: TitleReader | None,
) -> tuple[str | None, float]:
    if title_reader is None:
        return None, 0.0
    # Read the complete tile.  The title reader removes the lower building/room lines; retaining
    # the full tile prevents a partially visible building name from being mistaken for a title.
    crop = image[round(top) : round(bottom), x0 + 3 : x1 - 3]
    title, confidence = title_reader(crop)
    return (title.strip() if title else None), confidence


def _snap_quarter(value: float) -> int:
    return int(round(value))


def _quarter_to_time(quarter: int) -> time:
    minutes = FIRST_HOUR * 60 + quarter * 15
    return time(minutes // 60, minutes % 60)
