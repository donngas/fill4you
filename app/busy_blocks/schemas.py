from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, model_validator

BusyBlockSource = Literal["timetable", "manual", "google_calendar"]


class BusyBlockInput(BaseModel):
    source: BusyBlockSource
    title: str
    is_recurring: bool
    weekday: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "BusyBlockInput":
        if not self.title.strip():
            raise ValueError("A title is required")
        if self.is_recurring:
            if None in (self.weekday, self.start_time, self.end_time):
                raise ValueError("A recurring block needs a weekday, start time, and end time")
            if not 0 <= self.weekday <= 6:
                raise ValueError("Weekday must be between 0 and 6")
            if self.end_time <= self.start_time:
                raise ValueError("End time must be after start time")
        else:
            if self.starts_at is None or self.ends_at is None:
                raise ValueError("A one-time block needs start and end datetimes")
            if self.ends_at <= self.starts_at:
                raise ValueError("End time must be after start time")
        return self
