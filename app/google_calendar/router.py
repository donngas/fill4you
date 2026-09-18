from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.core.config import Settings, get_settings
from app.core.csrf import require_csrf
from app.core.database import get_db
from app.google_calendar import service

router = APIRouter(prefix="/google-calendar", tags=["google-calendar"])


@router.post("/sync")
def sync_google_calendar(
    request: Request,
    overwrite_local_changes: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
):
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    try:
        result = service.sync_for_user(
            db, user.id, settings, overwrite_local_changes=overwrite_local_changes
        )
    except service.GoogleCalendarError:
        request.session["google_sync_message"] = (
            "Google Calendar 동기화에 실패했습니다. 다시 로그인해 보세요."
        )
    else:
        request.session["google_sync_message"] = (
            f"Google Calendar 동기화 완료: {result.created}개 추가, {result.updated}개 갱신"
        )
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/calendars")
def save_calendar_selection(
    request: Request,
    calendar_ids: list[str] = Form([]),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
):
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    try:
        service.update_selected_calendars(db, user.id, set(calendar_ids))
        result = service.sync_for_user(db, user.id, settings)
    except service.GoogleCalendarError:
        request.session["google_sync_message"] = (
            "캘린더 선택을 저장하지 못했습니다. 다시 시도해 주세요."
        )
    else:
        request.session["google_sync_message"] = (
            f"선택한 캘린더를 동기화했습니다: {result.created}개 추가, {result.updated}개 갱신"
        )
    return RedirectResponse(url="/dashboard", status_code=303)
