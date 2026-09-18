from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.availability.schemas import AvailabilityRequest, AvailabilityResponse
from app.availability.service import busy_preview_blocks, desired_mask
from app.bookmarklet.service import authenticate_token
from app.busy_blocks import service as busy_block_service
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.google_calendar import service as google_calendar_service

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])
bearer = HTTPBearer(auto_error=False)


@router.post("/when2meet", response_model=AvailabilityResponse)
def when2meet_availability(
    payload: AvailabilityRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AvailabilityResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bookmarklet token required")
    token = authenticate_token(db, credentials.credentials)
    if token is None:
        raise HTTPException(status_code=401, detail="Bookmarklet token is invalid or revoked")
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
