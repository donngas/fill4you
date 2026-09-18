import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.accounts.router import router as accounts_router
from app.availability.router import router as availability_router
from app.bookmarklet.router import router as bookmarklet_router
from app.busy_blocks.router import router as busy_blocks_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import SecurityHeadersMiddleware
from app.everytime_importer.router import router as everytime_importer_router
from app.google_calendar import service as google_calendar_service
from app.google_calendar.router import router as google_calendar_router
from app.web.router import router as web_router

settings = get_settings()
BASE_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)


def _sync_connected_calendars() -> None:
    with SessionLocal() as db:
        user_ids = google_calendar_service.connected_user_ids(db)
    for user_id in user_ids:
        try:
            with SessionLocal() as db:
                google_calendar_service.sync_for_user(db, user_id, settings)
        except google_calendar_service.GoogleCalendarError:
            logger.warning("Google Calendar periodic sync failed for user %s", user_id)


async def _periodically_sync_calendars() -> None:
    interval_seconds = settings.google_sync_interval_minutes * 60
    while True:
        await asyncio.sleep(interval_seconds)
        await asyncio.to_thread(_sync_connected_calendars)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = None
    if settings.google_calendar_configured:
        task = asyncio.create_task(_periodically_sync_calendars())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware, production=settings.app_env == "production")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
    domain=settings.session_cookie_domain,
    https_only=settings.session_https_only_enabled,
    same_site=settings.session_same_site,
)
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
app.include_router(web_router)
app.include_router(accounts_router)
app.include_router(busy_blocks_router)
app.include_router(availability_router)
app.include_router(bookmarklet_router)
app.include_router(google_calendar_router)
app.include_router(everytime_importer_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
