from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.google_calendar import service

router = APIRouter(prefix="/google-calendar", tags=["google-calendar"])


@router.post("/sync")
def sync_google_calendar(
    request: Request,
    overwrite_local_changes: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    try:
        result = service.sync_for_user(
            db, user.id, settings, overwrite_local_changes=overwrite_local_changes
        )
    except service.GoogleCalendarError as error:
        request.session["google_sync_message"] = str(error)
    else:
        request.session["google_sync_message"] = (
            f"Google Calendar 동기화 완료: {result.created}개 추가, {result.updated}개 갱신"
        )
    return RedirectResponse(url="/dashboard", status_code=303)
