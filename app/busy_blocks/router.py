from datetime import datetime, time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.busy_blocks import service
from app.busy_blocks.schemas import BusyBlockInput
from app.core.csrf import require_csrf
from app.core.database import get_db
from app.shared.time import as_seoul_time

router = APIRouter(prefix="/blocks", tags=["busy-blocks"])


def _current_user_id(request: Request, db: Session) -> int:
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    return user.id


def _to_input(
    *,
    source: str,
    title: str,
    schedule_type: str,
    weekday: int | None,
    start_time: time | None,
    end_time: time | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    before_buffer_minutes: int,
    after_buffer_minutes: int,
    allow_google: bool,
) -> BusyBlockInput:
    if source == "google_calendar" and not allow_google:
        raise HTTPException(
            status_code=400, detail="Google Calendar blocks are imported during calendar sync"
        )
    try:
        return BusyBlockInput(
            source=source,
            title=title,
            is_recurring=schedule_type == "recurring",
            weekday=weekday if schedule_type == "recurring" else None,
            start_time=start_time if schedule_type == "recurring" else None,
            end_time=end_time if schedule_type == "recurring" else None,
            starts_at=(
                as_seoul_time(starts_at) if starts_at and schedule_type == "one_time" else None
            ),
            ends_at=as_seoul_time(ends_at) if ends_at and schedule_type == "one_time" else None,
            before_buffer_minutes=before_buffer_minutes,
            after_buffer_minutes=after_buffer_minutes,
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error


@router.post("")
def create_block(
    request: Request,
    source: str = Form(),
    title: str = Form(),
    schedule_type: str = Form(),
    weekday: int | None = Form(None),
    weekdays: list[int] = Form([]),
    start_time: time | None = Form(None),
    end_time: time | None = Form(None),
    starts_at: datetime | None = Form(None),
    ends_at: datetime | None = Form(None),
    before_buffer_minutes: int | None = Form(None),
    after_buffer_minutes: int | None = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    default_before, default_after = service.buffer_defaults(db, user_id)[source]
    effective_weekday = weekdays[0] if weekdays else weekday
    data = _to_input(
        source=source,
        title=title,
        schedule_type=schedule_type,
        weekday=effective_weekday,
        start_time=start_time,
        end_time=end_time,
        starts_at=starts_at,
        ends_at=ends_at,
        before_buffer_minutes=before_buffer_minutes
        if before_buffer_minutes is not None
        else default_before,
        after_buffer_minutes=after_buffer_minutes
        if after_buffer_minutes is not None
        else default_after,
        allow_google=False,
    )
    selected_weekdays = weekdays or [effective_weekday]
    if schedule_type == "recurring" and source == "timetable" and len(selected_weekdays) > 1:
        try:
            blocks = [
                data.model_copy(update={"weekday": selected}) for selected in selected_weekdays
            ]
            service.create_many(db, user_id, blocks)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors()) from error
    else:
        service.create(db, user_id, data)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/{block_id}")
def update_block(
    block_id: int,
    request: Request,
    source: str = Form(),
    title: str = Form(),
    schedule_type: str = Form(),
    weekday: int | None = Form(None),
    start_time: time | None = Form(None),
    end_time: time | None = Form(None),
    starts_at: datetime | None = Form(None),
    ends_at: datetime | None = Form(None),
    before_buffer_minutes: int = Form(15),
    after_buffer_minutes: int = Form(15),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    block = service.get_owned(db, user_id, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Busy block not found")
    data = _to_input(
        source=block.source,
        title=title,
        schedule_type=schedule_type,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        starts_at=starts_at,
        ends_at=ends_at,
        before_buffer_minutes=before_buffer_minutes,
        after_buffer_minutes=after_buffer_minutes,
        allow_google=True,
    )
    service.update(db, block, data, mark_locally_modified=block.source == "google_calendar")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/buffers/{source}")
def update_source_buffers(
    source: str,
    request: Request,
    before_buffer_minutes: int = Form(15),
    after_buffer_minutes: int = Form(15),
    apply_existing: bool = Form(False),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if source not in {"timetable", "manual", "google_calendar"}:
        raise HTTPException(status_code=404)
    if not 0 <= before_buffer_minutes <= 720 or not 0 <= after_buffer_minutes <= 720:
        raise HTTPException(status_code=422, detail="Buffers must be between 0 and 720 minutes")
    user_id = _current_user_id(request, db)
    service.update_buffer_defaults(
        db,
        user_id,
        source,
        before_buffer_minutes,
        after_buffer_minutes,
        apply_existing=apply_existing,
    )
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/{block_id}/delete")
def delete_block(
    block_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    block = service.get_owned(db, user_id, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Busy block not found")
    if block.source == "google_calendar" and block.external_event_id:
        from app.google_calendar import service as google_calendar_service

        google_calendar_service.exclude_event(db, user_id, block.external_event_id)
    service.delete(db, block)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/timetable/reset")
def reset_timetable(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    user_id = _current_user_id(request, db)
    service.delete_for_source(db, user_id, "timetable")
    return RedirectResponse(url="/dashboard", status_code=303)
