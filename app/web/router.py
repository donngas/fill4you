from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.bookmarklet import service as bookmarklet_service
from app.bookmarklet.router import bookmarklet_url
from app.busy_blocks import service as busy_block_service
from app.busy_blocks.models import BusyBlock
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.google_calendar import service as google_calendar_service
from app.shared.time import SEOUL, as_seoul_time

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = get_user(db, request.session.get("user_id"))
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "user": user,
            "development_login_enabled": settings.development_login_enabled,
            "auth_error": request.query_params.get("auth_error"),
        },
    )


def _block_for_client(block: BusyBlock) -> dict[str, str | int | bool | None]:
    starts_at = as_seoul_time(block.starts_at) if block.starts_at else None
    ends_at = as_seoul_time(block.ends_at) if block.ends_at else None
    return {
        "id": block.id,
        "source": block.source,
        "title": block.title,
        "isRecurring": block.is_recurring,
        "weekday": block.weekday
        if block.is_recurring
        else starts_at.weekday()
        if starts_at
        else None,
        "startTime": (
            block.start_time.isoformat(timespec="minutes")
            if block.start_time
            else starts_at.strftime("%H:%M")
            if starts_at
            else None
        ),
        "endTime": (
            block.end_time.isoformat(timespec="minutes")
            if block.end_time
            else ends_at.strftime("%H:%M")
            if ends_at
            else None
        ),
        "startsAt": starts_at.strftime("%Y-%m-%dT%H:%M") if starts_at else None,
        "endsAt": ends_at.strftime("%Y-%m-%dT%H:%M") if ends_at else None,
    }


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = get_user(db, request.session.get("user_id"))
    if user is None:
        return RedirectResponse(url="/?next=/dashboard", status_code=303)
    blocks = busy_block_service.list_for_user(db, user.id)
    new_bookmarklet_token = request.session.pop("new_bookmarklet_token", None)
    today = datetime.now(SEOUL).date()
    week_start = today - timedelta(days=today.weekday())
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "blocks": blocks,
            "blocks_json": [_block_for_client(block) for block in blocks],
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "bookmarklet_tokens": bookmarklet_service.list_tokens(db, user.id),
            "bookmarklet_url": (
                bookmarklet_url(str(request.base_url), new_bookmarklet_token)
                if new_bookmarklet_token
                else None
            ),
            "google_calendar_connected": google_calendar_service.has_token(db, user.id),
            "google_calendar_configured": settings.google_calendar_configured,
            "google_sync_message": request.session.pop("google_sync_message", None),
        },
    )
