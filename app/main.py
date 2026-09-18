from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.accounts.router import router as accounts_router
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
    https_only=settings.app_env == "production",
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
app.include_router(web_router)
app.include_router(accounts_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
