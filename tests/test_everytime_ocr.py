from app.everytime_importer.ocr import _correct_common_ocr_confusions


def test_strips_english_lecture_suffix_from_course_title() -> None:
    assert _correct_common_ocr_confusions("빅데이터분석영강") == "빅데이터분석"
    assert _correct_common_ocr_confusions("컴퓨터구조(영강)") == "컴퓨터구조"
