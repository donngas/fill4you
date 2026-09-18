from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.accounts.service import get_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.i18n import Language, translate

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/")
def home(
    request: Request,
    lang: Language = "ko",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = get_user(db, request.session.get("user_id"))
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "lang": lang,
            "user": user,
            "google_configured": settings.google_oauth_configured,
            "development_login_enabled": settings.development_login_enabled,
            "t": lambda key: translate(key, lang),
            "auth_error": request.query_params.get("auth_error"),
        },
    )
