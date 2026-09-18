from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.accounts.service import get_or_create_development_user, upsert_google_user
from app.core.config import Settings, get_settings
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["accounts"])
oauth = OAuth()


def _google_client(settings: Settings):
    if not settings.google_oauth_configured:
        return None
    if "google" not in oauth._clients:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly"
            },
        )
    return oauth.create_client("google")


@router.get("/google")
async def google_login(request: Request, settings: Settings = Depends(get_settings)):
    google = _google_client(settings)
    if google is None:
        url = "/?" + urlencode({"auth_error": "google_not_configured"})
        return RedirectResponse(url=url, status_code=303)
    return await google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    google = _google_client(settings)
    if google is None:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    token = await google.authorize_access_token(request)
    user_info = token.get("userinfo") or await google.userinfo(token=token)
    user = upsert_google_user(
        db,
        subject=user_info["sub"],
        email=user_info["email"],
        display_name=user_info.get("name") or user_info["email"],
        picture_url=user_info.get("picture"),
    )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.post("/development")
def development_login(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.development_login_enabled:
        raise HTTPException(status_code=404)
    user = get_or_create_development_user(db, settings.development_user_email)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
