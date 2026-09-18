import os
import re
from pathlib import Path

import numpy as np

from app.everytime_importer.service import TitleReader


class PaddleKoreanTitleReader:
    """On-device Korean OCR specialised for the title area of an Everytime class tile.

    PaddleOCR downloads its compact Korean models once on first construction.  A deployment may set
    ``FILL4YOU_PADDLEOCR_MODELS`` to a writable persistent model directory; no timetable image is
    sent to a third-party service.
    """

    def __init__(self, model_root: Path | None = None):
        from paddleocr import PaddleOCR

        root = model_root or _configured_model_root()
        kwargs: dict[str, str | bool] = {
            "lang": "korean",
            "use_angle_cls": False,
            "show_log": False,
        }
        if root is not None:
            kwargs.update(
                {
                    "det_model_dir": str(root / "det"),
                    "rec_model_dir": str(root / "rec"),
                    "cls_model_dir": str(root / "cls"),
                }
            )
        self._ocr = PaddleOCR(**kwargs)

    def __call__(self, image: np.ndarray) -> tuple[str | None, float]:
        result = self._ocr.ocr(image, cls=False)
        lines = result[0] if result else []
        if not lines:
            return None, 0.0

        # Everytime places course-name lines before building/room lines.  Do not rely on font size:
        # a wrapped title and a location can have similar bounding-box heights after rasterisation.
        parsed = []
        for box, (text, confidence) in lines:
            height = max(point[1] for point in box) - min(point[1] for point in box)
            top = min(point[1] for point in box)
            parsed.append((top, height, text.strip(), float(confidence)))
        parsed.sort(key=lambda line: line[0])
        title_lines = []
        for line in parsed:
            if title_lines and _looks_like_location(line[2]):
                break
            if line[2]:
                title_lines.append(line)
        if not title_lines:
            return None, 0.0
        title = "".join(line[2] for line in title_lines)
        return _correct_common_ocr_confusions(title), sum(
            line[3] for line in title_lines
        ) / len(title_lines)


def paddle_korean_title_reader(model_root: Path | None = None) -> TitleReader:
    return PaddleKoreanTitleReader(model_root)


def _configured_model_root() -> Path | None:
    value = os.environ.get("FILL4YOU_PADDLEOCR_MODELS")
    return Path(value) if value else None


def _looks_like_location(text: str) -> bool:
    compact = text.replace(" ", "")
    return (
        compact.endswith(("관", "호"))
        or bool(re.fullmatch(r"[A-Z]\d{2,4}", compact))
        # OCR can cut a building name before its final 관; these prefixes are Everytime's
        # location vocabulary, not course-name vocabulary.
        or compact.startswith(("정운", "애기능", "아산", "정보통신", "하나과학", "국제"))
    )


def _correct_common_ocr_confusions(title: str) -> str:
    # The Korean OCR model occasionally mistakes the first consonant of 딥러닝 at small sizes.
    return title.replace("덥러닝", "딥러닝").replace("립러닝", "딥러닝")
