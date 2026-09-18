from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.availability.schemas import AvailabilityRequest, AvailabilityResponse
from app.availability.service import desired_mask
from app.bookmarklet.service import authenticate_token
from app.busy_blocks import service as busy_block_service
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])
bearer = HTTPBearer(auto_error=False)


@router.post("/when2meet", response_model=AvailabilityResponse)
def when2meet_availability(
    payload: AvailabilityRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bookmarklet token required")
    token = authenticate_token(db, credentials.credentials)
    if token is None:
        raise HTTPException(status_code=401, detail="Bookmarklet token is invalid or revoked")
    blocks = busy_block_service.list_for_user(db, token.user_id)
    return AvailabilityResponse(desired=desired_mask(blocks, payload.slots, payload.slot_minutes))
