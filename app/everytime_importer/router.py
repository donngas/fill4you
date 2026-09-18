import logging
from datetime import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.busy_blocks import service as busy_block_service
from app.busy_blocks.schemas import BusyBlockInput
from app.core.csrf import get_csrf_token, require_csrf
from app.core.database import get_db
from app.everytime_importer.ocr import paddle_korean_title_reader
from app.everytime_importer.schemas import EverytimeImportBlock, TimetableImportPreview
from app.everytime_importer.service import EverytimeParseError, parse_everytime_image
from app.web.router import templates

router = APIRouter(prefix="/everytime", tags=["everytime-import"])
logger = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TOO_LARGE_MESSAGE = (
    "이미지 파일은 최대 20MB까지 업로드할 수 있습니다. 더 작은 JPG 또는 PNG를 선택해 주세요."
)


def _current_user_id(request: Request, db: Session) -> int:
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    return user.id


def _import_preview_from_form(
    titles: list[str], weekdays: list[int], start_times: list[time], end_times: list[time]
) -> TimetableImportPreview:
    return TimetableImportPreview(
        adapter="everytime-import-confirmation",
        blocks=tuple(
            EverytimeImportBlock(
                title=title,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                geometry_confidence=1.0,
            )
            for title, weekday, start_time, end_time in zip(
                titles, weekdays, start_times, end_times, strict=True
            )
        ),
        warnings=(),
    )


def _import_validation_message(error: ValidationError) -> str:
    message = error.errors()[0]["msg"].removeprefix("Value error, ")
    messages = {
        "A title is required": "강의명을 입력해 주세요.",
        "A recurring block needs a weekday, start time, and end time": (
            "강의의 요일과 시작·종료 시간을 입력해 주세요."
        ),
        "A recurring block cannot start and end at the same time": (
            "강의의 시작과 종료 시간은 같을 수 없습니다."
        ),
    }
    return messages.get(message, "시간표 항목을 확인해 주세요.")


@router.post("/import")
async def preview_import(
    request: Request,
    image: UploadFile = File(),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    _current_user_id(request, db)
    if image.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=422, detail="Please upload a JPG or PNG image")
    if image.size is not None and image.size > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=IMAGE_TOO_LARGE_MESSAGE,
        )
    try:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=IMAGE_TOO_LARGE_MESSAGE,
            )
        preview = parse_everytime_image(image_bytes, title_reader=paddle_korean_title_reader())
    except EverytimeParseError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Everytime image import failed")
        raise HTTPException(
            status_code=503,
            detail="에브리타임 이미지 인식 모델을 준비하지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from error
    return templates.TemplateResponse(
        request,
        "everytime_import_preview.html",
        {"preview": preview, "csrf_token": get_csrf_token(request)},
    )


@router.post("/import/confirm")
def confirm_import(
    request: Request,
    replace_timetable: bool = Form(False),
    titles: list[str] = Form([]),
    weekdays: list[int] = Form([]),
    start_times: list[time] = Form([]),
    end_times: list[time] = Form([]),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    if not titles or len({len(titles), len(weekdays), len(start_times), len(end_times)}) != 1:
        request.session["block_form_error"] = (
            "시간표 미리보기 정보가 완전하지 않습니다. 이미지를 다시 불러와 주세요."
        )
        return RedirectResponse(url="/dashboard", status_code=303)
    defaults = busy_block_service.buffer_defaults(db, user_id)["timetable"]
    try:
        blocks = [
            BusyBlockInput(
                source="timetable",
                title=title,
                is_recurring=True,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                before_buffer_minutes=defaults[0],
                after_buffer_minutes=defaults[1],
            )
            for title, weekday, start_time, end_time in zip(
                titles, weekdays, start_times, end_times, strict=True
            )
        ]
    except ValidationError as error:
        return templates.TemplateResponse(
            request,
            "everytime_import_preview.html",
            {
                "preview": _import_preview_from_form(titles, weekdays, start_times, end_times),
                "csrf_token": get_csrf_token(request),
                "form_error": _import_validation_message(error),
            },
            status_code=422,
        )
    if replace_timetable:
        busy_block_service.replace_source(db, user_id, "timetable", blocks)
    else:
        busy_block_service.create_many(db, user_id, blocks)
    return RedirectResponse(url="/dashboard", status_code=303)
