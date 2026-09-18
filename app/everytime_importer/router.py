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
from app.everytime_importer.service import EverytimeParseError, parse_everytime_image
from app.web.router import templates

router = APIRouter(prefix="/everytime", tags=["everytime-import"])
logger = logging.getLogger(__name__)


def _current_user_id(request: Request, db: Session) -> int:
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    return user.id


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
    try:
        preview = parse_everytime_image(
            await image.read(), title_reader=paddle_korean_title_reader()
        )
    except EverytimeParseError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
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
    titles: list[str] = Form(),
    weekdays: list[int] = Form(),
    start_times: list[time] = Form(),
    end_times: list[time] = Form(),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    if not titles or len({len(titles), len(weekdays), len(start_times), len(end_times)}) != 1:
        raise HTTPException(status_code=422, detail="The import preview data is incomplete")
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
        raise HTTPException(status_code=422, detail=error.errors()) from error
    busy_block_service.replace_source(db, user_id, "timetable", blocks)
    return RedirectResponse(url="/dashboard", status_code=303)
