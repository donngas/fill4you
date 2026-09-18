from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.availability.schemas import AvailabilityRequest, AvailabilityResponse
from app.availability.service import busy_preview_blocks, desired_mask
from app.bookmarklet.service import authenticate_token
from app.busy_blocks import service as busy_block_service
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limit import FixedWindowRateLimiter
from app.google_calendar import service as google_calendar_service

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])
bearer = HTTPBearer(auto_error=False)
# A real bookmarklet is normally invoked once or twice per poll.  These limits leave substantial
# headroom for retries while stopping the obvious request-flood and token-guessing attacks.
valid_token_limiter = FixedWindowRateLimiter(limit=30, window_seconds=60)
invalid_client_limiter = FixedWindowRateLimiter(limit=10, window_seconds=60)


def _rate_limit_error(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Too many availability requests. Please wait a moment and try again.",
        headers={"Retry-After": str(retry_after)},
    )


def _invalid_request_key(request: Request) -> str:
    # The app is not published directly in production: only cloudflared can reach it.  Its
    # forwarded client address is therefore safe to use when present; local development falls
    # back to the socket peer address.
    return request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )


@router.post("/when2meet", response_model=AvailabilityResponse)
def when2meet_availability(
    request: Request,
    payload: AvailabilityRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AvailabilityResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        retry_after = invalid_client_limiter.retry_after(_invalid_request_key(request))
        if retry_after:
            raise _rate_limit_error(retry_after)
        raise HTTPException(status_code=401, detail="Bookmarklet token required")
    token = authenticate_token(db, credentials.credentials)
    if token is None:
        retry_after = invalid_client_limiter.retry_after(_invalid_request_key(request))
        if retry_after:
            raise _rate_limit_error(retry_after)
        raise HTTPException(status_code=401, detail="Bookmarklet token is invalid or revoked")
    retry_after = valid_token_limiter.retry_after(token.token_digest)
    if retry_after:
        raise _rate_limit_error(retry_after)
    try:
        google_calendar_service.sync_for_user(db, token.user_id, settings)
    except google_calendar_service.GoogleCalendarError:
        # The bookmarklet remains useful with the last successfully imported events.
        pass
    blocks = busy_block_service.list_for_user(db, token.user_id)
    return AvailabilityResponse(
        desired=desired_mask(blocks, payload.slots, payload.slot_minutes),
        busy_blocks=busy_preview_blocks(
            blocks,
            payload.slots,
            payload.slot_minutes,
            include_titles=payload.include_busy_titles,
        ),
    )
