from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.accounts.router import router as accounts_router
from app.busy_blocks.router import router as busy_blocks_router
from app.core.config import get_settings
from app.web.router import router as web_router

settings = get_settings()
BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
