from datetime import datetime

from pydantic import BaseModel, field_validator


class AvailabilityRequest(BaseModel):
    slots: list[datetime]
    slot_minutes: int = 15
    include_busy_titles: bool = True

    @field_validator("slots")
    @classmethod
    def validate_slots(cls, slots: list[datetime]) -> list[datetime]:
        if not slots:
            raise ValueError("At least one poll slot is required")
        if len(slots) > 5000:
            raise ValueError("A request may contain at most 5000 slots")
        if any(slot.tzinfo is None for slot in slots):
            raise ValueError("Poll slot timestamps must include a timezone")
        return slots

    @field_validator("slot_minutes")
    @classmethod
    def validate_slot_minutes(cls, slot_minutes: int) -> int:
        if not 1 <= slot_minutes <= 60:
            raise ValueError("Poll slot duration must be between 1 and 60 minutes")
        return slot_minutes


class BusyPreviewBlock(BaseModel):
    id: int
    title: str | None = None
    slot_indexes: list[int]


class AvailabilityResponse(BaseModel):
    desired: list[bool]
    busy_blocks: list[BusyPreviewBlock]
